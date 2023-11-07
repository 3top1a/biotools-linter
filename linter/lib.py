"""Contains main classes and functions for linting."""

from __future__ import annotations

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, ClassVar

import requests
from joblib import Parallel, delayed
from message import Level, Message
from rules import delegate_key_value_filter, delegate_whole_json_filter
from rules.edam import initialize

if TYPE_CHECKING:
    import queue

REPORT: int = 15  # Report log level is between debug and info
TIMEOUT = 20  # Seconds


class Session:

    """Session for interacting with the biotools API and performing data processing.

    Attributes
    ----------
        jsons (dict): Dictonary of a seach query and the resulting JSON

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

    json: dict = ClassVar[dict[dict]]
    executor: None | ThreadPoolExecutor = None

    def __init__(self: Session,
                 json: dict | None = None,
                 cache: dict | None = None) -> None:
        """Initialize a new Session instance.

        Attributes
        ----------
            page (int): The current page number.
            json (dict): The JSON data retrieved from the API.
            cache (dict): Cache.

        Returns
        -------
            None

        Raises
        ------
            None
        """
        if json is None:
            json = {}

        if cache is None:
            cache = {}

        self.json = json
        self.cache = cache

        initialize()

    def clear_search(self: Session) -> None:
        """Reset multiple search. Call before `search_api`."""
        self.json = {}
        self.cache = {}

    def search_api(self: Session,
                   name: str,
                   page: int = 1) -> None:
        """Retrieve JSON data from the biotools API.

        Attributes
        ----------
            names (str): Multiple names to search for.
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

        tries = 5
        url = f"https://bio.tools/api/t/?q={name}&format=json&page={page!s}"

        while tries > 0:
            tries -= 1
            try:
                response = requests.get(url, timeout=TIMEOUT)
                if response.ok:
                    self.json[name] = response.json()
                    return

                logging.error("Non 200 status code received from bio.tools API")
            except Exception as e:
                logging.exception(f"Error while trying to contact the bio.tools API:\n{e}")
                time.sleep(5)

        logging.critical("Could not contact the bio.tools API after 5 tries, aborting")
        sys.exit(1)


    def search_api_multiple_pages(self: Session,
                   name: str,
                   page_start: int = 1,
                   page_end: int = 2) -> None:
        """Retrieve JSON data from the biotools API.

        Attributes
        ----------
            names (str): Multiple names to search for.
            page_start (int): At what page to start (inclusive)
            page_end (int): At which page to stop (exclusive, use +1)

        Returns
        -------
            None

        Raises
        ------
            None
        """
        logging.debug(f"Searching API for {name}")

        try:
            for page in range(page_start, page_end):
                tries = 5
                url = f"https://bio.tools/api/t/?q={name}&format=json&page={page!s}"

                while tries > 0:
                    tries -= 1
                    try:
                        response = requests.get(url, timeout=TIMEOUT)
                        if 'detail' in response.json() and response.json()['detail'] == 'Invalid page. That page contains no results.':
                            logging.warning(f"Page {page} doesn't exist, ending search")
                            return
                        if response.ok:
                            # HACK to avoid overwriting the entire dictionary it just adds the page number to the end to make it unique
                            self.json[f"{name}{page}"] = response.json()
                            break
                        else:
                            logging.error(f"Non 200 status code received from bio.tools API: {response.status_code}")
                    except Exception as e:
                        logging.exception(f"Error while trying to contact the bio.tools API:\n{e}")
                        time.sleep(5)
        except Exception as e:
            logging.critical(f"Could not contact the bio.tools API after 5 tries, aborting: {e}")
            sys.exit(1)


    def return_project_list_json(self: Session) -> list:
        """Return the project list from the JSON data.

        Returns
        -------
            list: The project list.

        Raises
        ------
            None
        """
        output = []
        for query in self.json.values():
            if "list" in query:
                output.extend(query["list"])
            else:
                output.append(query)

        return output

    def lint_specific_project(self: Session,
                              data_json: dict,
                              return_q: queue.Queue | None = None) -> None:
        """Perform linting on a specific project.

        Attributes
        ----------
            data_json (dict): The JSON data of the project.
            return_q (typing.Optional[queue.Queue]): The queue to store linting results (default: None).

        Returns
        -------
            bool: True if cache was used

        Raises
        ------
            None
        """
        if len(data_json) == 0:
            logging.critical("Received empty JSON!")
            return None

        tool_name = data_json["name"]

        if self.executor is None:
            self.executor = ThreadPoolExecutor()

        logging.info(
            f"Linting {tool_name} at https://bio.tools/{data_json['biotoolsID']}")
        logging.debug(f"Project JSON returned {len(data_json)} keys")

        dictionary = flatten_json_to_single_dict(data_json,
                                                 parent_key=tool_name + "/")

        # Put key value filters and whole json filters into queue
        futures = [
            self.executor.submit(delegate_key_value_filter, key, value)
            for key, value in dictionary.items()
        ] + [self.executor.submit(delegate_whole_json_filter, data_json)]

        for f in futures:
            output = f.result()
            for message in output:
                if type(message) == Message:
                    # Add the project name to the message
                    message.project = data_json["biotoolsID"]

                    message.print_message()
                    if return_q is not None:
                        return_q.put(message)

        if return_q is not None:
            m = Message("LINT-F", "Finished linting", "", level=Level.LinterInternal)
            return_q.put(m)

        return False

    def lint_all_projects(self: Session,
                          return_q: queue.Queue | None = None,
                          threads: int = 1) -> None:
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
        logging.debug(f"Linting all projects with {threads} threads")

        self.executor = ThreadPoolExecutor(threads)

        Parallel(n_jobs=threads,
                 prefer="threads",
                 require="sharedmem")(
                     delayed(self.lint_specific_project)(project, return_q)
                     for project in self.return_project_list_json())

    def next_page_exists(self: Session) -> bool:
        """Check if the next page exists in any project.

        Returns
        -------
            bool: True if the next page exists, False otherwise.

        Raises
        ------
            None
        """
        for query in self.json.values():
            if "next" in query:
                return query["next"] is not None
        return False

    def previous_page_exists(self: Session) -> bool:
        """Check if the previous page exists in any project.

        Returns
        -------
            bool: True if the previous page exists, False otherwise.

        Raises
        ------
            None
        """
        for query in self.json.values():
            if "previous" in query:
                return query["previous"] is not None
        return False

    def get_total_project_count(self: Session) -> int:
        """Return the total number (even not on page) of projects found."""
        return next(iter(self.json.items()))[1]["count"]


def flatten_json_to_single_dict(json_data: dict,
                                parent_key: str = "",
                                separator: str = "/") -> dict:
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

            out.update(
                flatten_json_to_single_dict(x,
                                            f"{parent_key}{separator}{index}"))
    elif isinstance(json_data, dict):
        for key, value in json_data.items():
            out.update(
                flatten_json_to_single_dict(value,
                                            f"{parent_key}{separator}{key}"))
    else:
        value = str(json_data)
        if value == "None":
            value = None
        out.update({parent_key: value})

    return out
