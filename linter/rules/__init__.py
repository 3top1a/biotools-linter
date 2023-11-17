"""Rule delegator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .edam import edam_filter
from .publications import filter_pub
from .url import filter_url

if TYPE_CHECKING:
    from message import Message

URL_REGEX = r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
IMPORTANT_KEYS = ["name", "description",
                  "homepage", "biotoolsID", "biotoolsCURIE"]

def delegate_key_value_filter(key: str, value: str) -> list[Message] | None:
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

    if "://edamontology.org/" in value:
        messages = edam_filter.filter_edam(key, value)
        if messages is not None:
            output.extend(messages)
    else:
        messages = filter_url(key, value)
        if messages is not None:
            output.extend(messages)

    if output is []:
        return None
    return output

def delegate_whole_json_filter(json: dict) -> list[Message] | None:
    """Delegate to separate filter functions that filter the whole json, not just one key value pair."""
    output = []

    messages = filter_pub(json)
    if messages is not None:
        output.extend(messages)

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
            #Needs to be more specific, removed for now
            pass

    return None
