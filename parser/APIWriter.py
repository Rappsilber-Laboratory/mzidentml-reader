"""APIWriter.py - Class for writing results via an API."""

import json
import traceback
from parser.Writer import Writer
from typing import Any

import requests

from config.config_parser import get_api_configs


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

    def write_data(
        self, table: str, data: list[dict[str, Any]] | dict[str, Any]
    ) -> dict[str, Any] | None:
        response = None
        try:
            API_ENDPOINT = self.base_url + "/write_data"
            API_KEY_VALUE = self.api_key_value
            API_KEY = self.api_key
            headers = {
                "Content-Type": "application/json",
                API_KEY: API_KEY_VALUE,
            }
            payload = {
                "table": table,
                "data": data,
            }
            # Calculate the size of the payload
            payload_size = len(json.dumps(payload))
            print("Payload Size:", payload_size)  # Print the payload size
            response = requests.post(
                url=API_ENDPOINT, headers=headers, json=payload
            )
            response.raise_for_status()

            # Check the response status code and handle it as needed
            if response.status_code == 200:
                print("Request successful:" + API_ENDPOINT)
            else:
                print(f"Unexpected status code: {response.status_code}")
        except Exception as e:
            print(f"Caught an exception: {e}")
            # print(payload)
            traceback.print_exc()
        if response is not None:
            return response.json()
        else:
            return None

    def write_new_upload(self, table: str, data: dict[str, Any]) -> int | None:
        response = None

        try:
            API_ENDPOINT = self.base_url + "/write_new_upload"
            API_KEY_VALUE = self.api_key_value
            API_KEY = self.api_key
            headers = {
                "Content-Type": "application/json",
                API_KEY: API_KEY_VALUE,
            }

            # Calculate the size of the payload
            payload_size = len(json.dumps(data))
            print(
                "write_new_upload Payload Size:", payload_size
            )  # Print the payload size
            response = requests.post(
                url=API_ENDPOINT, headers=headers, json=data
            )
            response.raise_for_status()

            # Check the response status code and handle it as needed
            if response.status_code == 200:
                print("Request successful")
            else:
                print(f"Unexpected status code: {response.status_code}")
            print(response.json())
        except Exception as e:
            print(f"Caught an exception: {e}")
            traceback.print_exc()
        if response is not None:
            return response.json()
        else:
            return None

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
        response = None
        try:
            API_ENDPOINT = (
                self.base_url + "/write_mzid_info?upload_id=" + str(upload_id)
            )
            API_KEY_VALUE = self.api_key_value
            API_KEY = self.api_key
            headers = {
                "Content-Type": "application/json",
                API_KEY: API_KEY_VALUE,
            }
            payload = {
                "analysis_software_list": analysis_software_list,
                "spectra_formats": spectra_formats,
                "provider": provider,
                "audits": audits,
                "samples": samples,
                "bib": bib,
            }
            # Calculate the size of the payload
            payload_size = len(json.dumps(payload))
            print(
                "write_mzid_info Payload Size:", payload_size
            )  # Print the payload size
            response = requests.post(
                url=API_ENDPOINT, headers=headers, json=payload
            )
            response.raise_for_status()
            result = response.json()

            # Check the response status code and handle it as needed
            if response.status_code == 200:
                print("Request successful")
                print(result)
            else:
                print(f"Unexpected status code: {response.status_code}")

            print(result)
        except Exception as e:
            print(f"Caught an exception: {e}")
            traceback.print_exc()
        if response is not None:
            return response.json()
        else:
            return None

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
        response = None
        try:
            # todo: use urljoin
            API_ENDPOINT = (
                self.base_url + "/write_other_info?upload_id=" + str(upload_id)
            )
            API_KEY_VALUE = self.api_key_value
            API_KEY = self.api_key
            headers = {
                "Content-Type": "application/json",
                API_KEY: API_KEY_VALUE,
            }
            payload = {
                "contains_crosslinks": contains_crosslinks,
                "upload_warnings": upload_warnings,
            }
            response = requests.post(
                url=API_ENDPOINT, headers=headers, json=payload
            )
            response.raise_for_status()
            result = response.json()

            # Check the response status code and handle it as needed
            if response.status_code == 200:
                print("Request successful")
                print(result)
            else:
                print(f"Unexpected status code: {response.status_code}")

            print(result)
        except Exception as e:
            print(f"Caught an exception: {e}")
            traceback.print_exc()
        if response is not None:
            return response.json()
        else:
            return None

    def fill_in_missing_scores(self) -> None:
        """ToDo: this needs to be adapted to sqlalchemy from old SQLite version."""
        pass
