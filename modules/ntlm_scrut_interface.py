import requests
import logging
from urllib.parse import urljoin
from requests import Response


class NTLMScrutInterface:
    def __init__(self, host, port) -> None:
        self.__base_url = f'https://{host}:{port}'

    def __send_post(self, url: str, json_content: dict[str, str | int]) -> Response:
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

    def dump_ntlm_status(self) -> None:
        pass

    def brute_ntlm_run(self) -> None:
        pass

    def brute_ntlm_re_run(self) -> None:
        pass

    def brute_ntlm_info(self) -> None:
        pass

    def brute_ntlm_info_all(self) -> None:
        pass

    def creds_bruted(self) -> None:
        pass

    def technical_clean(self) -> None:
        pass
