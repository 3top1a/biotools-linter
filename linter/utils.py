def flatten_json_to_single_dict(
    json_data: dict,
    parent_key: str = "",
    separator: str = "/",
) -> dict:
    """Recursively extract values from JSON.

    For example,
    ```json
    {
        "a": "1",
        "b": {
            "alpha": 1,
            "beta": 2
        }
    }
    ```

    will output

    ```
    {
        'json.a': 1,
        'json.b.alpha': 1,
        'json.b.beta': 2
    }
    ```

    assuming the parent is `json` and separator is `.`.

    Attributes
    ----------
        json_data (dict): Input JSON.
        parent_key (str): Default key.
        separator (str): Separator between values.

    Returns
    -------
        dict: Output dict.

    Raises
    ------
        None
    """
    out = {}

    if isinstance(json_data, list):
        for x in json_data:
            index = json_data.index(x)

            out.update(
                flatten_json_to_single_dict(x, f"{parent_key}{separator}{index}"),
            )
    elif isinstance(json_data, dict):
        for key, value in json_data.items():
            out.update(
                flatten_json_to_single_dict(value, f"{parent_key}{separator}{key}"),
            )
    else:
        value = str(json_data)
        if value == "None":
            value = None
        out.update({parent_key: value})

    return out

def unflatten_json_from_single_dict(flattened_dict: dict, separator: str = "/") -> dict:
    """Reassembles a flattened dictionary into a nested JSON-like structure.

    Parameters
    ----------
    flattened_dict : dict
        The flattened dictionary with keys as paths.
    separator : str, optional
        The separator used in the keys of the flattened dictionary (default is "/").

    Returns
    -------
    dict
        The reassembled, nested dictionary.
    """
    unflattened_dict = {}
    for compound_key, value in flattened_dict.items():
        parts = compound_key.split(separator)
        current_level = unflattened_dict

        for i, part in enumerate(parts):
            # Remove leading characters that might have been added as a root name
            if i == 0 and not part:
                continue
            if i == len(parts) - 1:
                # Last part of the key, assign the value
                current_level[part] = value
            else:
                # Dive into the nested dictionaries, creating them if necessary
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

    return unflattened_dict

def array_without_value(arr: list, value: any) -> list:
    """Return given array without a given value.

    Args:
    ----
        arr (list): Input array
        value (any): Value to ignore

    Returns:
    -------
        list: Output array

    """
    return [x for x in arr if x != value]


def single_tool_to_search_json(json: str | dict) -> dict:
    """
    Convert the JSON of a single tool into the JSON format returned by a search.
    """
    
    # Early quit if it's already processed
    if 'count' in json:
        return json
    
    return {
        "count": 1,
        "next": None,
        "previous": None,
        "list": [
            json,
        ],
    }


def sanity_check_json(input: dict) -> bool:
    """
    Sanity check tool JSON. Returns false if correct.
    """
    required = ['name', 'biotoolsID']
    
    if input == {} or input == []:
        return True
    
    for r in required:
        if r not in input or not isinstance(r, str) or r is None:
            return True
    
    
    
    return False

