from parser.csv_parser.FullCsvParser import FullCsvParser


class XiSpecCsvParser(FullCsvParser):

    @property
    def required_cols(self):
        return [
            "scanid",
            "charge",
            "pepseq1",
            "protein1",
            "peaklistfilename",
            # 'expMZ'
        ]

    @property
    def optional_cols(self):
        return [
            "rank",
            "fragmenttolerance",
            "iontypes",
            "pepseq2",
            "linkpos1",
            "linkpos2",
            "crosslinkermodmass",
            "passthreshold",
            "score",
            "decoy1",
            "decoy2",
            "protein2",
            "peppos1",
            "peppos2",
            "expmz",  # ToDo: required in mzid - also make required col?
            "calcmz",
        ]

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
        "peppos1": -1,
        "peppos2": -1,
        "expmz": -1,  # ToDo: required in mzid - also make required col?
        "calcmz": -1,
    }

    def upload_info(self):
        pass

    def parse_db_sequences(self):
        pass
