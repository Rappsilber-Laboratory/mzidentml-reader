from parser.csv_parser.FullCsvParser import FullCsvParser


class NoPeakListsCsvParser(FullCsvParser):

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
        ]

    @property
    def optional_cols(self):
        return [
            "scanid",
            "charge",
            "peaklistfilename",
            "rank",
            "fragmenttolerance",
            "iontypes",
            "crosslinkermodmass",
            "passthreshold",
            "score",
            "decoy1",
            "decoy2",
            "expmz",
            "calcmz",
        ]
