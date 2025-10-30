"""
PeakListWrapper.py
"""

import gzip
import io
import ntpath
import os
import re
import tarfile
import zipfile
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pyteomics import mgf, ms2, mzml


# todo -check error handling
class PeakListParseError(Exception):
    """raised if error reading peaklist, invalid spectrum id or spectrum not found in peaklist file."""

    pass


class SpectrumIdFormatError(Exception):
    """raised if the spectrum id format is not supported by the reader."""

    pass


class ScanNotFoundException(Exception):
    """raised if the scan is not found in the mzML file."""

    pass


class Spectrum:
    """A class to represent a spectrum."""

    def __init__(
        self,
        precursor: dict[str, float],
        mz_array: NDArray[np.float64],
        int_array: NDArray[np.float64],
        rt: float = np.nan,
    ) -> None:
        """Initialise a Spectrum object.

        Args:
            precursor: Spectrum precursor information as dict.
                e.g. {'mz': 102.234, 'charge': 2, 'intensity': 12654.35}
            mz_array: m/z values of the spectrum peaks (ndarray, dtype: float64)
            int_array: Intensity values of the spectrum peaks (ndarray, dtype: float64)
            rt: Retention time in seconds (can be a range, e.g. 60-62)
        """
        self.precursor = precursor
        self.rt = rt
        mz_array = np.asarray(mz_array, dtype=np.float64)
        int_array = np.asarray(int_array, dtype=np.float64)
        # make sure that the m/z values are sorted asc
        sorted_indices = np.argsort(mz_array)
        self.mz_values = mz_array[sorted_indices]
        self.int_values = int_array[sorted_indices]
        self._precursor_mass = None


class PeakListWrapper:
    """A class to wrap peak list files and provide an interface to access the spectra."""

    def __init__(
        self,
        pl_path: str,
        file_format_accession: str,
        spectrum_id_format_accession: str,
    ) -> None:
        self.file_format_accession = file_format_accession
        self.spectrum_id_format_accession = spectrum_id_format_accession
        self.peak_list_path = pl_path
        self.peak_list_file_name = os.path.split(pl_path)[1]

        try:
            # create the reader
            if self.is_mzml():
                self.reader = MZMLReader(spectrum_id_format_accession)
            elif self.is_mgf():
                self.reader = MGFReader(spectrum_id_format_accession)
            elif self.is_ms2():
                self.reader = MS2Reader(spectrum_id_format_accession)
            # load the file
            self.reader.load(pl_path)
        except Exception as e:
            message = "Error reading peak list file {0}: {1} - Arguments:\n{2!r}".format(
                self.peak_list_file_name, type(e).__name__, e.args
            )
            raise PeakListParseError(message)

    def __getitem__(self, spec_id: str) -> Spectrum:
        """Return the spectrum depending on the FileFormat and SpectrumIdFormat."""
        return self.reader[spec_id]

    def is_mgf(self) -> bool:
        """Check if the peak list is in MGF format.

        Returns:
            True if the peak list is in MGF format
        """
        return self.file_format_accession == "MS:1001062"

    def is_mzml(self) -> bool:
        """Check if the peak list is in mzML format.

        Returns:
            True if the peak list is in mzML format
        """
        return self.file_format_accession == "MS:1000584"

    def is_ms2(self) -> bool:
        """Check if the peak list is in MS2 format.

        Returns:
            True if the peak list is in MS2 format
        """
        return self.file_format_accession == "MS:1001466"

    @staticmethod
    def extract_gz(in_file: str) -> str:
        """Extract gzipped file.

        Args:
            in_file: Path to gzipped file

        Returns:
            Path to extracted file
        """
        if in_file.endswith(".gz"):
            in_f = gzip.open(in_file, "rb")
            in_file = in_file.replace(".gz", "")
            out_f = open(in_file, "wb")
            out_f.write(in_f.read())
            in_f.close()
            out_f.close()

            return in_file

        else:
            raise Exception(f"unsupported file extension for: {in_file}")

    @staticmethod
    def unzip_peak_lists(zip_file: str, out_path: str = ".") -> str:
        """Unzip and return resulting folder.

        Args:
            zip_file: Path to archive to unzip
            out_path: Where to extract the files

        Returns:
            Path to resulting folder
        """
        if zip_file.endswith(".zip"):
            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                unzip_path = os.path.join(
                    str(out_path), f"{ntpath.basename(zip_file)}_unzip"
                )
                os.makedirs(unzip_path, exist_ok=True)
                base = os.path.abspath(unzip_path) + os.sep
                for member in zip_ref.infolist():
                    dest = os.path.abspath(
                        os.path.join(unzip_path, member.filename)
                    )
                    if not dest.startswith(base):
                        raise Exception(
                            f"Illegal path in zip: {member.filename}"
                        )
                    zip_ref.extract(member, unzip_path)
            return unzip_path

        else:
            raise Exception(f"unsupported file extension for: {zip_file}")


