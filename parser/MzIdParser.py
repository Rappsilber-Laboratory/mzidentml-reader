"""
converts mzIdentML files to DB entries
"""
import base64
import gzip
import json
import ntpath
import os
import re
import struct
import traceback
import zipfile
from time import time

import obonet
from pyteomics import mzid  # https://pyteomics.readthedocs.io/en/latest/data.html#controlled-vocabularies
from pyteomics.auxiliary import cvquery
# noinspection PyProtectedMember
from pyteomics.xml import _local_name
from lxml import etree
from sqlalchemy.exc import SQLAlchemyError

from parser.APIWriter import APIWriter
from parser.peaklistReader.PeakListWrapper import PeakListWrapper


class MzIdParseException(Exception):
    """Exception raised when parsing mzIdentML files."""
    pass


# noinspection PyProtectedMember
class MzIdParser:
    """Class for parsing identification data from mzIdentML."""

    def __init__(self, mzid_path, temp_dir, peak_list_dir, writer, logger):
        """
        Initialise the Parser.

        :param mzid_path: path to mzidentML file
        :param temp_dir: absolute path to temp dir for unzipping/storing files
        :param peak_list_dir: path to the directory containing the peak list file(s)
        :param writer: result writer
        :param logger: logger
        """
        self.search_modifications = None
        self.mzid_path = mzid_path

        self.peak_list_readers = {}  # peak list readers indexed by spectraData_ref
        self.spectra_data_id_lookup = {}  # spectra_data_ref to spectra_data_id lookup
        self.sip_ref_to_sip_id_lookup = {}  # sip_ref to sip_id lookup
        self.sil_ref_to_protocol_id_lookup = {}  # sip_ref to sip_id lookup
        self.pep_ref_to_pep_id_lookup = {}  # peptide_ref to peptide_id lookup
        self.dbseqs = {}

        self.temp_dir = temp_dir
        if not self.temp_dir.endswith('/'):
            self.temp_dir += '/'
        self.peak_list_dir = peak_list_dir
        if peak_list_dir and not peak_list_dir.endswith('/'):
            self.peak_list_dir += '/'

        self.writer = writer
        self.logger = logger

        self.ms_obo = obonet.read_obo(
            'https://raw.githubusercontent.com/HUPO-PSI/psi-ms-CV/master/psi-ms.obo')

        self.contains_crosslinks = False

        self.warnings = set()
        self.write_new_upload()  # overridden (empty function) in xiSPEC subclass

        # init self.mzid_reader (pyteomics mzid reader)
        if self.mzid_path.endswith('.gz') or self.mzid_path.endswith('.zip'):
            self.mzid_path = MzIdParser.extract_mzid(self.mzid_path)

        self.logger.info('reading mzid - start ' + self.mzid_path)
        start_time = time()
        # schema:
        # https://raw.githubusercontent.com/HUPO-PSI/mzIdentML/master/schema/mzIdentML1.2.0.xsd
        try:
            self.mzid_reader = mzid.MzIdentML(self.mzid_path, retrieve_refs=False)
        except Exception as e:
            raise MzIdParseException(type(e).__name__, e.args)

        self.logger.info('reading mzid - done. Time: {} sec'.format(round(time() - start_time, 2)))

    def parse(self):
        """Parse the file."""
        start_time = time()
        self.upload_info()  # overridden (empty function) in xiSPEC subclass
        self.parse_analysis_protocol_collection()
        self.parse_spectradata_and_init_peak_list_readers()
        self.parse_analysis_collection()
        self.parse_db_sequences()  # overridden (empty function) in xiSPEC subclass
        self.parse_peptides()
        self.parse_peptide_evidences()
        self.check_target_proteins_have_sequence()
        self.main_loop()

        self.fill_in_missing_scores()  # empty here, overridden in xiSPEC subclass to do stuff
        self.write_other_info()  # overridden (empty function) in xiSPEC subclass

        self.logger.info('all done! Total time: ' + str(round(time() - start_time, 2)) + " sec")

    @staticmethod
    def check_spectra_data_validity(sp_datum):
        """
        Check if the SpectraData element is valid.
        :param sp_datum:
        """
        # is there anything we'd like to complain about?
        # SpectrumIDFormat
        if 'SpectrumIDFormat' not in sp_datum or sp_datum['SpectrumIDFormat'] is None:
            raise MzIdParseException('SpectraData is missing SpectrumIdFormat')
        if not hasattr(sp_datum['SpectrumIDFormat'], 'accession'):
            raise MzIdParseException('SpectraData.SpectrumIdFormat is missing accession')
        if sp_datum['SpectrumIDFormat'].accession is None:
            raise MzIdParseException('SpectraData.SpectrumIdFormat is missing accession')

        # FileFormat
        if 'FileFormat' not in sp_datum or sp_datum['FileFormat'] is None:
            raise MzIdParseException('SpectraData is missing FileFormat')
        if not hasattr(sp_datum['FileFormat'], 'accession'):
            raise MzIdParseException('SpectraData.FileFormat is missing accession')
        if sp_datum['FileFormat'].accession is None:
            raise MzIdParseException('SpectraData.FileFormat is missing accession')

        # location
        if 'location' not in sp_datum or sp_datum['location'] is None:
            raise MzIdParseException('SpectraData is missing location')

    def parse_spectradata_and_init_peak_list_readers(self):
        """
        Sets self.peak_list_readers by looping through SpectraData elements

        dictionary:
            key: spectra_data_ref
            value: associated peak_list_reader
        """
        peak_list_readers = {}
        spectra_data = []
        spectra_data_id_lookup = {}
        sd_int_id = 0
        for spectra_data_id in self.mzid_reader._offset_index["SpectraData"].keys():
            sp_datum = self.mzid_reader.get_by_id(spectra_data_id, tag_id='SpectraData')

            self.check_spectra_data_validity(sp_datum)

            peak_list_file_name = ntpath.basename(sp_datum['location'])
            file_format = sp_datum['FileFormat'].accession
            spectrum_id_format = sp_datum['SpectrumIDFormat'].accession

            if self.peak_list_dir:
                peak_list_file_path = self.peak_list_dir + peak_list_file_name
                # noinspection PyBroadException
                try:
                    peak_list_reader = PeakListWrapper(
                        peak_list_file_path,
                        file_format,
                        spectrum_id_format
                    )
                # ToDo: gz/zip code parts could do with refactoring
                except Exception:
                    # try gz version
                    try:
                        peak_list_reader = PeakListWrapper(
                            PeakListWrapper.extract_gz(peak_list_file_path + '.gz'),
                            file_format,
                            spectrum_id_format
                        )
                    except IOError:
                        # look for missing peak lists in zip files
                        for file in os.listdir(self.peak_list_dir):
                            if file.endswith(".zip"):
                                zip_file = os.path.join(self.peak_list_dir, file)
                                try:
                                    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                                        zip_ref.extractall(self.peak_list_dir)
                                except IOError:
                                    raise IOError()
                        try:
                            peak_list_reader = PeakListWrapper(
                                peak_list_file_path,
                                file_format,
                                spectrum_id_format
                            )
                        except Exception:
                            raise MzIdParseException('Missing peak list file: %s' % peak_list_file_path)

                peak_list_readers[spectra_data_id] = peak_list_reader

            spectra_datum = {
                'id': sd_int_id,
                'upload_id': self.writer.upload_id,
                # 'spectra_data_ref': spectra_data_id,
                'location': sp_datum['location'],
                'name': sp_datum.get('name', None),
                'external_format_documentation': sp_datum.get('externalFormatDocumentation', None),
                'file_format': file_format,
                'spectrum_id_format': spectrum_id_format
            }

            spectra_data.append(spectra_datum)
            spectra_data_id_lookup[spectra_data_id] = sd_int_id
            sd_int_id += 1

        self.writer.write_data('spectradata', spectra_data)

        self.peak_list_readers = peak_list_readers
        self.spectra_data_id_lookup = spectra_data_id_lookup

    def parse_analysis_protocol_collection(self):
        """Parse the AnalysisProtocolCollection and write SpectrumIdentificationProtocols."""
        self.logger.info('parsing AnalysisProtocolCollection- start')
        start_time = time()

        sid_protocols = []
        search_modifications = []
        enzymes = []
        sip_int_id = 0
        for sid_protocol_id in self.mzid_reader._offset_index['SpectrumIdentificationProtocol'].keys():
            try:
                sid_protocol = self.mzid_reader.get_by_id(sid_protocol_id, detailed=True)
            except KeyError:
                raise MzIdParseException('SpectrumIdentificationProtocol not found: %s, '
                                         'this can be caused by any schema error, '
                                         'such as missing name or accession in a cvParam ' % sid_protocol_id)

            # FragmentTolerance
            try:
                frag_tol = sid_protocol['FragmentTolerance']
                frag_tol_plus = frag_tol['search tolerance plus value']
                frag_tol_value = re.sub('[^0-9,.]', '', str(frag_tol_plus))
                if frag_tol_plus.unit_info.lower() == 'parts per million':
                    frag_tol_unit = 'ppm'
                elif frag_tol_plus.unit_info.lower() == 'dalton':
                    frag_tol_unit = 'Da'
                else:
                    frag_tol_unit = frag_tol_plus.unit_info

                if not all([
                    frag_tol['search tolerance plus value'] ==
                    frag_tol['search tolerance minus value'],
                    frag_tol['search tolerance plus value'].unit_info ==
                    frag_tol['search tolerance minus value'].unit_info
                ]):
                    raise MzIdParseException("Different values for search tolerance plus value"
                                             "and minus value are not yet supported.")

            except KeyError:
                self.warnings.add("could not parse ms2tolerance. Falling back to default: 10 ppm.")
                frag_tol_value = '10'
                frag_tol_unit = 'ppm'

            try:
                analysis_software = self.mzid_reader.get_by_id(sid_protocol['analysisSoftware_ref'])
            except KeyError:
                analysis_software = None
                self.warnings.add(
                    f'No analysis software given for SpectrumIdentificationProtocol {sid_protocol}.')

            # Additional search parameters
            add_sp = sid_protocol.get('AdditionalSearchParams', {})
            # Threshold
            threshold = sid_protocol.get('Threshold', {})
            data = {
                'id': sip_int_id,
                'upload_id': self.writer.upload_id,
                'sip_ref': sid_protocol['id'],
                'search_type': sid_protocol['SearchType'],
                'frag_tol': frag_tol_value,
                'frag_tol_unit': frag_tol_unit,
                'additional_search_params': cvquery(add_sp),
                'analysis_software': analysis_software,
                'threshold': threshold,
            }

            # Modifications
            if 'ModificationParams' in sid_protocol:
                mod_index = 0
                for mod in sid_protocol['ModificationParams']['SearchModification']:
                    # parse specificity rule accessions
                    specificity_rules = mod.get('SpecificityRules', [])  # second param is default value
                    spec_rule_accessions = []  # there may be many
                    for spec_rule in specificity_rules:
                        spec_rule_accession = cvquery(spec_rule)
                        if len(spec_rule_accession) != 1:
                            raise MzIdParseException(
                                f'Error when parsing SpecificityRules from SearchModification:\n'
                                f'{json.dumps(mod)}')
                        spec_rule_accessions.append(list(spec_rule_accession.keys())[0])

                    accessions = cvquery(mod)
                    # other modifications
                    # name
                    mod_name = None
                    mod_accession = None
                    # find the matching accession for the name cvParam.
                    for i, acc in enumerate(accessions):
                        # ToDo: be more strict with the allowed accessions?
                        match = re.match('(?:MOD|UNIMOD|MS|XLMOD):[0-9]+', acc)
                        if match:
                            # not crosslink donor
                            if match.group() != 'MS:1002509':
                                mod_accession = acc
                            # name
                            # unknown modification
                            if match.group() == 'MS:1001460':
                                mod_name = "({0:.2f})".format(mod['massDelta'])
                            # others
                            elif match.group() != 'MS:1002509':
                                # name is the key in mod dict corresponding to the matched accession.
                                mod_name = accessions[acc]  # list(mod.keys())[i]

                    crosslinker_id = cvquery(mod, "MS:1002509")
                    if crosslinker_id is None:
                        crosslinker_id = cvquery(mod, "MS:1002510")
                        if crosslinker_id is not None:
                            mod_name = 'crosslink acceptor'

                    if mod_name is None or mod_accession is None:
                        raise MzIdParseException(
                            f'Error parsing <SearchModification>s! '
                            f'Could not parse name/accession of modification:\n{json.dumps(mod)}')

                    if crosslinker_id:  # it's a string but don't want to convert null to word 'None'
                        crosslinker_id = str(crosslinker_id)

                    mass_delta = mod['massDelta']
                    if mass_delta == float('inf') or mass_delta == float('-inf'):
                        mass_delta = None
                        self.warnings.add("SearchModification with massDelta of +/- infinity found.")

                    search_modifications.append({
                        'id': mod_index,
                        'upload_id': self.writer.upload_id,
                        'protocol_id': sid_protocol['id'],
                        'mod_name': mod_name,
                        'mass': mass_delta,
                        'residues': ''.join([r for r in mod['residues'] if r != ' ']),
                        'specificity_rules': spec_rule_accessions,
                        'fixed_mod': mod['fixedMod'],
                        'accession': mod_accession,
                        'crosslinker_id': crosslinker_id
                    })
                    mod_index += 1

            # Enzymes
            if 'Enzymes' in sid_protocol:
                for enzyme in sid_protocol['Enzymes']['Enzyme']:

                    enzyme_name = None
                    enzyme_accession = None

                    # optional child element SiteRegexp
                    site_regexp = enzyme.get('SiteRegexp', None)

                    # optional child element EnzymeName
                    try:
                        enzyme_name_el = enzyme['EnzymeName']
                        # get cvParams that are children of 'cleavage agent name' (MS:1001045)
                        # there is a mandatory UserParam subelement of EnzymeName which we are ignoring
                        enzyme_name = self.get_cv_params(enzyme_name_el, 'MS:1001045')
                        if len(enzyme_name) > 1:
                            raise MzIdParseException(
                                f'Error when parsing EnzymeName from Enzyme:\n{json.dumps(enzyme)}')
                        enzyme_name_cv = list(enzyme_name.keys())[0]
                        enzyme_name = enzyme_name_cv
                        enzyme_accession = enzyme_name_cv.accession
                        # if the site_regexp was missing look it up using obo
                        if site_regexp is None:
                            for child, parent, key in self.ms_obo.out_edges(enzyme_accession,
                                                                            keys=True):
                                if key == 'has_regexp':
                                    site_regexp = self.ms_obo.nodes[parent]['name']
                    # fallback if no EnzymeName
                    except KeyError:
                        try:
                            # optional potentially ambiguous common name
                            enzyme_name = enzyme['name']
                        except KeyError:
                            # no name attribute
                            pass

                    enzymes.append({
                        'id': enzyme['id'],
                        'upload_id': self.writer.upload_id,
                        'protocol_id': sid_protocol['id'],
                        'name': enzyme_name,
                        'c_term_gain': enzyme.get('cTermGain', None),
                        'n_term_gain': enzyme.get('nTermGain', None),
                        'min_distance': enzyme.get('minDistance', None),
                        'missed_cleavages': enzyme.get('missedCleavages', None),
                        'semi_specific': enzyme.get('semiSpecific', None),
                        'site_regexp': site_regexp,
                        'accession': enzyme_accession
                    })

            sid_protocols.append(data)
            self.sip_ref_to_sip_id_lookup[sid_protocol['id']] = sip_int_id
            sip_int_id += 1

        self.mzid_reader.reset()
        self.logger.info('parsing AnalysisProtocolCollection - done. Time: {} sec'.format(
            round(time() - start_time, 2)))

        self.writer.write_data('spectrumidentificationprotocol', sid_protocols)
        if search_modifications:
            self.writer.write_data('searchmodification', search_modifications)
        if enzymes:
            self.writer.write_data('enzyme', enzymes)

    def parse_analysis_collection(self):
        """
        Parse the AnalysisCollection element of the mzIdentML file.
        """
        self.logger.info('parsing AnalysisCollection - start')
        start_time = time()
        spectrum_identification = []
        for si_key in self.mzid_reader._offset_index['SpectrumIdentification'].keys():
            si = self.mzid_reader.get_by_id(si_key, detailed=True)
            spectra_data_refs = []
            for input_spectra in si['InputSpectra']:
                spectra_data_refs.append(input_spectra['spectraData_ref'])
            search_database_refs = []
            for search_database_ref in si['SearchDatabaseRef']:
                search_database_refs.append(search_database_ref['searchDatabase_ref'])
            si_data = {
                'upload_id': self.writer.upload_id,
                'spectrum_identification_protocol_ref': si['spectrumIdentificationProtocol_ref'],
                'spectrum_identification_list_ref': si['spectrumIdentificationList_ref'],
                'spectrum_identification_id': si_key,
                'spectra_data_refs': spectra_data_refs,
                'search_database_refs': search_database_refs
            }
            spectrum_identification.append(si_data)
            self.sil_ref_to_protocol_id_lookup[si['spectrumIdentificationList_ref']] = self.sip_ref_to_sip_id_lookup[si['spectrumIdentificationProtocol_ref']]
        self.mzid_reader.reset()
        self.logger.info('parsing AnalysisCollection - done. Time: {} sec'.format(
            round(time() - start_time, 2)))

        self.writer.write_data('analysiscollectionspectrumidentification', spectrum_identification)

    def parse_db_sequences(self):
        """Parse and write the DBSequences."""
        self.logger.info('parse db sequences - start')
        start_time = time()

        db_sequences = []
        for db_id in self.mzid_reader._offset_index["DBSequence"].keys():
            db_sequence = self.mzid_reader.get_by_id(db_id, tag_id='DBSequence')
            db_sequence_data = {
                'id': db_id,
                'accession': db_sequence["accession"],
                'upload_id': self.writer.upload_id
            }

            # name, optional elem att
            if "name" in db_sequence:
                db_sequence_data['name'] = db_sequence["name"]
            else:
                db_sequence_data['name'] = db_sequence["accession"]

            # description
            try:
                # get the key by checking for the protein description accession number
                db_sequence_data['description'] = cvquery(db_sequence, 'MS:1001088')
            except ValueError:
                db_sequence_data['description'] = None

            # Seq is optional child elem of DBSequence
            if "Seq" in db_sequence and isinstance(db_sequence["Seq"], str):
                db_sequence_data['sequence'] = db_sequence["Seq"]
            elif "length" in db_sequence:
                db_sequence_data['sequence'] = "X" * db_sequence["length"]

            db_sequences.append(db_sequence_data)
            self.dbseqs[db_id] = db_sequence_data

        self.writer.write_data('dbsequence', db_sequences)

        self.logger.info('parse db sequences - done. Time: {} sec'.format(
            round(time() - start_time, 2)))

    def parse_peptides(self):
        """Parse and write the peptides."""
        start_time = time()
        self.logger.info('parse peptides - start')

        peptide_index = 0
        peptides = []
        for pep_id in self.mzid_reader._offset_index["Peptide"].keys():
            peptide = self.mzid_reader.get_by_id(pep_id, tag_id='Peptide')
            link_site_donor = None
            link_site_acc = None
            crosslinker_modmass = 0
            crosslinker_pair_id_donor = None
            crosslinker_pair_id_acceptor = None
            crosslinker_accession = None
            mod_pos = []
            mod_accessions = []
            mod_avg_masses = []
            mod_monoiso_masses = []
            # if someone tried to record higher order crosslinks (multiple donors/acceptors) it would break this
            if 'Modification' in peptide.keys():
                # parse modifications and crosslink info
                for mod in peptide['Modification']:
                    # crosslink donor
                    temp = cvquery(mod, 'MS:1002509')
                    if temp is not None:
                        crosslinker_pair_id_donor = temp
                        link_site_donor = mod['location']
                        crosslinker_modmass = mod['monoisotopicMassDelta']
                        # if mod has key 'name' - it should, as consequence of having 'suitably sourced CV param'
                        if 'name' in mod:
                            crosslinker_accession = mod['name'].accession
                        else:
                            crosslinker_accession = None
                            # Todo: reinstate this warning
                            # self.warnings.append(
                            #     f'No accession for crosslinker {crosslinker_pair_id} for peptide {pep_id}')
                    # crosslink acceptor/
                    else:
                        temp = cvquery(mod, 'MS:1002510')
                        if temp is not None:
                            crosslinker_pair_id_acceptor = temp
                            link_site_acc = mod['location']
                        else:
                            # no crosslinker modifications
                            cvs = cvquery(mod)
                            mod_pos.append(mod['location'])
                            mod_accessions.append(cvs)  # unit of fragment loss is always daltons
                            mod_avg_masses.append(mod.get('avgMassDelta', None))
                            mod_monoiso_masses.append(mod.get('monoisotopicMassDelta', None))

            crosslinker_pair_id = None
            link_site1 = None
            link_site2 = None
            if crosslinker_pair_id_donor is not None and crosslinker_pair_id_acceptor is None:
                # crosslink donor
                link_site1 = link_site_donor
                link_site2 = None
                crosslinker_pair_id = crosslinker_pair_id_donor
            elif crosslinker_pair_id_donor is None and crosslinker_pair_id_acceptor is not None:
                # crosslink acceptor
                link_site1 = link_site_acc
                link_site2 = None
                crosslinker_pair_id = crosslinker_pair_id_acceptor
            elif crosslinker_pair_id_donor is not None and crosslinker_pair_id_acceptor is not None:
                if crosslinker_pair_id_donor == crosslinker_pair_id_acceptor:
                    # loop link
                    link_site1 = link_site_donor
                    link_site2 = link_site_acc
                    crosslinker_pair_id = crosslinker_pair_id_donor
                else:
                    raise MzIdParseException(f'Crosslinker pair ids do not match for peptide {pep_id}, higher order '
                                             f'crosslinks, including multiple looplinks in peptide not supported')

            # link site validity check
            if link_site1 is not None and link_site1 < 0:
                self.logger.error(f'Link site for peptide {pep_id} is negative')
            if link_site2 is not None and link_site2 < 0:
                self.logger.error(f'Link site for peptide {pep_id} is negative')

            peptide_data = {
                'id': peptide_index,
                # 'ref': peptide['id'],
                'upload_id': self.writer.upload_id,
                'base_sequence': peptide['PeptideSequence'],
                'mod_accessions': mod_accessions,
                'mod_positions': mod_pos,
                'mod_avg_mass_deltas': mod_avg_masses,
                'mod_monoiso_mass_deltas': mod_monoiso_masses,
                'link_site1': link_site1,
                'link_site2': link_site2,
                'crosslinker_modmass': crosslinker_modmass,
                'crosslinker_pair_id': crosslinker_pair_id,
                'crosslinker_accession': crosslinker_accession
            }

            peptides.append(peptide_data)
            self.pep_ref_to_pep_id_lookup[peptide['id']] = peptide_index

            # Batch write 500 peptides into the DB
            if peptide_index > 0 and peptide_index % 500 == 0:
                self.logger.debug('writing 500 peptides to DB')
                try:
                    self.writer.write_data('modifiedpeptide', peptides)
                    peptides = []
                except Exception as e:
                    raise e
            peptide_index += 1

        # write the remaining peptides
        try:
            self.writer.write_data('modifiedpeptide', peptides)
        except Exception as e:
            raise e

        self.logger.info(
            f'parse peptides - done. Time: {round(time() - start_time, 2)} sec')


    def parse_peptide_evidences(self):
        """Parse and write the peptide evidences."""
        start_time = time()
        self.logger.info('parse peptide evidences - start')

        for db_seq in self.dbseqs.values():
            db_seq['is_decoy'] = False

        pep_evidences = []
        for pep_ev_id in self.mzid_reader._offset_index["PeptideEvidence"].keys():
            peptide_evidence = self.mzid_reader.get_by_id(pep_ev_id, tag_id='PeptideEvidence',
                                                          retrieve_refs=False)

            pep_start = -1
            if "start" in peptide_evidence:
                pep_start = peptide_evidence["start"]  # start att, optional

            is_decoy = False
            if "isDecoy" in peptide_evidence:
                is_decoy = peptide_evidence["isDecoy"]  # isDecoy att, optional
                if is_decoy:
                    self.dbseqs[peptide_evidence["dBSequence_ref"]][is_decoy] = True


            pep_ev_data = {
                'upload_id': self.writer.upload_id,
                'peptide_id': self.pep_ref_to_pep_id_lookup[peptide_evidence["peptide_ref"]],
                'dbsequence_id': peptide_evidence["dBSequence_ref"],
                # 'protein_accession': seq_id_to_acc_map[peptide_evidence["dBSequence_ref"]],
                'pep_start': pep_start,
                'is_decoy': is_decoy,
            }

            pep_evidences.append(pep_ev_data)

            # Batch write 500 peptide evidences into the DB
            if len(pep_evidences) % 500 == 0:
                self.logger.debug('writing 500 peptide_evidences to DB')
                try:
                    self.writer.write_data('peptideevidence', pep_evidences)
                    pep_evidences = []
                except Exception as e:
                    raise e

        # write the remaining data
        try:
            self.writer.write_data('peptideevidence', pep_evidences)
        except Exception as e:
            raise e

        self.mzid_reader.reset()

        self.logger.info('parse peptide evidences - done. Time: {} sec'.format(
            round(time() - start_time, 2)))

    def check_target_proteins_have_sequence(self):
        """
        Check that all target proteins have a sequence.
        """

        for db_seq in self.dbseqs.values():
            if 'sequence' not in db_seq and not db_seq['is_decoy']:
                raise MzIdParseException(f"DBSequence {db_seq['accession']} has no sequence.")

    def main_loop(self):
        """Parse the <SpectrumIdentificationResult>s and <SpectrumIdentificationItem>s within."""
        main_loop_start_time = time()
        self.logger.info('main loop - start')

        msi_regex = re.compile(r'^([0-9]+)(?::(P|C))$')

        spec_count = 0
        spectra = []
        spectrum_identifications = []

        # iterate over all the spectrum identification lists
        for sil_id in self.mzid_reader._offset_index["SpectrumIdentificationList"].keys():
            # sil = self.mzid_reader.get_by_id(sil_id, tag_id='SpectrumIdentificationList')
            self.mzid_reader.reset()
            for sid_result in iterfind_when(
                    self.mzid_reader,
                    "SpectrumIdentificationResult",
                    "SpectrumIdentificationList",
                    lambda x: x.attrib["id"] == sil_id,
                    retrieve_refs=False
            ):
                if self.peak_list_dir:
                    peak_list_reader = self.peak_list_readers[sid_result['spectraData_ref']]

                    spectrum = peak_list_reader[sid_result["spectrumID"]]

                    # convert mz and intensity numpy arrays into tightly packed binary objects
                    mz_blob = spectrum.mz_values.tolist()
                    mz_blob = struct.pack(f'{len(mz_blob)}d', *mz_blob)
                    intensity_blob = spectrum.int_values.tolist()
                    intensity_blob = struct.pack(f'{len(intensity_blob)}d', *intensity_blob)
                    # Encode binary data using base64 to enable transmitting in API call and then decode in API
                    if isinstance(self.writer, APIWriter):
                        mz_blob = base64.b64encode(mz_blob).decode('utf-8')
                        intensity_blob = base64.b64encode(intensity_blob).decode('utf-8')

                    spectra.append({
                        'id': sid_result["spectrumID"],
                        'spectra_data_id': self.spectra_data_id_lookup[sid_result['spectraData_ref']],
                        'upload_id': self.writer.upload_id,
                        'peak_list_file_name': ntpath.basename(peak_list_reader.peak_list_path),
                        'precursor_mz': spectrum.precursor['mz'],
                        'precursor_charge': spectrum.precursor['charge'],
                        'mz': mz_blob,
                        'intensity': intensity_blob,
                        'retention_time': spectrum.rt
                    })

                crosslink_ident_dict = dict()
                noncov_ident_dict = dict()
                linear_ident_dict = dict()
                linear_index = -1  # negative index values for linear peptides

                for spec_id_item in sid_result['SpectrumIdentificationItem']:
                    cvs = cvquery(spec_id_item)
                    # local_ident_id is the value of crosslink spectrum identifentification item,
                    # of noncov. assoc. sii or of id made up for linear
                    if 'MS:1002511' in cvs:
                        self.contains_crosslinks = True
                        local_ident_id = cvs['MS:1002511']
                        ident_dict = crosslink_ident_dict
                    elif 'MS:1003331' in cvs:
                        local_ident_id = cvs['MS:1003331']
                        ident_dict = noncov_ident_dict
                    else:  # assuming linear
                        local_ident_id = linear_index
                        linear_index -= 1
                        ident_dict = linear_ident_dict

                    # check if seen it before
                    if local_ident_id in ident_dict.keys():
                        # do crosslink specific stuff
                        ident_data = ident_dict.get(local_ident_id)
                        ident_data['pep2_id'] = self.pep_ref_to_pep_id_lookup[spec_id_item['peptide_ref']]
                    else:
                        # do stuff common to linears and crosslinks

                        psm_level_stats = self.get_cv_params(spec_id_item, 'MS:1001143')  # 'MS:1002347')

                        rank = spec_id_item['rank']
                        # from mzidentML schema 1.2.0: For PMF data, the rank attribute may be
                        # meaningless and values of rank = 0 should be given.
                        # xiSPEC front-end expects rank = 1 as default
                        if rank is None or int(rank) == 0:
                            rank = 1

                        calculated_mass_to_charge = None
                        if 'calculatedMassToCharge' in spec_id_item.keys():
                            calculated_mass_to_charge = float(spec_id_item['calculatedMassToCharge'])

                        msi_id = None
                        msi_pc = None
                        if 'MS:1003332' in cvs:
                            msi = cvs['MS:1003332']
                            m = msi_regex.match(msi)
                            msi_id = m[1]
                            msi_pc = m[2]

                        sd_int_id = self.spectra_data_id_lookup[sid_result['spectraData_ref']]
                        ident_data = {
                            'id': spec_id_item['id'],
                            'upload_id': self.writer.upload_id,
                            'spectrum_id': sid_result['spectrumID'],
                            'spectra_data_id': sd_int_id,
                            'pep1_id': self.pep_ref_to_pep_id_lookup[spec_id_item['peptide_ref']],
                            'pep2_id': None,
                            'charge_state': int(spec_id_item['chargeState']),
                            'pass_threshold': spec_id_item['passThreshold'],
                            'rank': int(rank),
                            'scores': psm_level_stats,
                            'exp_mz': spec_id_item['experimentalMassToCharge'],
                            'calc_mz': calculated_mass_to_charge,
                            'sip_id': self.sil_ref_to_protocol_id_lookup[sil_id],
                            'multiple_spectra_identification_id': msi_id,
                            'multiple_spectra_identification_pc': msi_pc,
                        }

                        ident_dict[local_ident_id] = ident_data

                spectrum_identifications += linear_ident_dict.values()
                spectrum_identifications += crosslink_ident_dict.values()
                spectrum_identifications += noncov_ident_dict.values()
                spec_count += 1

                if spec_count % 500 == 0:
                    self.logger.debug('writing 500 entries (500 spectra and their idents) to DB')
                    try:
                        if self.peak_list_dir:
                            self.writer.write_data('spectrum', spectra)
                        spectra = []
                        self.writer.write_data('match', spectrum_identifications)
                        spectrum_identifications = []
                    except Exception as e:
                        print(f"Caught an exception while writing data: {e}")
                        traceback.print_exc()

        # end main loop
        self.logger.info('main loop - done Time: {} sec'.format(
            round(time() - main_loop_start_time, 2)))

        # once loop is done write remaining data to DB
        db_wrap_up_start_time = time()
        self.logger.info('write remaining entries to DB - start')

        if self.peak_list_dir and spectra:  # spectra is not empty
            self.writer.write_data('spectrum', spectra)
        if spectrum_identifications:  # spectrum_identifications is not empty
            self.writer.write_data('match', spectrum_identifications)

        self.logger.info('write remaining entries to DB - done.  Time: {} sec'.format(
            round(time() - db_wrap_up_start_time, 2)))

    # noinspection PyBroadException
    def upload_info(self):
        """write mzid file level info to the DB."""
        upload_info_start_time = time()
        self.logger.info('parse upload info - start')
        self.mzid_reader.reset()
        # Analysis Software List - optional element
        # noinspection PyBroadException
        try:
            analysis_software_list = self.mzid_reader.iterfind('AnalysisSoftwareList').next()
        except Exception:
            analysis_software_list = {}

        spectra_formats = []
        for spectra_data_id in self.mzid_reader._offset_index["SpectraData"].keys():
            sp_datum = self.mzid_reader.get_by_id(spectra_data_id, tag_id='SpectraData',
                                                  detailed=True)
            spectra_formats.append(sp_datum)

        # Provider - optional element
        try:
            provider = self.mzid_reader.iterfind('Provider').next()
        except Exception:
            provider = {}
        self.mzid_reader.reset()

        # AuditCollection - optional element
        try:
            audits = self.mzid_reader.iterfind('AuditCollection').next()
        except Exception:
            audits = {}
        self.mzid_reader.reset()

        # AnalysisSampleCollection - optional element
        try:
            samples = self.mzid_reader.iterfind('AnalysisSampleCollection').next()['Sample']
        except Exception:
            samples = {}
        self.mzid_reader.reset()

        # BibliographicReference - optional element
        bib_refs = []
        for bib in self.mzid_reader.iterfind('BibliographicReference'):
            bib_refs.append(bib)
        self.mzid_reader.reset()

        self.writer.write_mzid_info(analysis_software_list, spectra_formats, provider, audits, samples, bib_refs,
                                    self.writer.upload_id)

        self.logger.info('getting upload info - done  Time: {} sec'.format(
            round(time() - upload_info_start_time, 2)))

    def fill_in_missing_scores(self):
        """
        Legacy xiSPEC, ignore
        """
        pass

    def write_new_upload(self):
        """Write new upload."""
        try:
            filename = os.path.basename(self.mzid_path)
            upload_data = {
                'identification_file_name': filename,
                'project_id': self.writer.pxid,
                'identification_file_name_clean': re.sub(r'[^0-9a-zA-Z-]+', '-', filename)
            }
            table = 'upload'

            response = self.writer.write_new_upload(table, upload_data)
            if response:
                self.writer.upload_id = int(response)
            else:
                raise Exception("Response is not available to create a upload ID")
        except SQLAlchemyError as e:
            print(f"Error during database insert: {e}")

    def write_other_info(self):
        """Write remaining information into Upload table."""
        self.writer.write_other_info(self.contains_crosslinks, list(self.warnings), self.writer.upload_id)

    @staticmethod
    def get_accessions(element):
        """Get the cvParam accessions for the given element. BUT ALSO INCLUDE EMPTY STRING FOR NON CV PARAMS."""
        accessions = []
        for el in element.keys():
            if hasattr(el, 'accession'):
                accessions.append(el.accession)
            else:
                accessions.append('')
        return accessions

    def get_cv_params(self, element, super_cls_accession=None):
        """
        Get the cvParams of an element.

        :param element: (dict) element from MzIdParser (pyteomics).
        :param super_cls_accession: (str) accession number of the superclass
        :return: filtered dictionary of cvParams
        """
        accessions = self.get_accessions(element)

        if super_cls_accession is None:
            filtered_idx = [i for i, a in enumerate(accessions) if a != '']
        else:
            children = []
            if not isinstance(super_cls_accession, list):
                super_cls_accession = [super_cls_accession]
            for sp_accession in super_cls_accession:

                for child, parent, key in self.ms_obo.in_edges(sp_accession, keys=True):
                    if key != 'is_a':
                        continue
                    children.append(child)
            filtered_idx = [i for i, a in enumerate(accessions) if a in children]

        result = {k: v for i, (k, v) in enumerate(element.items()) if i in filtered_idx}

        # hacky fix for https://github.com/levitsky/pyteomics/issues/150
        for k, v in result.items():
            # check if v is list
            if isinstance(v, list):
                # if every value in list is the same
                if all(x == v[0] for x in v):
                    # set the value to the first element
                    result[k] = v[0]

        return result

    # ToDo: refactor gz/zip
    # split into two functions
    @staticmethod
    def extract_mzid(archive):
        """
        Extract the files from the archive.
        :param archive:
        :return:
        """
        if archive.endswith('zip'):
            zip_ref = zipfile.ZipFile(archive, 'r')
            unzip_path = archive + '_unzip/'
            zip_ref.extractall(unzip_path)
            zip_ref.close()

            return_file_list = []

            for root, dir_names, file_names in os.walk(unzip_path):
                file_names = [f for f in file_names if not f[0] == '.']
                dir_names[:] = [d for d in dir_names if not d[0] == '.']
                for file_name in file_names:
                    os.path.join(root, file_name)
                    if file_name.lower().endswith('.mzid'):
                        return_file_list.append(root + '/' + file_name)
                    else:
                        raise IOError('unsupported file type: %s' % file_name)

            # todo - looks like potential problem here?
            if len(return_file_list) > 1:
                raise Exception("more than one mzid file found!")

            return return_file_list[0]

        elif archive.endswith('gz'):
            in_f = gzip.open(archive, 'rb')
            archive = archive.replace(".gz", "")
            out_f = open(archive, 'wb')
            try:
                out_f.write(in_f.read())
            except IOError:
                raise Exception('Zip archive error: %s' % archive)

            in_f.close()
            out_f.close()

            return archive

        else:
            raise Exception('unsupported file type: %s' % archive)


