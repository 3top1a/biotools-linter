"""Contains main classes and functions for linting."""

from __future__ import annotations

import asyncio
import logging
import queue
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import ClassVar

import requests
from message import Level, Message
from requests.adapters import HTTPAdapter
from rules import delegate_key_value_filter, delegate_whole_json_filter
from urllib3.util.retry import Retry
from utils import flatten_json_to_single_dict

REPORT: int = 15  # Report log level is between debug and info
TIMEOUT = (
    60  # Custom timeout for biotools API, it's longer so it doesn't silently crash
)
retries = 5
session = requests.Session()
retry = Retry(
    total=retries,
    read=retries,
    connect=retries,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)


class Session:

    """Session for interacting with the biotools API and performing data processing.

    Once initialized, it can search the bio.tools API for a specific term (for one page or multiple) or an exact tool name.
    The results are put into the session's `json` cache that can be cleared using `clear_cache()`.
    You can lint a single JSON dictionary using `lint_specific_tool_json` or lint all tools in the cache using `lint_all_tools`.
    As these functions are async, the results must be retrieved using a Queue.


    """

    # TODO Get rid of this, replace with function arguments
    json: dict = ClassVar[dict[dict]]
    executor: None | ThreadPoolExecutor = None

    def __init__(
        self: Session,
        json: dict | None = None,
    ) -> None:
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

        self.json = json

    def clear_cache(self: Session) -> None:
        """Reset multiple search. Call before `search_api`."""
        self.json = {}

    def search_api(self: Session, name: str, page: int = 1) -> None:
        """Retrieve JSON data from the biotools API.

        Attributes
        ----------
            names (str): Multiple names to search for.
            page (int): The page number to retrieve (default: 1).

        Returns
        -------
            None

        Raises
        ------
            None
        """
        logging.debug(f"Searching API for {name}")

        url = f"https://bio.tools/api/t/?q={name}&format=json&page={page!s}"

        try:
            response = requests.get(url, timeout=TIMEOUT)
            if response.ok:
                self.json[name] = response.json()
                return

            logging.error("Non 200 status code received from bio.tools API")
        except Exception as e:
            logging.exception(
                f"Error while trying to contact the bio.tools API:\n{e}",
            )
            time.sleep(5)

        logging.critical("Could not contact the bio.tools API after 5 tries, aborting")
        sys.exit(1)

    def search_api_exact_match(self: Session, name: str) -> None:
        """Retrieve JSON data from the biotools API.

        Attributes
        ----------
            names (str): Exact name of the tool.

        Returns
        -------
            None

        Raises
        ------
            None
        """
        logging.debug(f'Searching API for "{name}"')

        url = f"https://bio.tools/api/t/{name}?format=json"

        try:
            response = session.get(url, timeout=TIMEOUT)
            if response.ok:
                json = response.json()
                # Need to wrap it so its compatible with the rest of the code
                json = single_tool_to_search_json(json)
                self.json[name] = json
                return
            logging.error("Exact tool could not be found")
            return
        except Exception as e:
            logging.exception(
                f"Error while trying to contact the bio.tools API:\n{e}",
            )
            time.sleep(5)

        logging.critical("Could not contact the bio.tools API after 5 tries, aborting")
        sys.exit(1)

    def search_api_multiple_pages(
        self: Session,
        name: str,
        page_start: int = 1,
        page_end: int = 2,
    ) -> None:
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
        # Temporarily set to info to debug production crashes
        logging.info(f"Searching API for {name}")

        for page in range(page_start, page_end):
            url = f"https://bio.tools/api/t/?q={name}&format=json&page={page!s}"

            try:
                response = session.get(url, timeout=TIMEOUT)
                if (
                    "detail" in response.json()
                    and response.json()["detail"]
                    == "Invalid page. That page contains no results."
                ):
                    logging.warning(f"Page {page} doesn't exist, ending search")
                    continue

                if response.ok:
                    # To avoid overwriting the entire dictionary it just adds the page number to the end to make it unique
                    self.json[f"{name}{page}"] = response.json()
                    continue

                logging.error(
                    f"Non 200 status code received from bio.tools API: {response.status_code}",
                )
            except Exception as e:
                logging.exception(
                    f"Error while trying to contact the bio.tools API:\n{e}",
                )

    def return_tool_list_json(self: Session) -> list:
        """Return JSON of all tools currently cached.

        Returns
        -------
            list: Tools that have been searched.

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

    async def lint_specific_tool_json(
        self: Session,
        data_json: dict,
        return_q: queue.Queue | None = None,
    ) -> None:
        """Perform linting on a specific tool JSON.

        Attributes
        ----------
            data_json (dict): The JSON data of the tool.
            return_q (typing.Optional[queue.Queue]): The queue to store linting results (default: None).

        Raises
        ------
            None
        """
        if len(data_json) == 0:
            logging.critical("Received empty JSON!")
            return

        tool_name = data_json["name"]

        logging.info(
            f"Linting {tool_name} at https://bio.tools/{data_json['biotoolsID']}",
        )
        logging.debug(f"Tool {tool_name} returned {len(data_json)} JSON keys")

        dictionary = flatten_json_to_single_dict(data_json, parent_key=tool_name + "/")

        # Put key value filters and whole json filters into queue
        futures = [
            delegate_key_value_filter(key, value) for key, value in dictionary.items()
        ] + [delegate_whole_json_filter(data_json)]

        for f in asyncio.as_completed(futures):
            output: list[Message] = await f
            for message in output:
                if type(message) == Message:
                    # Add the tool name to the message
                    message.tool = data_json["biotoolsID"]

                    message.print_message()
                    if return_q is not None:
                        return_q.put(message)

        if return_q is not None:
            m = Message("LINT-F", "Finished linting", "", level=Level.LinterInternal)
            return_q.put(m)

    async def lint_all_tools(
        self: Session,
        return_q: queue.Queue | None = None,
    ) -> None:
        """Perform linting on all tools in cache. Uses multiple threads using a ThreadPoolExecutor.

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
        logging.debug("Linting all tools")

        await asyncio.gather(
            *[
                self.lint_specific_tool_json(tool, return_q)
                for tool in self.return_tool_list_json()
            ],
        )

    def next_page_exists(self: Session) -> bool:
        """Check if the next page exists in any search cache.

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
        """Check if the previous page exists in any search cache.

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

    def get_total_tool_count(self: Session) -> int:
        """Return the total number of tools in cache."""
        return next(iter(self.json.items()))[1]["count"]

def single_tool_to_search_json(json: str | dict) -> dict:
    """
    Convert the JSON of a single tool into the JSON format returned by a search.
    """
    
    # Early quit if it's already processed
    if 'count' in json:
        return json
    
    return {
        "count": 1,
        "next": None,
        "previous": None,
        "list": [
            json,
        ],
    }