class SpectraReader(ABC):
    """Abstract Base Class for all SpectraReader."""

    def __init__(self, spectrum_id_format_accession: str) -> None:
        """Initialize the SpectraReader.

        Args:
            spectrum_id_format_accession: Spectrum ID format accession
        """
        self._reader = None
        self.spectrum_id_format_accession = spectrum_id_format_accession
        self._source = None
        self.file_name = None
        self.source_path = None

    @abstractmethod
    def load(
        self,
        source: str | io.TextIOBase,
        file_name: str | None = None,
        source_path: str | None = None,
    ) -> None:
        """Load the spectrum file.

        Args:
            source: Spectra file source
            file_name: Filename
            source_path: Path to the source file (peak list file or archive)
        """
        self._source = source
        if source_path is None:
            if isinstance(source, str):
                self.source_path = source
            elif issubclass(type(source), io.TextIOBase) or issubclass(
                type(source), tarfile.ExFileObject
            ):
                self.source_path = source.name
        else:
            self.source_path = source_path

        if file_name is None:
            self.file_name = ntpath.basename(self.source_path)
        else:
            self.file_name = file_name

    @abstractmethod
    def __getitem__(self, spec_id: str | int) -> Spectrum:
        """Return the spectrum depending on the SpectrumIdFormat."""
        ...

    @abstractmethod
    def _convert_spectrum(self, spec: dict[str, Any]) -> Spectrum:
        """Convert the spectrum from the reader to a Spectrum object."""
        ...


class MGFReader(SpectraReader):
    """SpectraReader for MGF files."""

    def __getitem__(self, spec_id: str | int) -> Spectrum:
        """Return the spectrum depending on the SpectrumIdFormat.

        Args:
            spec_id: Spectrum identifier

        Returns:
            Spectrum object
        """
        # MS:1000774 multiple peak list nativeID format - zero based
        # index=xsd:nonNegativeInteger
        if self.spectrum_id_format_accession == "MS:1000774":
            try:
                matches = re.match("index=([0-9]+)", spec_id).groups()
                spec_id = int(matches[0])

            # try to cast spec_id to int if re doesn't match -> PXD006767 has this format
            # ToDo: do we want to be stricter?
            except (TypeError, AttributeError, IndexError):
                try:
                    spec_id = int(spec_id)
                except ValueError:
                    raise PeakListParseError("invalid spectrum ID format!")
            # noinspection PyUnresolvedReferences
            spec = self._reader[spec_id]

        # MS:1000775 single peak list nativeID format
        # The nativeID must be the same as the source file ID.
        # Used for referencing peak list files with one spectrum per file,
        # typically in a folder of PKL or DTAs, where each sourceFileRef is different.
        elif self.spectrum_id_format_accession == "MS:1000775":
            spec_id = 0
            # noinspection PyUnresolvedReferences
            spec = self._reader[spec_id]

        # # MS:1000768 Thermo nativeID format: ToDo: not supported for now.
        # # controllerType=xsd:nonNegativeInt controllerNumber=xsd:positiveInt scan=xsd:positiveInt
        # if self.spectrum_id_format_accession == 'MS:1000768':
        #     raise SpectrumIdFormatError(
        #         "Combination of spectrumIdFormat and FileFormat not supported.")

        else:
            raise SpectrumIdFormatError(
                f"{self.spectrum_id_format_accession} not supported for MGF"
            )

        return self._convert_spectrum(spec)

    def load(
        self,
        source: str | io.TextIOBase,
        file_name: str | None = None,
        source_path: str | None = None,
    ) -> None:
        """Load MGF file.

        Args:
            source: File source, path or stream
            file_name: MGF filename
            source_path: Path to the source file (MGF or archive)
        """
        self._reader = mgf.read(source, use_index=True)
        super().load(source, file_name, source_path)

    def _convert_spectrum(self, spec: dict[str, Any]) -> Spectrum:
        """Convert the spectrum from the reader to a Spectrum object."""
        precursor = {
            "mz": spec["params"]["pepmass"][0],
            "charge": spec["params"]["charge"][0],
            "intensity": spec["params"]["pepmass"][1],
        }

        # parse retention time, default to NaN
        rt = spec["params"].get("rtinseconds", np.nan)

        return Spectrum(
            precursor, spec["m/z array"], spec["intensity array"], rt
        )