def iterfind_when(source, target_name, condition_name, stack_predicate, **kwargs):
    """
    Iteratively parse XML stream in ``source``, yielding XML elements
    matching ``target_name`` as long as earlier in the tree a ``condition_name`` element
    satisfies ``stack_predicate``, a callable that takes a single :class:`etree.Element` and returns
    a :class:`bool`.

    Parameters
    ----------
    source: file-like
        A file-like object over an XML document
    target_name: str
        The name of the XML tag to parse until
    condition_name: str
        The name to start parsing at when `stack_predicate` evaluates to true on this element.
    stack_predicate: callable
        A function called with a single `etree.Element` that determines if the sub-tree should be parsed
    **kwargs:
        Additional arguments passed to :meth:`source._get_info_smart`

    Yields
    ------
    lxml.etree.Element
    """
    g = etree.iterparse(source, ("start", "end"), remove_comments=True)
    state = False
    history = []
    for event, tag in g:
        lc_name = _local_name(tag)
        if event == "start":
            if lc_name == condition_name:
                state = stack_predicate(tag)
        else:
            if lc_name == target_name and state:
                # noinspection PyProtectedMember
                value = source._get_info_smart(tag, **kwargs)
                for t in history:
                    t.clear()
                history.clear()
                yield value
            elif state:
                history.append(tag)
            elif not state:
                tag.clear()


