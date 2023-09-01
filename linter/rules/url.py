"""URL rules."""

from __future__ import annotations

import logging
import re

import requests
from message import Level, Message
from requests.adapters import HTTPAdapter

# Initialize (here so it inits once)
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 (Bio.tools linter, github.com/3top1a/biotools-linter)"
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
    # Wrap it in one big try block in case anything errors
    try:

        # Exit if it is a ftp address
        if value.startswith("ftp://"):
            return None

        # Exit if does not match URL or key doesn't end with url/uri
        if not re.match(
                URL_REGEX,
                value) and not key.endswith("url") and not key.endswith("uri"):
            return None

        # If the URL doesn't match the regex but is in a url/uri entry, throw an error
        if not re.match(URL_REGEX, value) and (key.endswith(("url", "uri"))):
            return [
                Message(
                    "URL_INVALID",
                    f"URL `{value}` at `{key}` does not match a valid URL (there may be hidden unicode).",
                    Level.ReportHigh)]

        logging.debug(f"Checking URL: {value}")
        reports = []

        # Make a request
        # https://stackoverflow.com/questions/1731298/how-do-i-check-the-http-status-code-of-an-object-without-downloading-it#1731388
        # The old way was using a get request, however some tools DOS'd the linter
        # because it tried to download a 2GB+ zip file, so we just request the headers
        # with `HEAD` and not the whole content of the file.
        # It's also just faster
        try:
            response = req_session.head(value, timeout=TIMEOUT, allow_redirects=True)

            response_no_auto_redirect = req_session.head(value, timeout=TIMEOUT, allow_redirects=False)
            if response_no_auto_redirect.is_permanent_redirect:
                reports.append(
                    Message(
                        "URL_PERMANENT_REDIRECT",
                        f"URL `{value}` at `{key}` returns a permanent redirect.",
                        Level.ReportLow))

            # Status is not between 200 and 400
            if not response.ok:
                reports.append(
                    Message(
                        "URL_BAD_STATUS",
                        f"URL `{value}` at `{key}` doesn't return ok status (>399).",
                        Level.ReportMedium))

            url_starts_with_https = value.startswith("https://")
            if not url_starts_with_https:
                # Try to request with SSL
                try:
                    req_session.head(value.replace("http://", "https://"),
                                    timeout=TIMEOUT)

                except:
                    # If that fails, the site does not use SSL at all
                    reports.append(
                        Message("URL_NO_SSL",
                                f"URL `{value}` at `{key}` does not use SSL.",
                                Level.ReportMedium)) # Medium as it's hard to fix without owning the website

                else:
                    # If it succeeds, the site can use SSL but the URL is just wrong
                    reports.append(
                        Message(
                            "URL_UNUSED_SSL",
                            f"URL `{value}` at `{key}` does not start with https:// but site uses SSL.",
                            Level.ReportMedium)) # Medium since your browser should auto-upgrade

        except requests.Timeout:
            # Timeout error
            reports.append(
                Message(
                    "URL_TIMEOUT",
                    f"URL `{value}` at `{key}` timeouts after {TIMEOUT} seconds.",
                    Level.ReportHigh)) # High as it's inaccessible

        except requests.exceptions.SSLError:
            # SSL error
            reports.append(
                Message("URL_SSL_ERROR",
                        f"URL `{value}` at `{key}` returned an SSL error.",
                        Level.ReportHigh))

        except requests.exceptions.ConnectionError:
            # Connection error
            reports.append(
                Message(
                    "URL_CONN_ERROR",
                    f"URL `{value}` at `{key}` returned a connection error, it may not exist.",
                    Level.ReportHigh)) # High as it may not even exist

    except Exception as e:
        # Catch all request error
        reports.append(Message("URL_LINTER_ERROR", f"Error: `{e}` at `{key}`",
                               Level.LinterError))

    if len(reports) != 0:
        return reports
    return None
