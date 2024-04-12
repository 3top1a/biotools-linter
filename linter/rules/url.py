"""URL rules that check for things like 404s or ssl certificates being expired."""

from __future__ import annotations

import asyncio
import logging
import re

import aiohttp
from cacheout import Cache
from message import Level, Message

# Initialize (here so it inits once)
# Now only used by other filters
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.3 (Bio.tools linter, github.com/3top1a/biotools-linter)"
cache: Cache = Cache(maxsize=2**20, ttl=0, default=None)

timeout = aiohttp.ClientTimeout(
    total=None,
    sock_connect=10,
    sock_read=10,
)
client_args = dict(
    trust_env=True,
    timeout=timeout,
    headers={"User-Agent": user_agent},
)

URL_REGEX = (
    r"(http[s]?)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)
REPORT = 15
# Timeouts cause a lot of slowness in the linter so this value is quite low (the aiohttp default is 5m)
TIMEOUT = 30


async def filter_url(key: str, value: str) -> list[Message] | None:
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
        logging.debug(
            f"Cache hit for URL {value} from tool - {len(hits)} messages")

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
        if (
            not re.match(URL_REGEX, value)
            and not key.endswith("url")
            and not key.endswith("uri")
        ):
            return None

        logging.debug(f"Checking URL: {value}")

        # Exit if it is a ftp address
        if value.startswith("ftp://"):
            logging.debug(
                f"URL `{value}` points to an ftp server and cannot be checked",
            )
            return None

        # If the URL doesn't match the regex but is in a url/uri entry, throw an error
        # For example, this errors when invisible unicode characters are in the URL
        if not re.match(URL_REGEX, value) and (key.endswith(("url", "uri"))):
            return [
                Message(
                    "URL_INVALID",
                    f'The URL {value} at {key} could not be parsed, possibly due to invisible Unicode characters',
                    key,
                    Level.ReportHigh,
                ),
            ]

        # Make a request
        # It streams it and then closes it so it doesn't download the file. Better than HEAD requests.
        try:
            # TODO Move session into singleton (needs to be initialized in async run loop)
            async with aiohttp.ClientSession(**client_args) as session:
                # https://github.com/aio-libs/aiohttp/issues/3203
                # AIOHTTP has an issue with timeouts appearing where they shouldn't be.
                # Making a new timeout for each request seems to eliminate this issue
                response = await session.get(value, timeout=aiohttp.ClientTimeout(total=None,
                                                                                  sock_connect=5,
                                                                                  sock_read=5))

                # Check for redirect
                # See https://docs.aiohttp.org/en/stable/client_advanced.html#redirection-history
                if len(response.history) != 0:
                    reports.append(
                        Message(
                            "URL_PERMANENT_REDIRECT",
                            f'URL {value} at {key} permanently redirected',
                            key,
                            Level.ReportLow,
                        ),
                    )

                # Status is not between 200 and 400
                if not response.ok:
                    reports.append(
                        Message(
                            "URL_BAD_STATUS",
                            # f"URL {value} at {key} doesn't return ok status (>399).",
                            f'URL {value} at {key} returned a non-2xx status code, indicating failure',
                            key,
                            Level.ReportMedium,
                        ),
                    )

                url_starts_with_https = value.startswith("https://")
                if not url_starts_with_https:
                    # Try to request with SSL
                    try:
                        # Takes extreme amount of time if no such site exists, need to refactor
                        new_response = await session.get(
                            value.replace("http://", "https://"),
                        )
                    except aiohttp.ClientConnectorError:
                        # If it fails with ClientConnectorError, the site does not use SSL at all
                        reports.append(
                            Message(
                                "URL_NO_SSL",
                                # f"URL {value} at {key} does not use SSL.",
                                f'Target website lacks SSL encryption.',
                                key,
                                Level.ReportLow,
                            ),
                        )  # Medium as it's hard to fix without owning the website
                    else:
                        # If it succeeds, the site can use SSL but the URL is just wrong
                        reports.append(
                            Message(
                                "URL_UNUSED_SSL",
                                f'Website {value} at {key} supports HTTPS but the provided URL uses HTTP.',
                                key,
                                Level.ReportMedium,
                            ),
                        )  # Medium since your browser should auto-upgrade

        # Timeout error>
        except asyncio.TimeoutError:
            reports.append(
                Message(
                    "URL_TIMEOUT",
                    # f"URL {value} at {key} timeouts after {TIMEOUT} seconds.",
                    f'Website {value} at {key} took longer than 30 seconds to respond.',
                    key,
                    Level.ReportHigh,
                ),
            )  # High as it's inaccessible

        except aiohttp.TooManyRedirects:
            # Timeout error
            reports.append(
                Message(
                    "URL_TOO_MANY_REDIRECTS",
                    # f"URL {value} at {key} failed exceeded 30 redirects.",
                    f'Encountered excessive or infinite redirects while fetching URL {value} at {key}',
                    key,
                    Level.ReportHigh,
                ),
            )

        except aiohttp.ClientSSLError as e:
            # SSL error
            reports.append(
                Message(
                    "URL_SSL_ERROR",
                    # f"URL {value} at {key} returned an SSL error. ({e})",
                    f'Detected an invalid or expired TLS certificate while fetching URL {value} at {key}: {e}',
                    key,
                    Level.ReportHigh,
                ),
            )

        except aiohttp.ClientConnectionError:
            # Connection error
            reports.append(
                Message(
                    "URL_CONN_ERROR",
                    # f"URL {value} at {key} returned a connection error, it may not exist.",
                    f'Unable to establish a network connection to the URL {value} at {key}',
                    key,
                    Level.ReportHigh,  # High as it may not even exist
                ),
            )

    except Exception as e:
        # Catch all request error
        reports.append(
            Message(
                "URL_LINTER_ERROR",
                # f"Error: {e} at {key} while checking {value}",
                f'Encountered an unhandled error while validating URL {value} at {key}. Manual review required.',
                key,
                Level.LinterError,
            ),
        )

    # Add to cache
    cache.set(value, reports)

    if len(reports) != 0:
        return reports
    return None


def clear_cache():
    global cache
    cache.clear()