class SqliteMzIdParser(MzIdParser):

    def write_new_upload(self):
        """Overrides base class function - not needed for xiSPEC."""
        self.writer.upload_id = 1
        try:
            filename = os.path.basename(self.mzid_path)
            upload_data = {
                'identification_file_name': filename,
                'project_id': self.writer.pxid,
                'identification_file_name_clean': re.sub(r'[^0-9a-zA-Z-]+', '-', filename)
            }
            table = 'upload'

            self.writer.write_data(table, upload_data)
        except SQLAlchemyError as e:
            print(f"Error during database insert: {e}")


class XiSpecMzIdParser(MzIdParser):

    def write_new_upload(self):
        """Overrides base class function - not needed for xiSPEC."""
        self.writer.upload_id = 1
        pass

    def upload_info(self):
        """Overrides base class function - not needed for xiSPEC."""
        pass

    # def parse_db_sequences(self):
    #     """Overrides base class function - not needed for xiSPEC."""
    #     pass

    def fill_in_missing_scores(self):
        # Fill missing scores with
        score_fill_start_time = time()
        self.logger.info('fill in missing scores - start')
        self.writer.fill_in_missing_scores()
        self.logger.info('fill in missing scores - done. Time: {}'.format(
            round(time() - score_fill_start_time, 2)))

    def write_other_info(self):
        """Overrides base class function - not needed for xiSPEC."""
        pass
