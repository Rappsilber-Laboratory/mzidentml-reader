"""Abstract class for csv parsers."""

import abc
import os
from parser import SimpleFASTA
from parser.peaklistReader.PeakListWrapper import PeakListWrapper
from time import time

import numpy as np
import pandas as pd
from sqlalchemy import Table


class CsvParseException(Exception):
    """
    Exception raised for errors parsing the csv file.
    """

    pass


class MissingFileException(Exception):
    """
    Exception raised for missing files.
    todo - reuse other exception?
    """

    pass


class AbstractCsvParser(abc.ABC):
    """
    Abstract class for csv parsers.
    """

    @property
    @abc.abstractmethod
    def required_cols(self):
        """
        Get required column names in csv file.
        :return: list of strings
        """
        pass

    @property
    @abc.abstractmethod
    def optional_cols(self):
        """
        Get optional column names in csv file.
        :return: list of strings
        """
        pass

    default_values = {
        "rank": 1,
        "pepseq1": "",
        "pepseq2": "",
        "linkpos1": -1,
        "linkpos2": -1,
        "crosslinkermodmass": 0,
        "passthreshold": True,
        "fragmenttolerance": "10 ppm",
        "iontypes": "peptide;b;y",
        "score": 0,
        "decoy1": -1,
        "decoy2": -1,
        "protein2": "",
        "peppos2": -1,
        "expmz": -1,  # ToDo: required in mzid - also make required col?
        "calcmz": -1,
    }

    def __init__(self, csv_path, temp_dir, peak_list_dir, writer, logger):
        """
        :param csv_path: path to csv file
        :param temp_dir: path to temp dir
        :param peak_list_dir: path to peak list dir
        :param writer: writer object
        :param logger: logger object
        """
        self.csv_path = csv_path
        self.peak_list_readers = (
            {}
        )  # peak list readers indexed by spectraData_ref

        self.temp_dir = temp_dir
        if not self.temp_dir.endswith("/"):
            self.temp_dir += "/"
        self.peak_list_dir = peak_list_dir
        if peak_list_dir and not peak_list_dir.endswith("/"):
            self.peak_list_dir += "/"

        self.writer = writer
        self.logger = logger

        # self.spectra_data_protocol_map = {}
        # ToDo: Might change to pyteomics unimod obo module
        # ToDo: check self.modlist against unimod?
        self.unimod_path = "obo/unimod.obo"
        self.modlist = []
        self.unknown_mods = set()

        self.contains_crosslinks = False
        self.fasta = False
        self.random_id = 0

        self.warnings = []
        self.write_new_upload()

        # connect to DB

        self.logger.info("reading csv - start")
        self.start_time = time()
        # schema: https://raw.githubusercontent.com/HUPO-PSI/mzIdentML/master/schema/mzIdentML1.2.0.xsd
        self.csv_reader = pd.read_csv(self.csv_path)

        # check for duplicate columns
        col_list = self.csv_reader.columns.tolist()
        duplicate_cols = set([x for x in col_list if col_list.count(x) > 1])
        if len(duplicate_cols) > 0:
            raise CsvParseException(
                "duplicate column(s): %s" % "; ".join(duplicate_cols)
            )

        self.csv_reader.columns = [
            x.lower().replace(" ", "") for x in self.csv_reader.columns
        ]
        self.meta_columns = [
            col for col in self.csv_reader.columns if col.startswith("meta")
        ][:3]

        # remove unused columns
        for col in self.csv_reader.columns:
            if (
                col
                not in self.required_cols
                + self.optional_cols
                + self.meta_columns
            ):
                try:
                    del self.csv_reader[col]
                except KeyError:
                    pass

        # check required cols
        # for required_col in self.required_cols:
        #     if required_col not in self.csv_reader.columns:
        #         raise CsvParseException("Required csv column %s missing" % required_col)

        # create missing non-required cols and fill with NaN (will then be fill with default values)
        for optional_col in self.optional_cols:
            if optional_col not in self.csv_reader.columns:
                self.csv_reader[optional_col] = np.nan

        self.csv_reader.fillna(value=self.default_values, inplace=True)

        # self.csv_reader.fillna('Null', inplace=True)

    def check_required_columns(self):
        """
        Check if all required columns are present in the csv file.
        todo - return type / raising exception is not consistent
        :return: bool
        :raises CsvParseException: if a required column is missing
        """
        for required_col in self.required_cols:
            if required_col not in self.csv_reader.columns:
                raise CsvParseException(
                    "Required csv column %s missing" % required_col
                )
        return True

    def get_missing_required_columns(self):
        """
        Get missing required columns in the csv file.
        :return: list of strings
        """
        missing_cols = []
        for required_col in self.required_cols:
            if required_col not in self.csv_reader.columns:
                missing_cols.append(required_col)
        return missing_cols

    # ToDo: not used atm - can be used for checking if all files are present in temp dir
    def get_peak_list_file_names(self):
        """
        :return: list of all used peak list file names
        """
        return self.csv_reader.peaklistfilename.unique()

    def get_sequence_db_file_names(self):
        """
        :return: list of all used sequence db file names
        """
        fasta_files = []
        for file in os.listdir(self.temp_dir):
            if file.endswith(".fasta") or file.endswith(".FASTA"):
                fasta_files.append(self.temp_dir + "/" + file)
        return fasta_files

    def set_peak_list_readers(self):
        """
        sets self.peak_list_readers
        dictionary:
            key: peak list file name
            value: associated peak list reader
        """

        peak_list_readers = {}
        for peak_list_file_name in self.csv_reader.peaklistfilename.unique():

            # ToDo: what about .ms2?
            if peak_list_file_name.lower().endswith(".mgf"):
                file_format_accession = "MS:1001062"  # MGF
                spectrum_id_format_accesion = "MS:1000774"  # MS:1000774 multiple peak list nativeID format - zero based

            elif peak_list_file_name.lower().endswith(".mzml"):
                file_format_accession = "MS:1000584"  # mzML
                spectrum_id_format_accesion = (
                    "MS:1001530"  # mzML unique identifier
                )
            else:
                raise CsvParseException(
                    "Unsupported peak list file type for: %s"
                    % peak_list_file_name
                )

            peak_list_file_path = self.peak_list_dir + peak_list_file_name

            try:
                peak_list_reader = PeakListWrapper(
                    peak_list_file_path,
                    file_format_accession,
                    spectrum_id_format_accesion,
                )
            except IOError:
                # try gz version
                try:
                    peak_list_reader = PeakListWrapper(
                        PeakListWrapper.extract_gz(
                            peak_list_file_path + ".gz"
                        ),
                        file_format_accession,
                        spectrum_id_format_accesion,
                    )
                except IOError:
                    # ToDo: output all missing files not just first encountered. Use get_peak_list_file_names()?
                    raise CsvParseException(
                        "Missing peak list file: %s" % peak_list_file_name
                    )

            peak_list_readers[peak_list_file_name] = peak_list_reader

        self.peak_list_readers = peak_list_readers

    def parse(self):
        """
        Parse csv file.
        """
        start_time = time()

        # ToDo: more gracefully handle missing files
        if self.peak_list_dir:
            self.set_peak_list_readers()

        self.upload_info()  # overridden (empty function) in xiSPEC subclass
        self.parse_db_sequences()  # overridden (empty function) in xiSPEC subclass
        self.main_loop()

        # meta_col_names = [col.replace("meta_", "") for col in self.meta_columns]
        # while len(meta_col_names) < 3:
        #     meta_col_names.append(-1)
        # meta_data = [self.writer.upload_id] + meta_col_names + [self.contains_crosslinks]
        # # ToDo: need to create MetaData
        # # self.writer.write_data('MetaData', meta_data)

        self.logger.info(
            "all done! Total time: "
            + str(round(time() - start_time, 2))
            + " sec"
        )

    @abc.abstractmethod
    def main_loop(self):
        """
        Main loop for parsing the csv.
        """
        pass

    # @staticmethod
    # def get_unimod_masses(unimod_path):
    #     masses = {}
    #     mod_id = -1
    #
    #     with open(unimod_path) as f:
    #         for line in f:
    #             if line.startswith('id: '):
    #                 mod_id = ''.join(line.replace('id: ', '').split())
    #
    #             elif line.startswith('xref: delta_mono_mass ') and not mod_id == -1:
    #                 mass = float(line.replace('xref: delta_mono_mass ', '').replace('"', ''))
    #                 masses[mod_id] = mass
    #
    #     return masses

    def parse_db_sequences(self):
        """
        Parse db sequences.
        """
        self.logger.info("reading fasta - start")
        self.start_time = time()
        self.fasta = SimpleFASTA.get_db_sequence_dict(
            self.get_sequence_db_file_names()
        )
        self.logger.info(
            "reading fasta - done. Time: "
            + str(round(time() - self.start_time, 2))
            + " sec"
        )

    def upload_info(self):
        """
        Write new upload to database.
        """
        self.logger.info("new csv upload")
        # # ident_file_size = os.path.getsize(self.csv_path)
        # # peak_list_file_names = json.dumps(self.get_peak_list_file_names(), cls=NumpyEncoder)
        # self.upload_id = self.db.new_upload([self.user_id, os.path.basename(self.csv_path), "-"],
        #                                     self.cur, self.con,
        #                                     )
        # self.random_id = self.db.get_random_id(self.upload_id, self.cur, self.con)

        # self.writer.write_mzid_info(spectra_formats, provider, audits, samples, bib_refs)

    def write_new_upload(self):
        """Write new upload todatabase.
        :raises Exception: if there is an error writing to the database.
        """
        upload_data = {
            # 'id': self.writer.upload_id,
            # 'user_id': self.writer.user_id,
            "identification_file_name": os.path.basename(self.csv_path),
        }
        # self.writer.write_data('Upload', upload_data)
        table = Table(
            "upload",
            self.writer.meta,
            autoload_with=self.writer.engine,
            quote=False,
        )
        with self.writer.engine.connect() as conn:
            # noinspection PyBroadException
            try:
                statement = (
                    table.insert()
                    .values(upload_data)
                    .returning(table.columns[0])
                )  # RETURNING id AS upload_id
                result = conn.execute(statement)
                self.writer.upload_id = result.fetchall()[0][0]
                conn.commit()
                conn.close()
            except Exception:
                # it's SQLite
                upload_data["id"] = 1
                statement = table.insert().values(upload_data)
                conn.execute(statement)
                self.writer.upload_id = upload_data["id"]
                conn.commit()
                conn.close()


# class NumpyEncoder(json.JSONEncoder):
#     def default(self, obj):
#         if isinstance(obj, np.ndarray):
#             return obj.tolist()
#         return json.JSONEncoder.default(self, obj)
