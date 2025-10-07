""""""

import json
import re
from time import time

from .AbstractCsvParser import AbstractCsvParser, CsvParseException


class FullCsvParser(AbstractCsvParser):

    @property
    def required_cols(self):
        return [
            "pepseq1",
            "peppos1",
            "linkpos1",
            "protein1",
            "pepseq2",
            "peppos2",
            "linkpos2",
            "protein2",
            "peaklistfilename",
            "scanid",
            "charge",
            "crosslinkermodmass",
            # 'expMZ'
        ]

    @property
    def optional_cols(self):
        return [
            # 'spectrum_id' $ ToDo: get rid of this? select alternatives by scanid and peaklistfilename?
            "rank",
            "fragmenttolerance",
            "iontypes",
            "passthreshold",
            "score",
            "decoy1",
            "decoy2",
            "expmz",  # ToDo: required in mzid - also make required col?
            "calcmz",
        ]

    def main_loop(self):
        main_loop_start_time = time()
        self.logger.info("main loop FullCsvParser - start")

        peptide_evidences = []
        spectrum_identifications = []
        spectra = []
        peptides = []
        proteins = set()
        # list of spectra that were already seen - index in list is spectrum_id
        # combination of peaklistfilename and scanid is a unique identifier
        seen_spectra = []

        # list of peptides that were already seen - index in list is peptide_id
        # pep sequence including cross-link site and cross-link mass is unique identifier
        seen_peptides = []

        crosslinker_pair_count = 0

        # # ID VALIDITY CHECK - unique ids
        # if len(self.csv_reader['id'].unique()) < len(self.csv_reader):
        #     duplicate_ids = self.csv_reader[self.csv_reader.duplicated('id', keep=False)].id.tolist()
        #     duplicate_ids = [str(i) for i in duplicate_ids]
        #     raise CsvParseException('Duplicate ids found: %s' % "; ".join(duplicate_ids))

        for identification_id, id_item in self.csv_reader.iterrows():

            # 1 based row number
            row_number = identification_id + 1

            #
            # VALIDITY CHECKS & TYPE CONVERSIONS - ToDo: move type checks/conversions to col level in parse()?
            #
            # rank - ToDo: more elaborate checks?
            try:
                rank = int(id_item["rank"])
            except KeyError:
                rank = 1  # ToDo: create default values in parse()
            except ValueError:
                raise CsvParseException(
                    "Invalid rank: %s for row: %s"
                    % (id_item["rank"], row_number)
                )

            # pepSeq

            # ToDo: reorder peptides by length and alphabetical?
            # add cross-linker always to first peptide?
            # From mzIdentML schema 1.2.0:
            # the cross-link donor SHOULD contain the complete mass delta introduced by the cross-linking reagent,
            # and that the cross-link acceptor reports a mass shift
            # delta of zero. It is RECOMMENDED that the 'donor' peptide SHOULD be the longer peptide, followed by
            # alphabetical order for equal length peptides.

            invalid_char_pattern_pepseq = (
                r"([^GALMFWKQESPVICYHRNDTXa-z:0-9(.)\-]+)"
            )
            # pepSeq - 1
            if id_item["pepseq1"] == "":
                raise CsvParseException(
                    "Missing PepSeq1 for row: %s" % row_number
                )

            invalid_char_match = re.match(
                invalid_char_pattern_pepseq, id_item["pepseq1"]
            )
            if invalid_char_match:
                invalid_chars = "; ".join(invalid_char_match.groups())
                raise CsvParseException(
                    "Invalid character(s) found in PepSeq1: %s for row: %s"
                    % (invalid_chars, row_number)
                )
            pepseq1 = id_item["pepseq1"]
            # pepSeq - 2
            if id_item["pepseq2"] == "":
                crosslinked_id_item = False
            else:
                self.contains_crosslinks = True
                crosslinked_id_item = True
                invalid_char_match = re.match(
                    invalid_char_pattern_pepseq, id_item["pepseq2"]
                )
                if invalid_char_match:
                    invalid_chars = "; ".join(invalid_char_match.groups())
                    raise CsvParseException(
                        "Invalid character(s) found in PepSeq2: %s for row: %s"
                        % (invalid_chars, row_number)
                    )
            pepseq2 = id_item["pepseq2"]

            # LinkPos
            # LinkPos - 1
            try:
                linkpos1 = int(id_item["linkpos1"])
            except ValueError:
                raise CsvParseException(
                    "Invalid LinkPos1: %s for row: %s"
                    % (id_item["linkpos1"], row_number)
                )

            # LinkPos - 2
            try:
                linkpos2 = int(id_item["linkpos2"])
            except ValueError:
                raise CsvParseException(
                    "Invalid LinkPos2: %s for row: %s"
                    % (id_item["linkpos2"], row_number)
                )

            if (linkpos1 == -1 and not linkpos2 == -1) or (
                linkpos1 == -1 and not linkpos2 == -1
            ):
                raise CsvParseException(
                    "Incomplete cross-link site information for row: %s"
                    % row_number
                )

            # CrossLinkerModMass
            try:
                crosslink_mod_mass = float(id_item["crosslinkermodmass"])
            except ValueError:
                raise CsvParseException(
                    "Invalid CrossLinkerModMass: %s for row: %s"
                    % (id_item["crosslinkermodmass"], row_number)
                )

            # charge
            try:
                charge = int(id_item["charge"])
            except ValueError:
                # raise CsvParseException('Invalid charge state: %s for row: %s' % (id_item['charge'], row_number))
                # self.warnings.append("Missing charge state.")
                charge = None

            # passthreshold
            if isinstance(id_item["passthreshold"], bool):
                pass_threshold = id_item["passthreshold"]
            else:
                raise CsvParseException(
                    "Invalid passThreshold value: %s for row: %s"
                    % (id_item["passthreshold"], row_number)
                )

            # fragmenttolerance - ToDo: fix - would beed to write SpectrumIdentificationProtocol for CSV
            # if not re.match('^([0-9.]+) (ppm|Da)$', str(id_item['fragmenttolerance'])):
            #     raise CsvParseException(
            #         'Invalid FragmentTolerance value: %s in row: %s' % (id_item['fragmenttolerance'], row_number))
            # else:
            #     fragment_tolerance = id_item['fragmenttolerance']

            # iontypes
            # ions = id_item['iontypes'].split(';')
            # valid_ions = [
            #     'peptide',
            #     'a',
            #     'b',
            #     'c',
            #     'x',
            #     'y',
            #     'z',
            #     ''  # split will add an empty sell if string ends with ';'
            # ]
            # ToDo: fix - would beed to write SpectrumIdentificationProtocol for CSV
            # if any([True for ion in ions if ion not in valid_ions]):
            #     raise CsvParseException(
            #         'Unsupported IonType in: %s in row %s! Supported ions are: peptide;a;b;c;x;y;z.'
            #         % (id_item['iontypes'], row_number)
            #     )
            # ion_types = id_item['iontypes']

            # score
            try:
                score = float(id_item["score"])
            except ValueError:
                raise CsvParseException(
                    "Invalid score: %s in row %s"
                    % (id_item["score"], row_number)
                )

            # protein1
            protein_list1 = id_item["protein1"].split(";")
            protein_list1 = [s.strip() for s in protein_list1]
            for p in protein_list1:
                proteins.add(p)

            # decoy1 - if decoy1 is not set fill list with default value (0)
            if id_item["decoy1"] == -1:
                is_decoy_list1 = [False] * len(protein_list1)
            else:
                is_decoy_list1 = []
                for decoy in str(id_item["decoy1"]).split(";"):
                    if decoy.lower().strip() == "true":
                        is_decoy_list1.append(True)
                    elif decoy.lower().strip() == "false":
                        is_decoy_list1.append(False)
                    else:
                        raise CsvParseException(
                            "Invalid value in Decoy 1: %s in row %s. Allowed values: True, False."
                            % (id_item["decoy1"], row_number)
                        )

            if len(is_decoy_list1) != len(protein_list1):
                is_decoy_list1 = [is_decoy_list1[0]] * len(protein_list1)

            # pepPos1 - if pepPos1 is not set fill list with default value (-1)
            # ToDo: might need changing for xiUI where pepPos is not optional
            if id_item["peppos1"] == -1:
                pep_pos_list1 = [-1] * len(protein_list1)
            else:
                pep_pos_list1 = str(id_item["peppos1"]).split(";")
                pep_pos_list1 = [s.strip() for s in pep_pos_list1]

            # protein - decoy - pepPos sensibility check
            if not len(protein_list1) == len(is_decoy_list1):
                raise CsvParseException(
                    "Inconsistent number of protein to decoy values for Protein1 and Decoy1 in row %s!"
                    % row_number
                )
            if not len(protein_list1) == len(pep_pos_list1):
                raise CsvParseException(
                    "Inconsistent number of protein to pepPos values for Protein1 and PepPos1 in row %s!"
                    % row_number
                )

            # protein2
            protein_list2 = id_item["protein2"].split(";")
            protein_list2 = [s.strip() for s in protein_list2]
            for p in protein_list2:
                proteins.add(p)

            # decoy2 - if decoy2 is not set fill list with default value (0)
            if id_item["decoy2"] == -1:
                is_decoy_list2 = [False] * len(protein_list2)
            else:
                is_decoy_list2 = []
                for decoy in str(id_item["decoy2"]).split(";"):
                    if decoy.lower().strip() == "true":
                        is_decoy_list2.append(True)
                    elif decoy.lower().strip() == "false":
                        is_decoy_list2.append(False)
                    else:
                        raise CsvParseException(
                            "Invalid value in Decoy 2: %s in row %s. Allowed values: True, False."
                            % (id_item["decoy2"], row_number)
                        )

            if len(is_decoy_list2) != len(protein_list2):
                is_decoy_list2 = [is_decoy_list2[0]] * len(protein_list2)

            # pepPos2 - if pepPos2 is not set fill list with default value (-1)
            # ToDo: might need changing for xiUI where pepPos is not optional
            if id_item["peppos2"] == -1:
                pep_pos_list2 = [-1] * len(protein_list2)
            else:
                pep_pos_list2 = str(id_item["peppos2"]).split(";")
                pep_pos_list2 = [s.strip() for s in pep_pos_list2]

            # protein - decoy - pepPos sensibility check
            if not len(protein_list2) == len(is_decoy_list2):
                raise CsvParseException(
                    "Inconsistent number of protein to decoy values for Protein2 and Decoy2 in row %s!"
                    % row_number
                )
            if not len(protein_list2) == len(pep_pos_list2):
                raise CsvParseException(
                    "Inconsistent number of protein to pepPos values for Protein2 and PepPos2! in row %s!"
                    % row_number
                )

            # scanId
            try:
                scan_id = id_item["scanid"]
            except KeyError:
                scan_id = -1

            # peakListFilename

            # expMZ
            try:
                exp_mz = float(id_item["expmz"])
            except ValueError:
                raise CsvParseException(
                    "Invalid expMZ: %s in row %s"
                    % (id_item["exmpmz"], row_number)
                )
            # calcMZ
            try:
                calc_mz = float(id_item["calcmz"])
            except ValueError:
                raise CsvParseException(
                    "Invalid calcMZ: %s in row %s"
                    % (id_item["calcmz"], row_number)
                )

            #
            # -----Start actual parsing------
            #
            # SPECTRA
            peak_list_file_name = id_item["peaklistfilename"]

            unique_spec_identifier = "%s-%s" % (peak_list_file_name, scan_id)

            if unique_spec_identifier not in seen_spectra:
                seen_spectra.append(unique_spec_identifier)
                spectrum_id = len(seen_spectra) - 1
                if self.peak_list_dir:
                    # get peak list
                    try:
                        peak_list_reader = self.peak_list_readers[
                            peak_list_file_name
                        ]
                    except KeyError:
                        raise CsvParseException(
                            "Missing peak list file: %s" % peak_list_file_name
                        )

                    spectrum = peak_list_reader[scan_id]

                    spectrum = {
                        "id": scan_id,
                        "spectra_data_id": peak_list_file_name,
                        "upload_id": self.writer.upload_id,
                        "peak_list_file_name": peak_list_file_name,
                        "precursor_mz": spectrum.precursor["mz"],
                        "precursor_charge": spectrum.precursor["charge"],
                        "mz": spectrum.mz_values,
                        "intensity": spectrum.int_values,
                    }

                    spectra.append(spectrum)
            else:
                spectrum_id = seen_spectra.index(unique_spec_identifier)

            # PEPTIDES
            if crosslinked_id_item:
                crosslinker_pair_id = crosslinker_pair_count
                crosslinker_pair_count += 1
            else:
                crosslinker_pair_id = -1  # linear ToDo: -1 or None?

            # peptide - 1
            unique_pep_identifier1 = "%s-%s" % (pepseq1, crosslinker_pair_id)

            if unique_pep_identifier1 not in seen_peptides:
                seen_peptides.append(unique_pep_identifier1)
                pep1_id = len(seen_peptides) - 1

                peptide1 = {
                    "id": pep1_id,
                    "upload_id": self.writer.upload_id,
                    "base_sequence": pepseq1,
                    "mod_accessions": [],  # mod_accessions,
                    "mod_positions": [],  # mod_pos,
                    "mod_monoiso_mass_deltas": [],  # mod_masses,
                    "link_site1": linkpos1,
                    "crosslinker_modmass": crosslink_mod_mass,
                    "crosslinker_pair_id": str(crosslinker_pair_id),
                }

                peptides.append(peptide1)
            else:
                pep1_id = seen_peptides.index(unique_pep_identifier1)

            if crosslinked_id_item:
                # peptide - 2
                unique_pep_identifier2 = "%s-%s" % (
                    pepseq2,
                    crosslinker_pair_id,
                )

                if unique_pep_identifier2 not in seen_peptides:
                    seen_peptides.append(unique_pep_identifier2)
                    pep2_id = len(seen_peptides) - 1

                    peptide2 = {
                        "id": pep2_id,
                        "upload_id": self.writer.upload_id,
                        "base_sequence": pepseq2,
                        "mod_accessions": [],  # mod_accessions,
                        "mod_positions": [],  # mod_pos,
                        "mod_monoiso_mass_deltas": [],  # mod_masses,
                        "link_site1": linkpos2,
                        "crosslinker_modmass": 0,
                        "crosslinker_pair_id": str(crosslinker_pair_id),
                    }
                    peptides.append(peptide2)
                else:
                    pep2_id = seen_peptides.index(unique_pep_identifier2)
            else:
                pep2_id = None

            #
            # PEPTIDE EVIDENCES
            # peptide evidence - 1
            for i in range(len(protein_list1)):
                pep_evidence1 = {
                    "upload_id": self.writer.upload_id,
                    "peptide_id": pep1_id,
                    "dbsequence_id": protein_list1[i],
                    "pep_start": pep_pos_list1[i],
                    "is_decoy": is_decoy_list1[i],
                }

                peptide_evidences.append(pep_evidence1)

            if crosslinked_id_item and pep1_id != pep2_id:
                # peptide evidence - 2

                if pep2_id is None:
                    raise Exception("Fatal! peptide id error!")

                for i in range(len(protein_list2)):
                    pep_evidence2 = {
                        "upload_id": self.writer.upload_id,
                        "peptide_id": pep2_id,
                        "dbsequence_id": protein_list2[i],
                        "pep_start": pep_pos_list2[i],
                        "is_decoy": is_decoy_list2[i],
                    }

                    peptide_evidences.append(pep_evidence2)

            #
            # SPECTRUM IDENTIFICATIONS
            #
            scores = json.dumps({"score": score})

            # try:
            #     meta1 = id_item[self.meta_columns[0]]
            # except IndexError:
            #     meta1 = ""
            # try:
            #     meta2 = id_item[self.meta_columns[1]]
            # except IndexError:
            #     meta2 = ""
            # try:
            #     meta3 = id_item[self.meta_columns[2]]
            # except IndexError:
            #     meta3 = ""

            spectrum_identification = {
                "id": identification_id,
                "upload_id": self.writer.upload_id,
                "spectrum_id": spectrum_id,
                # 'spectra_data_ref': peak_list_file_name,
                "pep1_id": pep1_id,
                "pep2_id": pep2_id,
                "charge_state": int(charge),
                "pass_threshold": pass_threshold,
                "rank": int(rank),
                "scores": scores,
                "exp_mz": exp_mz,
                "calc_mz": calc_mz,
                # meta1,
                # meta2,
                # meta3
            }

            spectrum_identifications.append(spectrum_identification)

            #
            # MODIFICATIONS
            # ToDo: check against unimod?

            try:
                modifications = re.findall(
                    "[^A-Z]+", "".join([pepseq1, pepseq2])
                )
            except AttributeError:
                modifications = []

            self.unknown_mods.update(modifications)

        # DBSEQUENCES
        # if self.fasta:
        db_sequences = []
        for prot_id in proteins:
            try:
                db_seq = {
                    "id": prot_id,
                    "upload_id": self.writer.upload_id,
                    "accession": self.fasta[prot_id][0],
                    "name": self.fasta[prot_id][1],
                    "description": self.fasta[prot_id][2],
                    "sequence": self.fasta[prot_id][3],
                }
            except KeyError:
                sp_regex = re.compile(r"(.*)\|(.*)\|(.*)")
                matches = sp_regex.search(prot_id)
                if matches is not None:
                    db_seq = {
                        "id": matches.group(),
                        "upload_id": self.writer.upload_id,
                        "accession": matches.group(2),
                        "name": matches.group(3),
                        "description": "",
                        "sequence": None,
                    }
                else:
                    db_seq = {
                        "id": prot_id,
                        "upload_id": self.writer.upload_id,
                        "accession": prot_id,
                        "name": prot_id,
                        "description": "",
                        "sequence": None,
                    }

            db_sequences.append(db_seq)

        # end main loop
        self.logger.info(
            "main loop - done. Time: "
            + str(round(time() - main_loop_start_time, 2))
            + " sec"
        )

        # once loop is done write data to DB
        db_wrap_up_start_time = time()
        self.logger.info("write spectra to DB - start")
        try:
            self.writer.write_data("dbsequence", db_sequences)
            self.writer.write_data("modifiedpeptide", peptides)
            self.writer.write_data("peptideevidence", peptide_evidences)
            if self.peak_list_dir:
                self.writer.write_data("spectrum", spectra)
            self.writer.write_data("match", spectrum_identifications)
        except Exception as e:
            raise e

        self.logger.info(
            "write spectra to DB - start - done. Time: "
            + str(round(time() - db_wrap_up_start_time, 2))
            + " sec"
        )
