from sys import argv
import requests
import re
import logging

# Constants
URL_REGEX = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

urls_already_checked = []

# Get target tool name
assert len(argv) == 2, "Program needs tool name as first argument"
tool_name = argv[1]

# Get JSON from biotools API
url = f"https://bio.tools/api/t/?q={tool_name}&format=json"
response = requests.get(url)
response.raise_for_status()  # Check if the request was successful
data = response.json()

# Main filter function
def filter_dict(key, value):
    logging.debug(key + ": ", value)

    # Check if URL is not 200
    if re.match(URL_REGEX, value):
        # Filter already checked URLs
        if value not in urls_already_checked:
            print("URL: " + value)

            response = requests.get(url)
            if response.status_code != 200:
                logging.warn(f"{value} in {key} doesn't returns 200 (HTTP_OK)")
                print(f"{value} in {key} doesn't returns 200 (HTTP_OK)")
            
            urls_already_checked.append(value)



# Recursively extract values from JSON and call filter on them
def flatten_json(json_data, parent_key='', separator='.'):

    if isinstance(json_data, list):
        for x in json_data:
            index = json_data.index(x)

            flatten_json(x, f"{parent_key}/{index}")
    elif isinstance(json_data, dict):
        for key, value in json_data.items():
            flatten_json(value, f"{parent_key}/{key}")
    else:
        if json_data == None:
            json_data = "null"

        filter_dict(parent_key, str(json_data))

flatten_json(data)