class MZMLReader(SpectraReader):
    """SpectraReader for mzML files."""

    def __init__(self, spectrum_id_format_accession: str) -> None:
        super().__init__(spectrum_id_format_accession)

    def __getitem__(self, spec_id: str) -> Spectrum:
        """Return the spectrum depending on the SpectrumIdFormat.

        Args:
            spec_id: Spectrum identifier

        Returns:
            Spectrum object
        """
        # MS:1001530 mzML unique identifier:
        # Used for referencing mzML. The value of the spectrum ID attribute is referenced directly.
        if self.spectrum_id_format_accession == "MS:1001530":
            spec = self._reader.get_by_id(spec_id)

        # ToDo: not supported for now.
        # # MS:1000768 Thermo nativeID format:
        # # controllerType=xsd:nonNegativeInt controllerNumber=xsd:positiveInt scan=xsd:positiveInt
        # elif self.spectrum_id_format_accession == 'MS:1000768':
        #     raise SpectrumIdFormatError(
        #         "Combination of spectrumIdFormat and FileFormat not supported.")
        #
        # # MS:1000774 multiple peak list nativeID format - zero based
        # elif self.spectrum_id_format_accession == 'MS:1000774':
        #     raise SpectrumIdFormatError(
        #         "Combination of spectrumIdFormat and FileFormat not supported.")
        #
        # # MS:1000775 single peak list nativeID format
        # # The nativeID must be the same as the source file ID.
        # # Used for referencing peak list files with one spectrum per file,
        # # typically in a folder of PKL or DTAs, where each sourceFileRef is different.
        # elif self.spectrum_id_format_accession == 'MS:1000775':
        #     raise SpectrumIdFormatError(
        #         "Combination of spectrumIdFormat and FileFormat not supported.")

        else:
            raise SpectrumIdFormatError(
                f"{self.spectrum_id_format_accession} not supported for mzML!"
            )

        return self._convert_spectrum(spec)

    def load(
        self,
        source: str | io.TextIOBase,
        file_name: str | None = None,
        source_path: str | None = None,
    ) -> None:
        """Read in spectra from an mzML file and stores them as Spectrum objects.

        Args:
            source: File source, path or stream
            file_name: mzML filename
            source_path: Path to the source file (mzML or archive)
        """

        self._reader = mzml.read(source, use_index=True, huge_tree=True)
        super().load(source, file_name, source_path)

    def reset(self) -> None:
        """Reset the reader."""
        if issubclass(type(self._source), tarfile.ExFileObject) or issubclass(
            type(self._source), zipfile.ZipExtFile
        ):
            self._source.seek(0)
            self._reader = mzml.read(self._source)
        else:
            self._reader.reset()

    def _convert_spectrum(self, spec: dict[str, Any]) -> Spectrum:

        # check for single scan per spectrum
        if spec["scanList"]["count"] != 1:
            raise ValueError(
                "xiSEARCH2 currently only supports a single scan per spectrum."
            )
        scan = spec["scanList"]["scan"][0]

        # check for single precursor per spectrum
        if (
            spec["precursorList"]["count"] != 1
            or spec["precursorList"]["precursor"][0]["selectedIonList"][
                "count"
            ]
            != 1
        ):
            raise ValueError(
                "Currently only a single precursor per spectrum is supported."
            )
        p = spec["precursorList"]["precursor"][0]["selectedIonList"][
            "selectedIon"
        ][0]

        # create precursor dict
        precursor = {
            "mz": p["selected ion m/z"],
            "charge": p.get("charge state", np.nan),
            "intensity": p.get("peak intensity", np.nan),
        }

        # parse retention time, default to NaN
        rt = scan.get("scan start time", np.nan)
        rt = rt * 60

        return Spectrum(
            precursor, spec["m/z array"], spec["intensity array"], rt
        )


