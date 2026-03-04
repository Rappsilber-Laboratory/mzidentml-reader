# """Tests for RawFileReader and related PeakListWrapper integration."""
#
# import os
# import subprocess
# from parser.peaklistReader.PeakListWrapper import (
#     PeakListParseError,
#     PeakListWrapper,
#     SpectrumIdFormatError,
# )
# from parser.peaklistReader.RawFileReader import (
#     _THERMO_ENV_VAR,
#     _THERMO_GITHUB,
#     RawFileReader,
#     ThermoRawFileParserNotFoundError,
#     find_thermorawfileparser,
# )
# from unittest import mock
#
# import numpy as np
# import pytest
#
# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------
#
#
# def _make_fake_spec(mz=500.0, charge=2, intensity=1000.0, rt_min=1.5):
#     """Build a minimal pyteomics-style mzML spectrum dict."""
#     return {
#         "scanList": {
#             "count": 1,
#             "scan": [{"scan start time": rt_min}],
#         },
#         "precursorList": {
#             "count": 1,
#             "precursor": [
#                 {
#                     "selectedIonList": {
#                         "count": 1,
#                         "selectedIon": [
#                             {
#                                 "selected ion m/z": mz,
#                                 "charge state": charge,
#                                 "peak intensity": intensity,
#                             }
#                         ],
#                     }
#                 }
#             ],
#         },
#         "m/z array": np.array([100.0, 200.0, 300.0]),
#         "intensity array": np.array([10.0, 20.0, 30.0]),
#     }
#
#
# # ---------------------------------------------------------------------------
# # TestFindThermoRawFileParser
# # ---------------------------------------------------------------------------
#
#
# class TestFindThermoRawFileParser:
#     def test_env_var_found(self, tmp_path):
#         """Returns path from env var when the file exists and is executable."""
#         exe = tmp_path / "ThermoRawFileParser"
#         exe.write_text("#!/bin/sh\n")
#         exe.chmod(0o755)
#         with mock.patch.dict(os.environ, {_THERMO_ENV_VAR: str(exe)}):
#             result = find_thermorawfileparser()
#         assert result == str(exe)
#
#     def test_env_var_set_but_file_missing(self, tmp_path):
#         """Raises if env var points to a non-existent file."""
#         bad_path = str(tmp_path / "nonexistent")
#         with mock.patch.dict(os.environ, {_THERMO_ENV_VAR: bad_path}):
#             with pytest.raises(ThermoRawFileParserNotFoundError) as exc_info:
#                 find_thermorawfileparser()
#         assert _THERMO_ENV_VAR in str(exc_info.value)
#
#     def test_found_on_path(self):
#         """Returns shutil.which result when found on PATH."""
#         with mock.patch.dict(os.environ, {}, clear=False):
#             # Ensure env var is not set
#             os.environ.pop(_THERMO_ENV_VAR, None)
#             with mock.patch(
#                 "shutil.which", return_value="/usr/bin/ThermoRawFileParser"
#             ):
#                 result = find_thermorawfileparser()
#         assert result == "/usr/bin/ThermoRawFileParser"
#
#     def test_sh_wrapper_found_on_path(self):
#         """Returns .sh wrapper when ThermoRawFileParser not found but .sh is."""
#
#         def which_side_effect(name):
#             if name == "ThermoRawFileParser":
#                 return None
#             if name == "ThermoRawFileParser.sh":
#                 return "/usr/local/bin/ThermoRawFileParser.sh"
#             return None
#
#         with mock.patch.dict(os.environ, {}, clear=False):
#             os.environ.pop(_THERMO_ENV_VAR, None)
#             with mock.patch("shutil.which", side_effect=which_side_effect):
#                 result = find_thermorawfileparser()
#         assert result == "/usr/local/bin/ThermoRawFileParser.sh"
#
#     def test_not_found_anywhere(self):
#         """Raises ThermoRawFileParserNotFoundError with env var name and URL."""
#         with mock.patch.dict(os.environ, {}, clear=False):
#             os.environ.pop(_THERMO_ENV_VAR, None)
#             with mock.patch("shutil.which", return_value=None):
#                 with pytest.raises(
#                     ThermoRawFileParserNotFoundError
#                 ) as exc_info:
#                     find_thermorawfileparser()
#         msg = str(exc_info.value)
#         assert _THERMO_ENV_VAR in msg
#         assert _THERMO_GITHUB in msg
#
#
# # ---------------------------------------------------------------------------
# # TestRawFileReaderLoad
# # ---------------------------------------------------------------------------
#
#
# class TestRawFileReaderLoad:
#     def test_wrong_spectrum_id_format_raises(self):
#         """load() raises SpectrumIdFormatError for non-MS:1000768 accessions."""
#         reader = RawFileReader("MS:1001530")
#         with pytest.raises(SpectrumIdFormatError):
#             reader.load("/fake/path/file.raw")
#
#     def test_subprocess_called_with_correct_args(self, tmp_path):
#         """subprocess.run is called with the expected arguments."""
#         raw = tmp_path / "sample.raw"
#         raw.write_bytes(b"fake")
#         mzml_out = tmp_path / "sample.mzML"
#         mzml_out.write_bytes(b"<mzML/>")
#
#         mock_result = mock.MagicMock()
#         mock_result.returncode = 0
#
#         with (
#             mock.patch(
#                 "parser.peaklistReader.RawFileReader.find_thermorawfileparser",
#                 return_value="/usr/bin/ThermoRawFileParser",
#             ),
#             mock.patch("subprocess.run", return_value=mock_result) as mock_run,
#             mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)),
#             mock.patch("pyteomics.mzml.read"),
#         ):
#             reader = RawFileReader("MS:1000768")
#             reader.load(str(raw))
#
#         mock_run.assert_called_once()
#         call_args = mock_run.call_args[0][0]
#         assert call_args[0] == "/usr/bin/ThermoRawFileParser"
#         assert "-i" in call_args
#         assert str(raw) in call_args
#         assert "-f" in call_args
#         assert "2" in call_args
#         assert "-o" in call_args
#
#     def test_nonzero_exit_raises(self, tmp_path):
#         """Non-zero subprocess exit raises PeakListParseError."""
#         raw = tmp_path / "sample.raw"
#         raw.write_bytes(b"fake")
#
#         mock_result = mock.MagicMock()
#         mock_result.returncode = 1
#         mock_result.stdout = "some output"
#         mock_result.stderr = "some error"
#
#         with (
#             mock.patch(
#                 "parser.peaklistReader.RawFileReader.find_thermorawfileparser",
#                 return_value="/usr/bin/ThermoRawFileParser",
#             ),
#             mock.patch("subprocess.run", return_value=mock_result),
#             mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)),
#         ):
#             reader = RawFileReader("MS:1000768")
#             with pytest.raises(PeakListParseError):
#                 reader.load(str(raw))
#
#     def test_timeout_raises(self, tmp_path):
#         """subprocess.TimeoutExpired raises PeakListParseError."""
#         raw = tmp_path / "sample.raw"
#         raw.write_bytes(b"fake")
#
#         with (
#             mock.patch(
#                 "parser.peaklistReader.RawFileReader.find_thermorawfileparser",
#                 return_value="/usr/bin/ThermoRawFileParser",
#             ),
#             mock.patch(
#                 "subprocess.run",
#                 side_effect=subprocess.TimeoutExpired(
#                     cmd="ThermoRawFileParser", timeout=600
#                 ),
#             ),
#             mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)),
#         ):
#             reader = RawFileReader("MS:1000768")
#             with pytest.raises(PeakListParseError) as exc_info:
#                 reader.load(str(raw))
#         assert "timed out" in str(exc_info.value).lower()
#
#     def test_missing_mzml_output_raises(self, tmp_path):
#         """Missing mzML output file after conversion raises PeakListParseError."""
#         raw = tmp_path / "sample.raw"
#         raw.write_bytes(b"fake")
#
#         mock_result = mock.MagicMock()
#         mock_result.returncode = 0
#
#         with (
#             mock.patch(
#                 "parser.peaklistReader.RawFileReader.find_thermorawfileparser",
#                 return_value="/usr/bin/ThermoRawFileParser",
#             ),
#             mock.patch("subprocess.run", return_value=mock_result),
#             mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)),
#         ):
#             reader = RawFileReader("MS:1000768")
#             # No mzML file created in tmp_path
#             with pytest.raises(PeakListParseError) as exc_info:
#                 reader.load(str(raw))
#         assert "mzml" in str(exc_info.value).lower()
#
#
# # ---------------------------------------------------------------------------
# # TestRawFileReaderGetItem
# # ---------------------------------------------------------------------------
#
#
# class TestRawFileReaderGetItem:
#     def _make_loaded_reader(self):
#         """Return a RawFileReader with a mocked _reader."""
#         reader = RawFileReader("MS:1000768")
#         reader._reader = mock.MagicMock()
#         return reader
#
#     def test_get_by_id_called_with_native_id(self):
#         """__getitem__ calls get_by_id with the native ID string."""
#         reader = self._make_loaded_reader()
#         spec = _make_fake_spec()
#         reader._reader.get_by_id.return_value = spec
#         native_id = "controllerType=0 controllerNumber=1 scan=42"
#         result = reader[native_id]
#         reader._reader.get_by_id.assert_called_once_with(native_id)
#         assert result.precursor["mz"] == 500.0
#
#     def test_missing_spectrum_raises(self):
#         """KeyError from get_by_id is converted to PeakListParseError."""
#         reader = self._make_loaded_reader()
#         reader._reader.get_by_id.side_effect = KeyError("not found")
#         with pytest.raises(PeakListParseError):
#             reader["controllerType=0 controllerNumber=1 scan=99"]
#
#     def test_convert_spectrum_rt_in_seconds(self):
#         """Retention time is converted from minutes to seconds."""
#         reader = self._make_loaded_reader()
#         spec = _make_fake_spec(rt_min=2.0)  # 2 minutes
#         reader._reader.get_by_id.return_value = spec
#         result = reader["controllerType=0 controllerNumber=1 scan=1"]
#         assert result.rt == pytest.approx(120.0)
#
#     def test_convert_spectrum_nan_defaults(self):
#         """Missing charge/intensity default to NaN."""
#         reader = self._make_loaded_reader()
#         spec = _make_fake_spec()
#         # Remove optional fields
#         ion = spec["precursorList"]["precursor"][0]["selectedIonList"][
#             "selectedIon"
#         ][0]
#         del ion["charge state"]
#         del ion["peak intensity"]
#         reader._reader.get_by_id.return_value = spec
#         result = reader["controllerType=0 controllerNumber=1 scan=1"]
#         assert np.isnan(result.precursor["charge"])
#         assert np.isnan(result.precursor["intensity"])
#
#
# # ---------------------------------------------------------------------------
# # TestRawFileReaderCleanup
# # ---------------------------------------------------------------------------
#
#
# class TestRawFileReaderCleanup:
#     def test_cleanup_removes_temp_dir(self, tmp_path):
#         """_cleanup() removes the temp directory."""
#         td = str(tmp_path / "temp_conv")
#         os.makedirs(td)
#         reader = RawFileReader("MS:1000768")
#         reader._temp_dir = td
#         reader._cleanup()
#         assert not os.path.exists(td)
#         assert reader._temp_dir is None
#
#     def test_cleanup_idempotent(self):
#         """_cleanup() can be called multiple times safely."""
#         reader = RawFileReader("MS:1000768")
#         reader._temp_dir = None
#         reader._cleanup()  # should not raise
#         reader._cleanup()
#
#     def test_cleanup_safe_with_none(self):
#         """_cleanup() is safe when _temp_dir is None."""
#         reader = RawFileReader("MS:1000768")
#         reader._cleanup()  # no exception
#
#
# # ---------------------------------------------------------------------------
# # TestPeakListWrapperRawIntegration
# # ---------------------------------------------------------------------------
#
#
# class TestPeakListWrapperRawIntegration:
#     def test_is_raw_true_for_ms1000563(self):
#         """is_raw() returns True only for MS:1000563."""
#         wrapper = object.__new__(PeakListWrapper)
#         wrapper.file_format_accession = "MS:1000563"
#         assert wrapper.is_raw() is True
#
#     def test_is_raw_false_for_other(self):
#         """is_raw() returns False for other accessions."""
#         wrapper = object.__new__(PeakListWrapper)
#         wrapper.file_format_accession = "MS:1001062"
#         assert wrapper.is_raw() is False
#
#     def test_peaklistwrapper_creates_rawfilereader(self, tmp_path):
#         """PeakListWrapper instantiates RawFileReader for MS:1000563."""
#         raw = tmp_path / "sample.raw"
#         raw.write_bytes(b"fake")
#         mzml_out = tmp_path / "sample.mzML"
#         mzml_out.write_bytes(b"<mzML/>")
#
#         mock_result = mock.MagicMock()
#         mock_result.returncode = 0
#
#         with (
#             mock.patch(
#                 "parser.peaklistReader.RawFileReader.find_thermorawfileparser",
#                 return_value="/usr/bin/ThermoRawFileParser",
#             ),
#             mock.patch("subprocess.run", return_value=mock_result),
#             mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)),
#             mock.patch("pyteomics.mzml.read"),
#         ):
#             wrapper = PeakListWrapper(str(raw), "MS:1000563", "MS:1000768")
#         from parser.peaklistReader.RawFileReader import RawFileReader
#
#         assert isinstance(wrapper.reader, RawFileReader)
#
#     def test_peaklistwrapper_unsupported_format_raises(self, tmp_path):
#         """PeakListWrapper raises PeakListParseError for unknown format."""
#         fake = tmp_path / "data.xyz"
#         fake.write_bytes(b"x")
#         with pytest.raises(PeakListParseError) as exc_info:
#             PeakListWrapper(str(fake), "MS:9999999", "MS:1000768")
#         assert "Unsupported file format" in str(exc_info.value)
#
#
# # ---------------------------------------------------------------------------
# # TestMZMLReaderMS1000768
# # ---------------------------------------------------------------------------
#
#
# class TestMZMLReaderMS1000768:
#     def test_mzml_reader_ms1000768_calls_get_by_id(self):
#         """MZMLReader with MS:1000768 calls get_by_id with the spec_id."""
#         from parser.peaklistReader.PeakListWrapper import MZMLReader
#
#         reader = MZMLReader("MS:1000768")
#         reader._reader = mock.MagicMock()
#         spec = _make_fake_spec()
#         reader._reader.get_by_id.return_value = spec
#
#         native_id = "controllerType=0 controllerNumber=1 scan=5"
#         result = reader[native_id]
#         reader._reader.get_by_id.assert_called_once_with(native_id)
#         assert result.precursor["mz"] == 500.0
#
#     def test_mzml_reader_unknown_accession_raises(self):
#         """MZMLReader raises SpectrumIdFormatError for unsupported accessions."""
#         from parser.peaklistReader.PeakListWrapper import MZMLReader
#
#         reader = MZMLReader("MS:9999999")
#         reader._reader = mock.MagicMock()
#         with pytest.raises(SpectrumIdFormatError):
#             reader["some_id"]
#
#     def test_mzml_reader_ms1001530_still_works(self):
#         """MZMLReader still supports original MS:1001530 accession."""
#         from parser.peaklistReader.PeakListWrapper import MZMLReader
#
#         reader = MZMLReader("MS:1001530")
#         reader._reader = mock.MagicMock()
#         spec = _make_fake_spec()
#         reader._reader.get_by_id.return_value = spec
#         result = reader["spectrum=1"]
#         assert result.precursor["mz"] == 500.0
