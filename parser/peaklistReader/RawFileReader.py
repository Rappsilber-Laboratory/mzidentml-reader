"""
RawFileReader.py

SpectraReader subclass for Thermo .raw files. Converts to mzML using
ThermoRawFileParser CLI, then reads spectra with pyteomics.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from parser.peaklistReader.PeakListWrapper import (
    PeakListParseError,
    SpectraReader,
    Spectrum,
    SpectrumIdFormatError,
)
from typing import Any

import numpy as np
from pyteomics import mzml

logger = logging.getLogger(__name__)

_THERMO_ENV_VAR = "THERMO_RAW_FILE_PARSER_PATH"
_THERMO_GITHUB = "https://github.com/compomics/ThermoRawFileParser"


class ThermoRawFileParserNotFoundError(Exception):
    """Raised when ThermoRawFileParser cannot be found."""

    pass


def find_thermorawfileparser() -> str:
    """Locate the ThermoRawFileParser executable.

    Search order:
    1. THERMO_RAW_FILE_PARSER_PATH environment variable
    2. ThermoRawFileParser on PATH
    3. ThermoRawFileParser.sh on PATH (Linux wrapper)

    Returns:
        Path to the executable.

    Raises:
        ThermoRawFileParserNotFoundError: If not found anywhere.
    """
    env_path = os.environ.get(_THERMO_ENV_VAR)
    if env_path:
        if os.path.isfile(env_path) and os.access(env_path, os.X_OK):
            return env_path
        raise ThermoRawFileParserNotFoundError(
            f"ThermoRawFileParser not found at "
            f"{_THERMO_ENV_VAR}={env_path!r}. "
            "Please check that the path is correct and the file is "
            "executable."
        )

    for name in ("ThermoRawFileParser", "ThermoRawFileParser.sh"):
        path = shutil.which(name)
        if path:
            return path

    raise ThermoRawFileParserNotFoundError(
        "ThermoRawFileParser not found. Set the "
        f"{_THERMO_ENV_VAR} environment variable to the executable path, "
        "or install it and ensure it is on PATH. "
        f"See {_THERMO_GITHUB} for installation instructions."
    )


class RawFileReader(SpectraReader):
    """SpectraReader for Thermo .raw files.

    Converts to mzML using ThermoRawFileParser, then reads with pyteomics.
    Requires spectrum_id_format_accession == MS:1000768 (Thermo nativeID).
    """

    def __init__(self, spectrum_id_format_accession: str) -> None:
        super().__init__(spectrum_id_format_accession)
        self._temp_dir: str | None = None

    def load(
        self,
        source: str,
        file_name: str | None = None,
        source_path: str | None = None,
    ) -> None:
        """Convert .raw to mzML and open with pyteomics.

        Args:
            source: Path to the .raw file (must be a file path, not a stream).
            file_name: Filename override.
            source_path: Source path override.

        Raises:
            SpectrumIdFormatError: If spectrum_id_format_accession is not
                MS:1000768.
            PeakListParseError: If conversion fails or output is missing.
        """
        if self.spectrum_id_format_accession != "MS:1000768":
            raise SpectrumIdFormatError(
                f"{self.spectrum_id_format_accession} not supported for "
                "Thermo RAW files; expected MS:1000768"
            )

        super().load(source, file_name, source_path)

        raw_path = source if isinstance(source, str) else source.name
        exe = find_thermorawfileparser()
        self._temp_dir = tempfile.mkdtemp(prefix="rawfilereader_")

        try:
            result = subprocess.run(
                [exe, "-i", raw_path, "-f", "2", "-o", self._temp_dir],
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            self._cleanup()
            raise PeakListParseError(
                f"ThermoRawFileParser timed out after 600 s "
                f"converting {raw_path}"
            )

        if result.returncode != 0:
            self._cleanup()
            raise PeakListParseError(
                f"ThermoRawFileParser failed (exit {result.returncode}) "
                f"converting {raw_path}.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

        basename = os.path.splitext(os.path.basename(raw_path))[0]
        mzml_path = os.path.join(self._temp_dir, basename + ".mzML")
        if not os.path.isfile(mzml_path):
            self._cleanup()
            raise PeakListParseError(
                f"ThermoRawFileParser did not produce expected output "
                f"{mzml_path}"
            )

        self._reader = mzml.read(mzml_path, use_index=True, huge_tree=True)
        logger.debug("Loaded converted mzML: %s", mzml_path)

    def __getitem__(self, spec_id: str) -> Spectrum:
        """Return spectrum by Thermo nativeID string.

        Args:
            spec_id: e.g. "controllerType=0 controllerNumber=1 scan=42"

        Returns:
            Spectrum object.

        Raises:
            PeakListParseError: If spectrum not found.
        """
        try:
            spec = self._reader.get_by_id(spec_id)
        except KeyError:
            raise PeakListParseError(
                f"Spectrum with id {spec_id!r} not found in RAW-converted mzML"
            )
        return self._convert_spectrum(spec)

    def _convert_spectrum(self, spec: dict[str, Any]) -> Spectrum:
        """Convert pyteomics mzML spectrum dict to Spectrum object."""
        if spec["scanList"]["count"] != 1:
            raise ValueError(
                "xiSEARCH2 currently only supports a single scan per spectrum."
            )
        scan = spec["scanList"]["scan"][0]

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

        precursor = {
            "mz": p["selected ion m/z"],
            "charge": p.get("charge state", np.nan),
            "intensity": p.get("peak intensity", np.nan),
        }

        rt = scan.get("scan start time", np.nan)
        rt = rt * 60

        return Spectrum(
            precursor, spec["m/z array"], spec["intensity array"], rt
        )

    def _cleanup(self) -> None:
        """Remove the temporary directory created during conversion."""
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def __del__(self) -> None:
        self._cleanup()
