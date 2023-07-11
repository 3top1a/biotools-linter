import logging

from rule.url import filter_url

from message import Message

URL_REGEX = r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
IMPORTANT_KEYS = ["name", "description",
                  "homepage", "biotoolsID", "biotoolsCURIE"]

urls_already_checked = {}


def reset_cache() -> None:
    """Reset the cache of checked URLs.

    Returns
    -------
        None

    Raises
    ------
        None
    """
    urls_already_checked.clear()


def delegate_filter(key: str, value: str) -> Message | None:
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

    if value is None or value == [] or value == "":
        output.append(filter_none(key, value))
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
            return Message("TEXT001", f"Important key {key} is null/empty")

    return None

