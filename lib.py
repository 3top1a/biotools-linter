import logging
import queue
from concurrent.futures import ThreadPoolExecutor

import requests

from rules import delegate_filter, reset_cache

REPORT = 15

class Session:
    page = 1
    json = []

    def __init__(self, page=1, json=[]):
        self.page = page
        self.json = json

    def to_dict(self):
        return {'page': self.page, 'json': self.json}

    def search_api(self, name, page=1):
        """
        Get JSON from biotools API
        """

        logging.debug(f"Searching API for {name}")

        # Search as if it's an exact match
        url = f"https://bio.tools/api/t/{name}?format=json"
        response = requests.get(url)
        if response.status_code == 200:
            self.json = response.json()
            return

        # Search
        url = f"https://bio.tools/api/t/?q={name}&format=json&page={str(page)}"
        response = requests.get(url)
        if response.status_code == 200:
            self.json = response.json()
            return

        logging.critical("Could not search the API")

    def return_project_list(self):
        if 'next' in self.json.keys():
            logging.info(f"Search returned {len(self.json['list'])} results")

            return self.json['list']
        else:
            return [self.json]

    def lint_specific_project(self, data_json:str, return_q: queue.Queue | None = None):
        if len(data_json) == 0:
            logging.critical("Recieved empty JSON!")
            return
        
        name = data_json['name']

        logging.info(f"Linting {name} at https://bio.tools/{data_json['biotoolsID']}")
        logging.debug(f"Project JSON returned {len(data_json)} keys")

        dictionary = flatten_json_to_single_dict(data_json, parent_key=name)

        executor = ThreadPoolExecutor()
        futures = [executor.submit(delegate_filter, key, value, return_q)
                for key, value in dictionary.items()]

        for f in futures:
            try:
                f.result()
            except Exception as e:
                logging.critical(f"Error while executing future: {e}")
        
        if return_q is not None:
            return_q.put("Finished linting")

        reset_cache()

    def lint_all_projects(self, return_q: queue.Queue | None = None):
        for project in self.return_project_list():
            self.lint_specific_project(project, return_q)

    def next_page_exists(self):
        if 'next' in self.json:
            return self.json['next'] is not None
        return False

    def previous_page_exists(self):
        if 'previous' in self.json:
            return self.json['previous'] is not None
        return False

# Utils
def flatten_json_to_single_dict(json_data, parent_key='', separator='.'):
    """
    Recursively extract values from JSON

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
        'a': 1,
        'b.alpha': 1,
        'b.beta': 2
    }
    ```


    """

    out = {}

    if isinstance(json_data, list):
        for x in json_data:
            index = json_data.index(x)

            out.update(flatten_json_to_single_dict(x, f"{parent_key}/{index}"))
    elif isinstance(json_data, dict):
        for key, value in json_data.items():
            out.update(flatten_json_to_single_dict(
                value, f"{parent_key}/{key}"))
    else:
        json_data = str(json_data)
        if json_data == "None":
            json_data = None
        out.update({parent_key: json_data})

    return out
