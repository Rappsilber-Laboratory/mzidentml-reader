"""APIWriter.py - Class for writing results via an API."""

import json
import logging
from parser.Writer import Writer
from typing import Any

import requests

from config.config_parser import get_api_configs

logger = logging.getLogger(__name__)

# Default timeout for API requests (connect_timeout, read_timeout) in seconds
API_TIMEOUT = (10, 120)


# noinspection PyPep8Naming
class APIWriter(Writer):
    """Class for writing results to a relational database."""

    def __init__(
        self, upload_id: int | None = None, pxid: str | None = None
    ) -> None:
        super().__init__(upload_id, pxid)
        configs = get_api_configs()
        self.base_url = configs["base_url"]
        self.api_key = configs["api_key"]
        self.api_key_value = configs["api_key_value"]
        self._write_counts: dict[str, int] = {}

    def _get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            self.api_key: self.api_key_value,
        }

    def _track_count(self, table: str, count: int) -> None:
        self._write_counts[table] = self._write_counts.get(table, 0) + count

    def get_write_summary(self) -> dict[str, int]:
        """Return cumulative record counts written per table."""
        return dict(self._write_counts)

    def write_data(
        self, table: str, data: list[dict[str, Any]] | dict[str, Any]
    ) -> dict[str, Any] | None:
        # Normalize data format to match DatabaseWriter behaviour
        if isinstance(data, dict):
            data = [data]

        # Ensure all dicts have the same keys (fill missing with None)
        keys = list(set(k for r in data for k in r.keys()))
        for r in data:
            for k in keys:
                if k not in r:
                    r[k] = None

        record_count = len(data)
        self._track_count(table, record_count)

        API_ENDPOINT = self.base_url + "/write_data"
        payload = {
            "table": table,
            "data": data,
        }
        payload_size = len(json.dumps(payload))
        logger.info(
            f"write_data table={table} records={record_count} "
            f"payload_size={payload_size} bytes"
        )

        response = requests.post(
            url=API_ENDPOINT,
            headers=self._get_headers(),
            json=payload,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            f"write_data table={table} records={record_count} "
            f"status={response.status_code} "
            f"response={result} "
            f"cumulative_{table}={self._write_counts[table]}"
        )

        return result

    def write_new_upload(self, table: str, data: dict[str, Any]) -> int | None:
        API_ENDPOINT = self.base_url + "/write_new_upload"

        payload_size = len(json.dumps(data))
        logger.info(
            f"write_new_upload payload_size={payload_size} bytes"
        )

        response = requests.post(
            url=API_ENDPOINT,
            headers=self._get_headers(),
            json=data,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            f"write_new_upload status={response.status_code} "
            f"response={result}"
        )

        return result

    def write_mzid_info(
        self,
        analysis_software_list: dict[str, Any],
        spectra_formats: list[Any],
        provider: dict[str, Any],
        audits: dict[str, Any],
        samples: dict[str, Any] | list[Any],
        bib: list[Any],
        upload_id: int,
    ) -> dict[str, Any] | None:
        API_ENDPOINT = (
            self.base_url + "/write_mzid_info?upload_id=" + str(upload_id)
        )
        payload = {
            "analysis_software_list": analysis_software_list,
            "spectra_formats": spectra_formats,
            "provider": provider,
            "audits": audits,
            "samples": samples,
            "bib": bib,
        }
        payload_size = len(json.dumps(payload))
        logger.info(
            f"write_mzid_info upload_id={upload_id} "
            f"payload_size={payload_size} bytes"
        )

        response = requests.post(
            url=API_ENDPOINT,
            headers=self._get_headers(),
            json=payload,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            f"write_mzid_info status={response.status_code} "
            f"response={result}"
        )

        return result

    def write_other_info(
        self,
        contains_crosslinks: bool,
        upload_warnings: list[str],
        upload_id: int,
    ) -> dict[str, Any] | None:
        """Update Upload row with remaining info.

        Args:
            contains_crosslinks: Whether the upload contains crosslink data
            upload_warnings: List of warning messages
            upload_id: Upload identifier

        Returns:
            Response from API, or None if request failed
        """
        API_ENDPOINT = (
            self.base_url + "/write_other_info?upload_id=" + str(upload_id)
        )
        payload = {
            "contains_crosslinks": contains_crosslinks,
            "upload_warnings": upload_warnings,
        }

        logger.info(
            f"write_other_info upload_id={upload_id} "
            f"contains_crosslinks={contains_crosslinks}"
        )

        response = requests.post(
            url=API_ENDPOINT,
            headers=self._get_headers(),
            json=payload,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            f"write_other_info status={response.status_code} "
            f"response={result}"
        )

        return result

    def fill_in_missing_scores(self) -> None:
        """ToDo: this needs to be adapted to sqlalchemy from old SQLite version."""
        pass