class MS2Reader(SpectraReader):
    """SpectraReader for MS2 files."""

    def __getitem__(self, spec_id: str | int) -> Spectrum:
        """Return the spectrum depending on the SpectrumIdFormat."""
        # MS:1000774 multiple peak list nativeID format - zero based
        if self.spectrum_id_format_accession == "MS:1000774":
            try:
                matches = re.match("index=([0-9]+)", spec_id).groups()
                spec_id = int(matches[0])

            # try to cast spec_id to int if re doesn't match -> PXD006767 has this format
            # ToDo: do we want to be stricter?
            except (AttributeError, IndexError):
                try:
                    spec_id = int(spec_id)
                except ValueError:
                    raise PeakListParseError("invalid spectrum ID format!")

        # MS:1000775 single peak list nativeID format
        # The nativeID must be the same as the source file ID.
        # Used for referencing peak list files with one spectrum per file,
        # typically in a folder of PKL or DTAs, where each sourceFileRef is different.
        elif self.spectrum_id_format_accession == "MS:1000775":
            spec_id = 0

        # ToDo: not supported for now.
        # # MS:1000768 Thermo nativeID format:
        # # controllerType=xsd:nonNegativeInt controllerNumber=xsd:positiveInt scan=xsd:positiveInt
        # if self.spectrum_id_format_accession == 'MS:1000768':
        #     raise SpectrumIdFormatError(
        #         "Combination of spectrumIdFormat and FileFormat not supported.")

        else:
            raise SpectrumIdFormatError(
                f"{self.spectrum_id_format_accession} not supported for MS2"
            )

        try:
            spec = self._reader[spec_id]
        except IndexError:
            raise PeakListParseError(f"Spectrum with id {spec_id} not found!")
        return self._convert_spectrum(spec)

    def load(
        self,
        source: str | io.TextIOBase,
        file_name: str | None = None,
        source_path: str | None = None,
    ) -> None:
        """Load MS2 file.

        Args:
            source: File source, path or stream
            file_name: MS2 filename
            source_path: Path to the source file (MS2 or archive)
        """
        self._reader = MyMS2(source)
        super().load(source, file_name, source_path)

    def _convert_spectrum(self, spec: dict[str, Any]) -> Spectrum:
        """Convert spectrum to Spectrum object.

        Args:
            spec: Spectrum dictionary

        Returns:
            Spectrum object
        """
        if "PrecursorInt" in spec["params"]:
            precursor = {
                "mz": spec["params"]["precursor m/z"],
                "charge": spec["params"]["charge"][0],
                "intensity": spec["params"]["PrecursorInt"],
            }
        else:
            precursor = {
                "mz": spec["params"]["precursor m/z"],
                "charge": spec["params"]["charge"][0],
            }

        # parse retention time, default to NaN
        rt = spec["params"].get("RetTime", np.nan)
        rt = float(rt) * 60

        return Spectrum(
            precursor, spec["m/z array"], spec["intensity array"], rt
        )


class MyMS2(ms2.IndexedMS2):
    label = r"S\s+(.*\S)"
