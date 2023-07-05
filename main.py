#!/usr/bin/env python3

"""A rule-based checker for bio.tools tools 
"""

import argparse
import sys
import requests
import re
import logging
from concurrent.futures import ThreadPoolExecutor
import colorlog

URL_REGEX = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
REPORT = 15
urls_already_checked = set()
req_session = requests.Session()


def main(arguments):
    # Configure requests
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=100, pool_maxsize=100)
    req_session.mount('http://', adapter)
    req_session.mount('https://', adapter)

    # Configure parser
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('name', help="Tool name")
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'REPORT', 'WARNING', 'ERROR'], default='REPORT',
                        help="Set the logging level (default: INFO)")
    parser.add_argument('--page', '-p', default=1, type=int,
                        help="Sets the page of the search")
    args = parser.parse_args(arguments)
    tool_name = args.name
    page = args.page

    # Configure logging
    logging.addLevelName(REPORT, 'REPORT')
    logging.basicConfig(level=args.log_level, force=True)
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(message)s',
        log_colors={
            'DEBUG': 'thin',
            'INFO': 'reset',
            'REPORT': 'bold_green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red'
        },
        reset=True,
        style='%'
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.removeHandler(root_logger.handlers[0])
    root_logger.addHandler(console_handler)

    data = search_api(tool_name, page)

    # Check if it returned a search or a single project
    if 'next' in data.keys():
        logging.info(f"Search returned {len(data['list'])} results")

        for project in data['list']:
            lint_project_json(project)

        if data['next'] != None:
            logging.info(
                f"You can also search the next page (page {int(page) + 1})")
        if data['previous'] != None:
            logging.info(
                f"You can also search the previous page (page {int(page) - 1})")
    else:
        lint_project_json(data)


def search_api(name, page=1):
    """
    Get JSON from biotools API
    """

    logging.debug(f"Searching API for {name}")

    url = f"https://bio.tools/api/t/?q={name}&format=json&page={str(page)}"
    response = req_session.get(url)
    response.raise_for_status()  # Check if the request was successful
    data = response.json()

    return data


def filter_dict(key, value):
    """
    Delegates to filter file
    """

    logging.debug(f"Checking {key}: {str(value)}")

    if value is None:
        logging.debug(f"{key} returned null")
        return

    # Check if URL is not 200
    if re.match(URL_REGEX, value):
        # Filter already checked URLs
        if value not in urls_already_checked:
            logging.debug("Checking URL: " + value)

            try:
                response = req_session.get(value, timeout=5)
                if response.status_code != 200:
                    logging.log(REPORT, 
                        f"{value} in {key} doesn't returns 200 (HTTP_OK)")
            except requests.ConnectTimeout:
                logging.log(REPORT, 
                    f"{value} in {key} timeouted in 5 seconds")
            except requests.RequestException as e:
                logging.error(f"Error while making URL request to {value} - {e}")

            urls_already_checked.add(value)
        else:
            logging.debug("URL {value} already checked")


def flatten_json_to_single_dict(json_data, parent_key='', separator='.'):
    """
    Recursively extract values from JSON

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
        'a': 1,
        'b.alpha': 1,
        'b.beta': 2
    }
    ```


    """

    out = {}

    if isinstance(json_data, list):
        for x in json_data:
            index = json_data.index(x)

            out.update(flatten_json_to_single_dict(x, f"{parent_key}/{index}"))
    elif isinstance(json_data, dict):
        for key, value in json_data.items():
            out.update(flatten_json_to_single_dict(
                value, f"{parent_key}/{key}"))
    else:
        json_data = str(json_data)
        if json_data == "None":
            json_data = None
        out.update({parent_key: json_data})

    return out


def lint_project_json(json_data):
    if len(json_data) == 0:
        logging.critical("Recieved empty JSON!")

    logging.info(f"Starting to lint {json_data['name']}")
    logging.debug(f"JSON returned {len(json_data)} keys")

    dictionary = flatten_json_to_single_dict(json_data)

    executor = ThreadPoolExecutor()
    futures = [executor.submit(filter_dict, key, value)
               for key, value in dictionary.items()]

    for f in futures:
        try:
            f.result()
        except Exception as e:
            logging.critical(f"Error while executing future: {e}")


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
