import json
import re
from time import time

from .AbstractCsvParser import AbstractCsvParser, CsvParseException


class LinksOnlyCsvParser(AbstractCsvParser):

    @property
    def required_cols(self):
        return [
            "abspos1",
            "protein1",
            "abspos2",
            "protein2",
        ]

    @property
    def optional_cols(self):
        return [
            "passthreshold",
            "score",
            "decoy1",
            "decoy2",
        ]

    # noinspection PyUnboundLocalVariable
    def main_loop(self):
        main_loop_start_time = time()
        self.logger.info("main loop LinksOnlyCsvParser - start")

        peptide_evidences = []
        spectrum_identifications = []
        peptides = []

        proteins = set()

        # list of peptides that were already seen - index in list is peptide_id
        # pep sequence including cross-link site and cross-link mass is unique identifier
        seen_peptides = []

        crosslinker_pair_count = 0

        for identification_id, id_item in self.csv_reader.iterrows():

            # 1 based row number
            row_number = identification_id + 1

            #
            # VALIDITY CHECKS & TYPE CONVERSIONS - ToDo: move type checks/conversions to col level in parse()?
            #
            if id_item["protein2"] == "":
                crosslinked_id_item = False
            else:
                self.contains_crosslinks = True
                crosslinked_id_item = True

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

            # absPos1
            abs_pos_list1 = str(id_item["abspos1"]).split(";")
            abs_pos_list1 = [s.strip().replace("'", "") for s in abs_pos_list1]

            # protein - decoy - pepPos sensibility check
            if not len(protein_list1) == len(is_decoy_list1):
                raise CsvParseException(
                    "Inconsistent number of protein to decoy values for Protein1 and Decoy1 in row %s!"
                    % row_number
                )
            if not len(protein_list1) == len(abs_pos_list1):
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

            # pepPos2 - if pepPos2 is not set fill list with default value (-1)
            # ToDo: might need changing for xiUI where pepPos is not optional
            self.logger.info(id_item["abspos2"])
            abs2 = id_item["abspos2"]
            if abs2 == -1:  # or math.isnan(abs2): # todo - check
                abs_pos_list2 = [-1] * len(
                    protein_list2
                )  # todo - check, should maybe set it to none instead of -1
            else:
                abs_pos_list2 = str(id_item["abspos2"]).split(";")
                abs_pos_list2 = [
                    s.strip().replace("'", "") for s in abs_pos_list2
                ]

            # protein - decoy - pepPos sensibility check
            if not len(protein_list2) == len(is_decoy_list2):
                raise CsvParseException(
                    "Inconsistent number of protein to decoy values for Protein2 and Decoy2 in row %s!"
                    % row_number
                )

            #
            # -----Start actual parsing------
            #
            if crosslinked_id_item:
                crosslinker_pair_id = crosslinker_pair_count
                crosslinker_pair_count += 1
            else:
                crosslinker_pair_id = -1  # linear ToDo: -1 or None?

            #
            # PEPTIDE EVIDENCES
            # peptide evidence - 1
            for i in range(len(protein_list1)):

                # peptide - 1
                unique_pep_identifier1 = "%s-%s" % (1, crosslinker_pair_id)

                if unique_pep_identifier1 not in seen_peptides:
                    seen_peptides.append(unique_pep_identifier1)
                    pep1_id = len(seen_peptides) - 1
                    peptide1 = {
                        "id": pep1_id,
                        "upload_id": self.writer.upload_id,
                        "base_sequence": "",
                        "mod_accessions": [],  # mod_accessions,
                        "mod_positions": [],  # mod_pos,
                        "mod_monoiso_mass_deltas": [],  # mod_masses,
                        "link_site1": 1,
                        # 'crosslinker_modmass': crosslink_mod_mass,
                        "crosslinker_pair_id": str(crosslinker_pair_id),
                    }
                    peptides.append(peptide1)
                else:
                    pep1_id = seen_peptides.index(unique_pep_identifier1)

                if crosslinked_id_item:
                    # peptide - 2
                    unique_pep_identifier2 = "%s-%s" % (2, crosslinker_pair_id)

                    if unique_pep_identifier2 not in seen_peptides:
                        seen_peptides.append(unique_pep_identifier2)
                        pep2_id = len(seen_peptides) - 1
                        peptide2 = {
                            "id": pep2_id,
                            "upload_id": self.writer.upload_id,
                            "base_sequence": "",
                            "mod_accessions": [],  # mod_accessions,
                            "mod_positions": [],  # mod_pos,
                            "mod_monoiso_mass_deltas": [],  # mod_masses,
                            "link_site1": 1,
                            "crosslinker_modmass": 0,
                            "crosslinker_pair_id": str(crosslinker_pair_id),
                        }
                        peptides.append(peptide2)
                    else:
                        pep2_id = seen_peptides.index(unique_pep_identifier2)
                else:
                    pep2_id = None

                # m = re.search(r'..\|(.*)\|(.*)\s?', protein_list1[i])
                # ToDO: fix?
                # accession = protein_list1[i]
                # if m:
                #     accession = m.groups()[0]
                pep_evidence1 = {
                    "upload_id": self.writer.upload_id,
                    "peptide_ref": pep1_id,
                    "dbsequence_ref": protein_list1[i],
                    "pep_start": int(float(abs_pos_list1[i])),
                    "is_decoy": is_decoy_list1[i],
                }

                peptide_evidences.append(pep_evidence1)

            if crosslinked_id_item and pep1_id != pep2_id:
                # peptide evidence - 2

                if pep2_id is None:
                    raise Exception("Fatal! peptide id error!")

                for i in range(len(protein_list2)):
                    # m = re.search(r'..\|(.*)\|(.*)\s?', protein_list2[i])
                    # ToDo: fix?
                    # accession = protein_list2[i]
                    # if m:
                    #     accession = m.groups()[0]

                    pep_evidence2 = {
                        "upload_id": self.writer.upload_id,
                        "peptide_ref": pep2_id,
                        "dbsequence_ref": protein_list2[i],
                        "pep_start": int(float(abs_pos_list2[i])),
                        "is_decoy": is_decoy_list2[i],
                    }

                    peptide_evidences.append(pep_evidence2)

            #
            # SPECTRUM IDENTIFICATIONS
            #
            scores = json.dumps({"score": score})

            spectrum_identification = {
                "id": identification_id,
                "upload_id": self.writer.upload_id,
                "pep1_id": pep1_id,
                "pep2_id": pep2_id,
                "pass_threshold": True,
                "rank": 1,
                "scores": scores,
            }

            spectrum_identifications.append(spectrum_identification)

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

        # for prot in proteins:
        #     try:
        #         # data = [prot] + self.fasta[prot] + [self.upload_id]
        #         temp = self.fasta[prot]
        #         data = [prot, temp[0], temp[1], temp[2], temp[3], self.writer.upload_id]  # surely there's better way
        #     except Exception as ke:
        #         sp_regex = re.compile('(.*)\|(.*)\|(.*)')
        #         matches = sp_regex.search(prot)
        #         if matches is not None:
        #             data = [matches.group(), matches.group(2), matches.group(3), "", None, self.writer.upload_id]
        #         else:
        #             data = [prot, prot, prot, "", None, self.writer.upload_id]
        #
        #     db_sequences.append(data)

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
            self.writer.write_data("match", spectrum_identifications)
        except Exception as e:
            raise e

        self.logger.info(
            "write spectra to DB - start - done. Time: "
            + str(round(time() - db_wrap_up_start_time, 2))
            + " sec"
        )
