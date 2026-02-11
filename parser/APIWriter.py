"""APIWriter.py - Class for writing results via an API."""

import gzip
import json
import logging
import os
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
        self._use_gzip = os.environ.get("GZIP_REQUESTS", "").lower() in (
            "1", "true", "yes",
        )
        if self._use_gzip:
            logger.info("gzip compression enabled for API requests")

    def _get_headers(self, compressed: bool = False) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            self.api_key: self.api_key_value,
        }
        if compressed:
            headers["Content-Encoding"] = "gzip"
        return headers

    def _post(
        self, url: str, payload: Any, timeout: tuple[int, int] = API_TIMEOUT
    ) -> requests.Response:
        """Serialize payload to JSON and POST. Optionally gzip-compress."""
        raw = json.dumps(payload).encode("utf-8")

        if self._use_gzip:
            compressed = gzip.compress(raw)
            ratio = len(compressed) / len(raw) * 100 if raw else 0
            logger.info(
                f"payload raw={len(raw)} compressed={len(compressed)} "
                f"ratio={ratio:.1f}%"
            )
            return requests.post(
                url=url,
                data=compressed,
                headers=self._get_headers(compressed=True),
                timeout=timeout,
            )

        logger.info(f"payload size={len(raw)} bytes")
        return requests.post(
            url=url,
            data=raw,
            headers=self._get_headers(),
            timeout=timeout,
        )

    def _track_count(self, table: str, count: int) -> None:
        self._write_counts[table] = self._write_counts.get(table, 0) + count

    def get_write_summary(self) -> dict[str, int]:
        """Return cumulative record counts written per table."""
        return dict(self._write_counts)

    @staticmethod
    def _strip_none_values(
        data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Remove keys with None values to reduce payload size."""
        return [{k: v for k, v in row.items() if v is not None} for row in data]

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

        # Strip None values to reduce payload size
        data = self._strip_none_values(data)

        API_ENDPOINT = self.base_url + "/write_data"
        payload = {
            "table": table,
            "data": data,
        }

        logger.info(
            f"write_data table={table} records={record_count}"
        )

        response = self._post(API_ENDPOINT, payload)
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

        logger.info("write_new_upload")

        response = self._post(API_ENDPOINT, data)
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
        logger.info(f"write_mzid_info upload_id={upload_id}")

        response = self._post(API_ENDPOINT, payload)
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

        response = self._post(API_ENDPOINT, payload)
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
