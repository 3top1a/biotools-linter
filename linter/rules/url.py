"""URL rules."""

from __future__ import annotations

import logging
import re

import requests
from message import Message
from requests.adapters import HTTPAdapter

# Initialize (here so it inits once)
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
req_session = requests.Session()
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100)
req_session.mount("http://", adapter)
req_session.mount("https://", adapter)
# Change the UA so it doesn't get rate limited
req_session.headers.update({"User-Agent": user_agent})

URL_REGEX = r"(http[s]?)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
REPORT = 15
TIMEOUT = 30


def filter_url(key: str, value: str) -> list[Message] | None:
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
    # Exit if it is a ftp address
    if value.startswith("ftp://"):
        return None

    # Exit if does not match URL or key doesnt end with url/uri
    if not re.match(
            URL_REGEX,
            value) and not key.endswith("url") and not key.endswith("uri"):
        return None

    # If the URL doesn't match the regex but is in a url/uri entry, throw an error
    if not re.match(URL_REGEX, value) and (key.endswith(("url", "uri"))):
        return [Message(
            "URL001", f"URL `{value}` at `{key}` does not match a valid URL (there may be hidden unicode).")]

    logging.debug(f"Checking URL: {value}")
    reports = []

    # Special check for edamontology
    if "://edamontology.org/" in value:
        # TODO(3top1a): Redirect to edamontology checks
        return None

    # Make a request
    try:
        # https://stackoverflow.com/questions/1731298/how-do-i-check-the-http-status-code-of-an-object-without-downloading-it#1731388
        # The old way was using a get request, however some tools DOS'd the linter
        # because it tried to download a 2GB+ zip file, so we just request the headers
        # with `HEAD` and not the whole content of the file.
        # It's also just faster
        response = req_session.head(value, timeout=TIMEOUT)

        # Return a permanent redirect but only if it doesn't change http to https TODO
        # Lib BUG - when doing a head request, the `url` value after a redirect
        # is the same as the original url, but not with `requests.get`

        if response.is_permanent_redirect:
            reports.append(
                Message(
                    "URL005",
                    f"URL `{value}` at `{key}` returns a permanent redirect."))

        if response.is_redirect or response.is_permanent_redirect:
            # Fixes an annoying bug where response.url was still http
            # even if the redirect was to the https site
            if "Location" in response.headers:
                value = response.headers["Location"]

        # Status is not between 200 and 400
        if not response.ok:
            reports.append(
                Message(
                    "URL002",
                    f"URL `{value}` at `{key}` doesn't return ok status (>399)."))

        url_starts_with_https = value.startswith("https://")
        if not url_starts_with_https:
            # Try to request with SSL
            try:
                req_session.head(value.replace("http://", "https://"),
                                 timeout=TIMEOUT)

            except:
                # If that fails, the site does not use SSL at all
                reports.append(
                    Message("URL006",
                            f"URL `{value}` at `{key}` does not use SSL."))

            else:
                # If it succeeds, the site can use SSL but the URL is just wrong
                reports.append(
                    Message(
                        "URL007",
                        f"URL `{value}` at `{key}` does not start with https:// but site uses SSL.",
                    ))

    except requests.Timeout:
        # Timeout error
        reports.append(
            Message(
                "URL003",
                f"URL `{value}` at `{key}` timeouted after {TIMEOUT} seconds."))

    except requests.exceptions.SSLError:
        # SSL error
        reports.append(
            Message("URL004",
                    f"URL `{value}` at `{key}` returned an SSL error."))

    except requests.exceptions.ConnectionError:
        # Connection error
        reports.append(
            Message(
                "URL008",
                f"URL `{value}` at `{key}` returned a connection error, it may not exist."
            ))

    except requests.RequestException as e:
        # Catch all request error
        reports.append(Message("URL---", f"Error: `{e}` at `{key}`"))

    if len(reports) != 0:
        return reports
    return None
