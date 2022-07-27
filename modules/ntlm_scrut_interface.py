"""
The module for interaction with ntlm-scrutinizer's API

Author:
    Konstantin S. (https://github.com/ST1LLY)
"""
import logging
import os
from typing import Any
from urllib.parse import urljoin

import requests
from requests import Response

from enviroment import TEMP_DIR


class NTLMScrutInterface:
    """
    The class for interaction with ntlm-scrutinizer
    """

    def __init__(self, host: str, port: str) -> None:
        self.__base_url = f'https://{host}:{port}'

    @staticmethod
    def __send_get(url: str) -> Response:
        """
        Wrapper for sending GET request
        """

        logging.debug('GET: %s', locals())
        response = requests.get(url, verify=False)

        logging.debug('GET %s status code: %s', url, response.status_code)

        if response.status_code in (200,):
            return response

        raise Exception(f'Error of POST request to url: {url} response: {response.__dict__}')

    @staticmethod
    def __send_post(url: str, json_content: dict[str, str | int] | None = None) -> Response:
        """
        Wrapper for sending POST request
        """

        logging.debug('POST: %s', locals())
        response = requests.post(url, verify=False, json=json_content)

        logging.debug('POST %s status_code: %s', url, response.status_code)

        if response.status_code == 200:
            return response

        raise Exception(f'Error of POST request to url: {url} response: {response.__dict__}')

    def dump_ntlm_run(self, target: str) -> dict[str, str]:
        """
        Dump NTLM-hashes from AD
        """
        return self.__send_post(urljoin(self.__base_url, 'dump-ntlm/run'), {'target': target}).json()

    def dump_ntlm_status(self, session_name: str) -> dict[str, str]:
        """
        Get information about a running process of dumping NTLM-hashes
        """
        return self.__send_get(urljoin(self.__base_url, f'dump-ntlm/status?session_name={session_name}')).json()

    def brute_ntlm_run(self, hash_file_path: str) -> dict[str, str]:
        """
        Run an instance for bruting
        """
        return self.__send_post(urljoin(self.__base_url, 'brute-ntlm/run'), {'hash_file_path': hash_file_path}).json()

    def brute_ntlm_info(self, session_name: str) -> dict[str, Any]:
        """
        Get information about a running instance
        """
        return self.__send_get(urljoin(self.__base_url, f'brute-ntlm/info?session_name={session_name}')).json()

    def brute_ntlm_re_run(self, session_name: str) -> dict[str, str]:
        """
        Re-run an instance of hashcat to brute NTLM-hashes if the restore file exists
        """
        return self.__send_post(urljoin(self.__base_url, f'brute-ntlm/re-run?session_name={session_name}')).json()

    def creds_bruted(self, session_name: str) -> dict[str, Any]:
        """
        Get bruted credentials
        """
        return self.__send_get(urljoin(self.__base_url, f'creds/bruted?session_name={session_name}')).json()

    def download_ntlm_hashes(self, file_path: str) -> str:
        """
        Download file cointains dumped NTLM-hashes
        """
        output_file_path = os.path.join(TEMP_DIR, os.path.basename(file_path))
        with open(output_file_path, 'wb') as file:
            url = urljoin(self.__base_url, f'dump-ntlm/download-hashes?file_path={file_path}')
            resp = requests.get(url, verify=False)
            if resp.status_code != 200:
                raise Exception(f'url:{url} resp:{resp}')
            file.write(resp.content)
        return output_file_path
