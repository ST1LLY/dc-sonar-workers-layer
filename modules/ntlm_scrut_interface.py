from typing import Any

import requests
import logging
from urllib.parse import urljoin
from requests import Response


class NTLMScrutInterface:
    def __init__(self, host, port) -> None:
        self.__base_url = f'https://{host}:{port}'

    def __send_get(self, url) -> Response:
        """
        Wrapper for sending GET request
        """

        logging.debug(f'GET: {locals()}')
        response = requests.get(url, verify=False)

        logging.debug(f'GET {url} status code: {response.status_code}')

        if response.status_code in (200,):
            return response

        raise Exception(f'Error of POST request to url: {url} response: {response.__dict__}')

    def __send_post(self, url: str, json_content: dict[str, str | int] | None = None) -> Response:
        """
        Wrapper for sending POST request
        """

        logging.debug(f'POST: {locals()}')
        response = requests.post(url, verify=False, json=json_content)

        logging.debug(f'POST {url} status_code: {response.status_code}')

        if response.status_code == 200:
            return response

        raise Exception(f'Error of POST request to url: {url} response: {response.__dict__}')

    def dump_ntlm_run(self, target: str) -> dict[str, str]:
        return self.__send_post(urljoin(self.__base_url, 'dump-ntlm/run'), {'target': target}).json()

    def dump_ntlm_status(self, session_name: str) -> dict[str, str]:
        return self.__send_get(urljoin(self.__base_url, f'dump-ntlm/status?session_name={session_name}')).json()

    def brute_ntlm_run(self, hash_file_path: str) -> dict[str, str]:
        return self.__send_post(urljoin(self.__base_url, 'brute-ntlm/run'), {'hash_file_path': hash_file_path}).json()

    def brute_ntlm_info(self, session_name: str) -> dict[str, Any]:
        return self.__send_get(urljoin(self.__base_url, f'brute-ntlm/info?session_name={session_name}')).json()

    def brute_ntlm_re_run(self, session_name: str) -> dict[str, str]:
        return self.__send_post(urljoin(self.__base_url, f'brute-ntlm/re-run?session_name={session_name}')).json()

    def creds_bruted(self, session_name: str) -> dict[str, Any]:
        return self.__send_get(urljoin(self.__base_url, f'creds/bruted?session_name={session_name}')).json()

    def technical_clean_dump(self, session_name: str) -> None:
        self.__send_get(urljoin(self.__base_url, f'technical/clean-dump?session_name={session_name}'))

    def technical_clean_brute(self, session_name: str) -> None:
        self.__send_get(urljoin(self.__base_url, f'technical/clean-brute?session_name={session_name}'))
