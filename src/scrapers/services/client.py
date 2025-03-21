import http.client

import requests
import urllib3
from faker import Faker
from functools import wraps

from time import sleep

from requests.exceptions import ChunkedEncodingError, ProxyError, SSLError

request_timeout = 30
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
http.client._MAXHEADERS = 1000
max_attempts = 10


def attempts(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        for i in range(5):
            try:
                response = f(*args, **kwargs)

                if response.status_code == 401 or response.status_code == 403:
                    print(response.text)
                    print(response.status_code)

                    raise Exception

                return response
            except (
                ChunkedEncodingError,
                ProxyError,
                SSLError,
            ) as e:
                print(f"method: {f.__name__}, Error: {e}, retrying...")
                sleep(5)

        print("Client exit")
        exit(1)

    return wrapper


def logging_requests(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        response = f(*args, **kwargs)

        info = (
            "--------------------------------------------------------------------------------------------------\n"
            f"Request DATA:\n{args}, \n\n"
            f"Request DATA:\n{kwargs}, \n\n"
            f"Response DATA:\n"
            f"Code: {response.status_code}, \n"
            f"Headers: {response.headers}, \n"
            f"Content: {response.text}, \n"
            "--------------------------------------------------------------------------------------------------\n"
        )

        if response and response.status_code != 200:
            print(info)

        return response

    return wrapper


class Client:
    def __init__(self):
        self.__session = requests.session()

    @property
    def base_headers(self):
        ua = Faker(
            providers=[
                "faker.providers.user_agent",
                "faker.providers.date_time",
                "faker.providers.misc",
            ]
        ).firefox()
        return {
            "User-Agent": ua,
            "Accept": "application/xml, text/xml, */*; q=0.01",
            "Accept-Language": "en-US;q=0.5,en;q=0.3",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

    @logging_requests
    @attempts
    def post(self, url: str, data = None, **kwargs):
        kwargs["headers"] = self.__get_headers(kwargs.get("headers", {}))
        return self.__make_request("post", **{"url": url, "data": data, **kwargs})

    @logging_requests
    @attempts
    def get(self, url: str, **kwargs):
        kwargs["headers"] = self.__get_headers(kwargs.get("headers", {}))
        return self.__make_request("get", **{"url": url, **kwargs})

    def __make_request(self, method: str, **kwargs):
        if method == "post":
            return self.__session.post(**kwargs, verify=False)
        elif method == "get":
            return self.__session.get(**kwargs, verify=False)

    def __get_headers(self, additional: dict) -> dict:
        base = self.base_headers
        if additional:
            base.update(additional)

        return base
