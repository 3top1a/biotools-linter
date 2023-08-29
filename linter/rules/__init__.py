"""Rule delegator.

Please keep reports in the following format:
what(URL, name) `value(example.com)` at `key(tool//description)` is Issue(missing, invalid).
"""

from __future__ import annotations

import logging

from message import Message

from .url import filter_url

URL_REGEX = r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
IMPORTANT_KEYS = ["name", "description",
                  "homepage", "biotoolsID", "biotoolsCURIE"]

def delegate_filter(key: str, value: str) -> list[Message] | None:
    """Delegate to separate filter functions based on the key and value.

    Attributes
    ----------
        key (str): The key to filter.
        value (str): The value to filter.
        return_q (queue.Queue | None): The queue to store filter results (default: None).

    Returns
    -------
        None

    Raises
    ------
        None
    """
    logging.debug(f"Checking {key}: {value!s}")

    output = []

    none = filter_none(key, value)
    if value is None or value == [] or value == "":
        output.append(none)
        # We can't check anything else as it will error
        return output

    url = filter_url(key, value)
    if url is not None:
        output.extend(url)

    if output is []:
        return None
    return output


def filter_none(key: str, _value: str) -> Message | None:
    """Filter the key-value pair if the value is None or empty.

    Attributes
    ----------
        key (str): The key to filter.
        value (str): The value to filter.
        return_q (queue.Queue | None): The queue to store filter results (default: None).

    Returns
    -------
        None

    Raises
    ------
        None
    """
    logging.debug(f"{key} returned null")

    for ik in IMPORTANT_KEYS:
        if key.endswith(ik):
            #TODO(3top1a) Needs to be more specific
            #return Message("NONE001", f"Important value `` at `{key}` is null/empty.")
            pass

    return None
