

def flatten_json_to_single_dict(
    json_data: dict, parent_key: str = "", separator: str = "/",
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
