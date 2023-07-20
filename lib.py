"""Contains main classes and functions for linting."""

import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import ClassVar

import requests

from message import Level, Message
from rules import delegate_filter

REPORT: int = 15
TIMEOUT = 10

class Session:

    """Session for interacting with the biotools API and performing data processing.

    Attributes
    ----------
        page (int): The current page number.
        json (dict): The JSON data retrieved from the API.

    Methods
    -------
        __init__(self, page: int = 1, json: dict = {}) -> None:
            Initializes a new Session instance.
        search_api(self, name: str, page: int = 1) -> None:
            Retrieves JSON data from the biotools API.
        return_project_list_json(self) -> list:
            Returns the project list from the JSON data.
        lint_specific_project(self, data_json: dict, return_q: typing.Optional[queue.Queue] = None) -> None:
            Performs linting on a specific project.
        lint_all_projects(self, return_q: typing.Optional[queue.Queue] = None) -> None:
            Performs linting on all projects in the JSON data.
        next_page_exists(self) -> bool:
            Checks if the next page exists in the JSON data.
        previous_page_exists(self) -> bool:
            Checks if the previous page exists in the JSON data.
    """

    page: int = 1
    json: dict = ClassVar[dict]

    def __init__(self: "Session", page: int = 1, json: dict | None = None) -> None:
        """Initialize a new Session instance.

        Attributes
        ----------
            page (int): The current page number.
            json (dict): The JSON data retrieved from the API.

        Returns
        -------
            None

        Raises
        ------
            None
        """
        if json is None:
            json = {}

        self.page = page
        self.json = json

    def search_api(self: "Session", name: str, page: int = 1, im_feeling_lucky: bool = True) -> None:
        """Retrieve JSON data from the biotools API.

        Attributes
        ----------
            name (str): The name to search for.
            page (int): The page number to retrieve (default: 1).
            im_feeling_lucky (bool): Return only one result if the name is an exact match

        Returns
        -------
            None

        Raises
        ------
            None
        """
        logging.debug(f"Searching API for {name}")

        if im_feeling_lucky:
            # Search as if it's an exact match
            url = f"https://bio.tools/api/t/{name}?format=json"
            response = requests.get(url, timeout=TIMEOUT)
            if response.ok:
                self.json = response.json()
                return

        # Search
        url = f"https://bio.tools/api/t/?q={name}&format=json&page={page!s}"
        response = requests.get(url, timeout=TIMEOUT)
        if response.ok:
            self.json = response.json()
            return

        logging.critical("Could not search the API")

    def return_project_list_json(self: "Session") -> list:
        """Return the project list from the JSON data.

        Returns
        -------
            list: The project list.

        Raises
        ------
            None
        """
        if "next" in self.json:
            logging.info(f"Search returned {len(self.json['list'])} results")

            return self.json["list"]

        return [self.json]

    def lint_specific_project(self: "Session", data_json: dict, return_q: queue.Queue | None = None) -> None:
        """Perform linting on a specific project.

        Attributes
        ----------
            data_json (dict): The JSON data of the project.
            return_q (typing.Optional[queue.Queue]): The queue to store linting results (default: None).

        Returns
        -------
            None

        Raises
        ------
            None
        """
        if len(data_json) == 0:
            logging.critical("Received empty JSON!")
            return

        name = data_json["name"]

        logging.info(
            f"Linting {name} at https://bio.tools/{data_json['biotoolsID']}")
        logging.debug(f"Project JSON returned {len(data_json)} keys")

        dictionary = flatten_json_to_single_dict(data_json, parent_key=name)

        executor = ThreadPoolExecutor()
        futures = [executor.submit(delegate_filter, key, value)
                   for key, value in dictionary.items()]

        for f in futures:
            output = f.result()
            for x in output:
                if type(x) == Message:
                    x.print_message()
                    if return_q is not None:
                        return_q.put(x)

        if return_q is not None:
            m = Message("LINT-F", "Finished linting", level=Level.Debug)
            return_q.put(m)

    def lint_all_projects(self: "Session", return_q: queue.Queue | None = None) -> None:
        """Perform linting on all projects in the JSON data.

        Attributes
        ----------
            return_q (typing.Optional[queue.Queue]): The queue to store linting results (default: None).

        Returns
        -------
            None

        Raises
        ------
            None
        """
        for project in self.return_project_list_json():
            self.lint_specific_project(project, return_q)

    def next_page_exists(self: "Session") -> bool:
        """Check if the next page exists in the JSON data.

        Returns
        -------
            bool: True if the next page exists, False otherwise.

        Raises
        ------
            None
        """
        if "next" in self.json:
            return self.json["next"] is not None
        return False

    def previous_page_exists(self: "Session") -> bool:
        """Check if the previous page exists in the JSON data.

        Returns
        -------
            bool: True if the previous page exists, False otherwise.

        Raises
        ------
            None
        """
        if "previous" in self.json:
            return self.json["previous"] is not None
        return False


def flatten_json_to_single_dict(json_data: dict, parent_key: str = "", separator: str = "/") -> dict:
    """Recursively extract values from JSON.

    For example,
    ```json
    {
        "a": "1",
        "b": {
            "alpha": 1,
            "beta": 2
        }
    }
    ```

    will output

    ```
    {
        'parent.a': 1,
        'parent.b.alpha': 1,
        'parent.b.beta': 2
    }
    ```

    Attributes
    ----------
        json_data (dict): Input JSON.
        parent_key (str): Default key.
        separator (str): Separator between values.

    Returns
    -------
        dict: Output dict.

    Raises
    ------
        None
    """
    out = {}

    if isinstance(json_data, list):
        for x in json_data:
            index = json_data.index(x)

            out.update(flatten_json_to_single_dict(
                x, f"{parent_key}{separator}{index}"))
    elif isinstance(json_data, dict):
        for key, value in json_data.items():
            out.update(flatten_json_to_single_dict(
                value, f"{parent_key}{separator}{key}"))
    else:
        value = str(json_data)
        if value == "None":
            value = None
        out.update({parent_key: value})

    return out
