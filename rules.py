import logging
import queue
import re

import requests

REPORT = 15

urls_already_checked = {}

# Initialize (here so it inits once)
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
req_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100, pool_maxsize=100)
req_session.mount("http://", adapter)
req_session.mount("https://", adapter)
# Change the UA so it doesn't get rate limited
req_session.headers.update({"User-Agent": user_agent})


def reset_cache():
    urls_already_checked.clear()


def delegate_filter(key: str, value: str, return_q: queue.Queue | None = None):
    """Delegates to seperate filter functions."""
    logging.debug(f"Checking {key}: {value!s}")

    if value is None or value == [] or value == "":
        filter_none(key, value, return_q)
        return

    filter_url(key, value, return_q)


def filter_none(key: str, value: str, return_q: queue.Queue | None = None):
    IMPORTANT_KEYS = ["name", "description",
                      "homepage", "biotoolsID", "biotoolsCURIE"]
    logging.debug(f"{key} returned null")

    for ik in IMPORTANT_KEYS:
        if key.endswith(ik):
            logging.log(REPORT, f"Important key {key} is null/empty")
            if return_q is not None:
                return_q.put(f"Important key {key} is null/empty")


def filter_url(key: str, value: str, return_q: queue.Queue | None = None):
    URL_REGEX = r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

    # Check for cached duplicates
    if key in urls_already_checked and urls_already_checked[key] is not None:
        logging.log(REPORT, urls_already_checked[key])
        if return_q is not None:
            return_q.put(urls_already_checked[key])

    # Return if does not match URL or key doesnt end with url/uri
    if not re.match(URL_REGEX, value) and not key.endswith("url") and not key.endswith("uri"):
        urls_already_checked[key] = None
        return

    # If the URL doesn't match the regex but is in a url/uri entry, throw an error
    elif not re.match(URL_REGEX, value) and (key.endswith(("url", "uri"))):
        urls_already_checked[key] = None
        logging.log(
            REPORT, f"URL {value} in entry at {key} does not match a URL")
        if return_q is not None:
            return_q.put(f"URL {value} in entry at {key} does not match a URL")

    logging.debug("Checking URL: " + value)

    # Special check for edamontology
    if "://edamontology.org/" in value:
        # TODO Special edamontology checks
        logging.debug("Checking edamontology: " + value)
        urls_already_checked[key] = None
        return

    # Make a request
    try:
        response = req_session.get(value, timeout=5)

        # Status is not HTTP_OK
        if response.status_code != 200:
            logging.log(REPORT,
                        f"{value} in {key} doesn't returns 200 (HTTP_OK)")
            urls_already_checked[key] = f"{value} in {key} didn't return 200 (HTTP_OK)"
            if return_q is not None:
                return_q.put(f"{value} in {key} doesn't returns 200 (HTTP_OK)")
            return

    except requests.Timeout:
        # Timeout error
        logging.log(REPORT,
                    f"{value} in {key} timeouted in 5 seconds")
        urls_already_checked[key] = f"{value} in {key} timed out in 5 seconds"
        if return_q is not None:
            return_q.put(f"{value} in {key} timeouted in 5 seconds")
        return

    except requests.exceptions.SSLError:
        # SSL error
        logging.log(REPORT,
                    f"{value} at {key} returned an SSL error")
        urls_already_checked[key] = f"{value} at {key} returned an SSL error"
        if return_q is not None:
            return_q.put(f"{value} at {key} returned an SSL error")
        return

    except requests.RequestException as e:
        # Generic request error
        logging.log(REPORT, f"Error while making URL request to {value} - {e}")
        urls_already_checked[key] = f"Error while making URL request to {value} - {e}"
        if return_q is not None:
            return_q.put(f"Error while making URL request to {value} - {e}")
        return

    urls_already_checked[key] = None
