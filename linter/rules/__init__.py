"""Rule delegator.

Exposes two methods:
- delegate_key_value_filter() for delegating specific JSON pairs
- delegate_whole_json_filter() for delegating the entire tools JSON
"""

from __future__ import annotations

import asyncio

from message import Message

from .edam import edam_filter
from .publications import filter_pub
from .url import filter_url

URL_REGEX = r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
IMPORTANT_KEYS = ["name", "description", "homepage", "biotoolsID", "biotoolsCURIE"]


async def delegate_key_value_filter(key: str, value: str) -> list[Message] | None:
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
    # logging.debug(f"Checking {key}: {value!s}") Only makes noisy output, theres logging at every rule submodule

    output = []

    none = filter_none(key, value)
    if value is None or value == [] or value == "":
        output.append(none)
        # We can't check anything else as it will error
        return output

    futures = []
    if "://edamontology.org/" in value:
        futures.append(edam_filter.filter_edam_key_value_pair(key, value))
    else:
        futures.append(filter_url(key, value))

    results = await asyncio.gather(*futures)
    [output.extend(x) if x is not None else None for x in results]

    if output is []:
        return None
    return output


async def delegate_whole_json_filter(json: dict) -> list[Message] | None:
    """Delegate to separate filter functions that filter the whole json, not just one key value pair."""
    output = []
    futures = []

    futures.append(filter_pub(json))
    futures.append(edam_filter.filter_whole_json(json))

    results = await asyncio.gather(*futures)
    [output.extend(x) if x is not None else None for x in results]

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
    # Needs to be more specific, removed for now
    #for ik in IMPORTANT_KEYS:
    #    if key.endswith(ik):
    #        pass

    return None
