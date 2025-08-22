"""Fuzzing tests"""

import copy
import logging

import pytest
from lib import Session
from utils import single_tool_to_search_json

SCHEMA = {
    "name": "MSMC",
    "description": "This software implements MSMC, a method to infer population size and gene flow from multiple genome sequences.",
    "homepage": "https://github.com/stschiff/msmc",
    "biotoolsID": "msmc",
    "biotoolsCURIE": "biotools:msmc",
    "version": ["2.0"],
    "otherID": [
        {
            "value": "MSMC2",
            "type": "Other",
            "version": "2.0",
        },
    ],
    "function": [
        {
            "operation": [
                {
                    "uri": "http://edamontology.org/operation_0324",
                    "term": "Phylogenetic tree analysis",
                },
            ],
            "input": [
                {
                    "data": {
                        "uri": "http://edamontology.org/data_0863",
                        "term": "Genomic sequences",
                    },
                    "format": [
                        {
                            "uri": "http://edamontology.org/format_1929",
                            "term": "FASTA",
                        },
                    ],
                },
            ],
            "output": [
                {
                    "data": {
                        "uri": "http://edamontology.org/data_0863",
                        "term": "Phylogenetic tree",
                    },
                    "format": [
                        {
                            "uri": "http://edamontology.org/format_1929",
                            "term": "Newick",
                        },
                    ],
                },
            ],
            "note": "Useful for analyzing sequence data.",
            "cmd": "msmc2",
        },
    ],
    "toolType": ["Command-line tool"],
    "topic": [
        {
            "uri": "http://edamontology.org/topic_0194",
            "term": "Phylogenomics",
        },
    ],
    "operatingSystem": ["Linux", "Mac"],
    "language": ["D"],
    "license": "GPL-3.0",
    "collectionID": ["Animal and Crop Genomics"],
    "documentation": [
        {
            "url": "https://github.com/stschiff/msmc/blob/master/guide.md",
            "type": ["General"],
            "note": "Comprehensive guide",
        },
    ],
    "publication": [
        {
            "doi": "10.1038/ng.3015",
            "type": ["Primary"],
            "note": "Original MSMC publication.",
            "version": "1.0",
            "metadata": {
                "title": "Inferring human population size and separation history from multiple genome sequences",
                "abstract": "",
                "date": "2014-01-01T00:00:00Z",
                "citationCount": 612,
                "journal": "Nature Genetics",
            },
        },
    ],
    "download": [
        {
            "url": "https://github.com/stschiff/msmc/releases",
            "type": "Source code",
            "note": "Latest source code",
            "version": "2.0",
        },
    ],
    "link": [
        {
            "url": "https://github.com/stschiff/msmc/issues",
            "type": ["Issue tracker"],
            "note": "Report issues here",
        },
    ],
    "relation": [
        {
            "biotoolsID": "relatedToolID",
            "type": "isSimilarTo",
        },
    ],
    "credit": [
        {
            "name": "Stephan Schiffels",
            "orcidid": "0000-0002-1553-5323",
            "email": "stephan.schiffels@mpi-inf.mpg.de",
            "typeEntity": "Person",
            "typeRole": ["Developer", "Maintainer"],
            "note": "Main developer of MSMC",
        },
    ],
    "labels": {
        "maturity": "Stable",
        "cost": "Free",
        "accessibility": ["OpenAccess"],
        "elixirNode": ["Germany"],
        "elixirCommunity": ["Computational biology"],
        "elixirPlatform": ["Data"],
    },
    "owner": "root",
    "additionDate": "2024-03-16T13:49:37.059450Z",
    "lastUpdate": "2024-03-16T13:49:37.078403Z",
    "editPermission": {
        "type": "private",
    },
    "validated": 0,
    "homepage_status": 0,
    "elixir_badge": 0,
}


# Check if the linter crashes
async def check(json):
    json_data = {"x": single_tool_to_search_json(json)}
    session = Session(json_data)
    session.get_total_tool_count()
    session.return_tool_list_json()
    await session.lint_all_tools(return_q=None)


def remove_elements(input_dict, collected_dicts=None, path=None):
    """Recursively navigates through a given dictionary, creating variations of it by removing
    one key at a time, including keys from nested dictionaries. Each modified dictionary is
    collected along with the path of removal.

    Parameters
    ----------
    - input_dict (dict): The original dictionary from which keys will be removed.
    - collected_dicts (list, optional): A list to collect tuples of modified dictionaries and their
      removal paths. This parameter is primarily used internally by recursive calls.
    - path (list, optional): The current path of keys leading to the current dictionary being processed.
      This parameter is used internally by recursive calls to track the nesting path.

    Returns
    -------
    - list: A list of tuples, where each tuple contains a modified dictionary and the path of keys
      leading to the removed key. This enables tracking not only the variations but also how each
      variation was achieved.

    """
    if collected_dicts is None:
        collected_dicts = []
    if path is None:
        path = []

    for key in list(input_dict.keys()):
        # Work on a copy to preserve original dictionary
        temp_dict = copy.deepcopy(input_dict)

        # Remove the current key
        del temp_dict[key]

        # Store the modified dictionary
        new_path = [*path, key]
        collected_dicts.append((temp_dict, new_path))

        # If the value is another dictionary, recurse
        if isinstance(input_dict[key], dict):
            remove_elements(input_dict[key], collected_dicts, new_path)

    return collected_dicts


def replace_values(input_dict, value):
    """Recursively navigates through a given JSON-like dictionary, replacing all values with `None`
    for non-dictionary values, and with an empty list `[]` for dictionary values that are emptied.

    Parameters
    ----------
    - input_dict (dict): The JSON-like dictionary whose values are to be replaced.
    - value (any): The new values of the JSON

    Returns
    -------
    - dict: A modified version of the input dictionary with all values replaced as described.

    Note:
    - The function directly modifies the input dictionary. If you need to preserve the original
      dictionary, consider passing a copy of the dictionary to this function.
    - This implementation replaces non-dictionary values with `None` and dictionary values with
      `[]` if they become empty as a result of the recursion. Adjustments can be made based on
      specific needs for differentiating between replaced values.

    """
    for key in input_dict.keys():
        if isinstance(input_dict[key], dict):
            # If the value is a dictionary, recurse and then check if it's empty
            input_dict[key] = replace_values(input_dict[key], value)
            if not input_dict[
                key
            ]:  # If the dictionary is now empty, replace it with []
                input_dict[key] = []
        else:
            # Replace non-dictionary values with None
            input_dict[key] = None
    return input_dict


@pytest.mark.asyncio()
async def test_remove_elements():

    # Remove elements
    for new_json, x in remove_elements(SCHEMA):
        logging.info(f"Removing {x}")
        await check(new_json)


@pytest.mark.asyncio()
async def test_replace_values():
    for x in [None, [], {}]:
        logging.info(f"Replacing all values with {x}")
        new_json = replace_values(SCHEMA, x)

        new_json["name"] = "name"
        new_json["biotoolsID"] = "biotoolsID"

        await check(new_json)
