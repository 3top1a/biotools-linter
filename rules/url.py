"""URL rules."""

import logging
import re

import requests
from requests.adapters import HTTPAdapter

from message import Message

# Initialize (here so it inits once)
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
req_session = requests.Session()
adapter = HTTPAdapter(
    pool_connections=100, pool_maxsize=100)
req_session.mount("http://", adapter)
req_session.mount("https://", adapter)
# Change the UA so it doesn't get rate limited
req_session.headers.update({"User-Agent": user_agent})

URL_REGEX = r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
REPORT = 15
TIMEOUT = 25

def filter_url(key: str, value: str) -> Message | None:
    """Filter the URL based on various conditions.

    Attributes
    ----------
        key (str): The key to filter.
        value (str): The value to filter.
        return_q (queue.Queue | None): The queue to store filter results (default: None).

    Returns
    -------
        Message or None

    Raises
    ------
        None
    """
    # Return if does not match URL or key doesnt end with url/uri
    if not re.match(URL_REGEX, value) and not key.endswith("url") and not key.endswith("uri"):
        return None

    # If the URL doesn't match the regex but is in a url/uri entry, throw an error
    if not re.match(URL_REGEX, value) and (key.endswith(("url", "uri"))):
        return Message("URL001", f"URL {value} in entry at {key} does not match a URL")

    logging.debug(f"Checking URL: {value}")

    # Special check for edamontology
    if "://edamontology.org/" in value:
        # TODO(3top1a): Special edamontology checks
        return None

    # Make a request
    try:
        response = req_session.get(value, timeout=TIMEOUT)

        # Status is not HTTP_OK
        if not response.ok:
            return Message("URL002", f"{value} in {key} doesn't returns 200 (HTTP_OK)")

    except requests.Timeout:
        # Timeout error
        return Message("URL003", f"{value} in {key} timeouted in {TIMEOUT} seconds")

    except requests.exceptions.SSLError:
        # SSL error
        return Message("URL004", f"{value} at {key} returned an SSL error")

    except requests.RequestException as e:
        # Generic request error
        return Message("URL---", f"Generic error while making URL request to {value} - {e}")

    return None
