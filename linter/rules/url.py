"""URL rules that check for things like 404s or ssl certificates being expired."""

from __future__ import annotations

import logging
import re

import requests
from cacheout import Cache
from message import Level, Message
from requests.adapters import HTTPAdapter
from urllib3 import Retry

# Initialize (here so it inits once)
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 (Bio.tools linter, github.com/3top1a/biotools-linter)"
req_session = requests.Session()
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100)
req_session.mount("http://", adapter)
req_session.mount("https://", adapter)
# Change the UA so it doesn't get rate limited
req_session.headers.update({"User-Agent": user_agent})
cache: Cache = Cache(maxsize=8192, ttl=0, default=None)

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
    global cache

    # Check cache
    if value in cache:
        hits: list[Message] = cache.get(value)
        logging.debug(f"Cache hit for URL {value} from tool - {len(hits)} messages")

        # Replace keys since those are different
        for message in hits:
            message.body = message.body.replace(message.location, key, 1)
            message.location = key

        if len(hits) != 0:
            return hits
        return None

    # Wrap it in one big try block in case anything errors
    try:
        reports: list[Message] = []

        # Exit if does not match URL or key doesn't end with url/uri
        if not re.match(
                URL_REGEX,
                value) and not key.endswith("url") and not key.endswith("uri"):
            return None

        logging.debug(f"Checking URL: {value}")

        # Exit if it is a ftp address
        if value.startswith("ftp://"):
            logging.debug(f"URL `{value}` points to an ftp server and cannot be checked")
            return None

        # If the URL doesn't match the regex but is in a url/uri entry, throw an error
        # For example, this errors when invisible unicode characters are in the URL
        if not re.match(URL_REGEX, value) and (key.endswith(("url", "uri"))):
            return [
                Message(
                    "URL_INVALID",
                    f"URL {value} at {key} does not match a valid URL (there may be hidden unicode).",
                    key,
                    Level.ReportHigh)]

        # Make a request
        # It streams it and then closes it so it doesn't download the file. Better than HEAD requests.
        try:
            response = req_session.get(value, timeout=TIMEOUT, allow_redirects=False, stream=True)

            if response.is_permanent_redirect:
                reports.append(
                    Message(
                        "URL_PERMANENT_REDIRECT",
                        f"URL {value} at {key} returns a permanent redirect.",
                        key,
                        Level.ReportLow))

            # Status is not between 200 and 400
            if not response.ok:
                reports.append(
                    Message(
                        "URL_BAD_STATUS",
                        f"URL {value} at {key} doesn't return ok status (>399).",
                        key,
                        Level.ReportMedium))

            url_starts_with_https = value.startswith("https://")
            if not url_starts_with_https:
                # Try to request with SSL
                try:
                    # Takes extreme amount of time if no such site exists, need to refactor
                    req_session.get(value.replace("http://", "https://"),
                                    stream=True)

                except Exception:
                    # If that fails, the site does not use SSL at all
                    reports.append(
                        Message("URL_NO_SSL",
                                f"URL {value} at {key} does not use SSL.",
                                key,
                                Level.ReportMedium)) # Medium as it's hard to fix without owning the website

                else:
                    # If it succeeds, the site can use SSL but the URL is just wrong
                    reports.append(
                        Message(
                            "URL_UNUSED_SSL",
                            f"URL {value} at {key} does not start with https:// but site uses SSL.",
                            key,
                            Level.ReportMedium)) # Medium since your browser should auto-upgrade

        except requests.Timeout:
            # Timeout error
            reports.append(
                Message(
                    "URL_TIMEOUT",
                    f"URL {value} at {key} timeouts after {TIMEOUT} seconds.",
                    key,
                    Level.ReportHigh)) # High as it's inaccessible

        except requests.TooManyRedirects:
            # Timeout error
            reports.append(
                Message(
                    "URL_TOO_MANY_REDIRECTS",
                    f"URL {value} at {key} failed exceeded 30 redirects.",
                    key,
                    Level.ReportHigh))

        except requests.exceptions.SSLError as e:
            # SSL error
            reports.append(
                Message("URL_SSL_ERROR",
                        f"URL {value} at {key} returned an SSL error. ({e})",
                        key,
                        Level.ReportHigh))

        except requests.exceptions.ConnectionError:
            # Connection error
            reports.append(
                Message(
                    "URL_CONN_ERROR",
                    f"URL {value} at {key} returned a connection error, it may not exist.",
                    key,
                    Level.ReportHigh)) # High as it may not even exist

    except Exception as e:
        # Catch all request error
        reports.append(Message("URL_LINTER_ERROR", f"Error: {e} at {key} while checking {value}",
                               key,
                               Level.LinterError))

    # Add to cache
    cache.set(value, reports)

    if len(reports) != 0:
        return reports
    return None

def clear_cache():
    global cache
    cache.clear()
