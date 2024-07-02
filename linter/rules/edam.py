"""EDAMontology rules, learn more at `https://edamontology.org/page`."""

from __future__ import annotations

import csv
import logging
import os
import sys

import owlready2
import requests
from message import Level, Message
from utils import flatten_json_to_single_dict


class EdamFilter:
    ontology: owlready2.Ontology
    
    is_obsolete_dict: dict[str, bool]
    not_recommended_dict: dict[str, str]
    deprecation_comment_dict: dict[str, str]
    label_dict: dict[str, str]
    
    def __init__(self: EdamFilter) -> None:
        """Initialize EDAM filter. Returns early if already initialized. Parses local files if they are already downloaded, otherwise downloads them."""
        # Simple dicts, replace?
        self.is_obsolete_dict: dict[str, bool] = {}
        self.not_recommended_dict: dict[str, str] = {}
        self.deprecation_comment_dict: dict[str, str] = {}
        self.label_dict: dict[str, str] = {}
        
        self.download_file("EDAM.csv", "https://edamontology.org/EDAM.csv")
        self.download_file("EDAM.owl", "https://edamontology.org/EDAM.owl")

        self.parse_csv("EDAM.csv")
        self.ontology = owlready2.get_ontology("EDAM.owl").load()

    def download_file(self: EdamFilter, filename: str, url: str) -> None:
        """Download file helper."""
        if not os.path.exists(filename):
            logging.info(f"Downloading {filename}")
            response = requests.get(url)
            if not response.ok:
                logging.exception(f"Unable to download {url}")
                sys.exit(1)
            with open(filename, "w") as file:
                file.write(response.text)

    def parse_csv(self: EdamFilter, filename: str) -> None:
        """Parse EDAM CSV.

        Args:
        ----
            filename (str): CSV file location

        """
        with open(filename) as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                class_id = row['Class ID']
                self.label_dict[class_id] = row['Preferred Label']
                self.is_obsolete_dict[class_id] = row['Obsolete'] == "TRUE"
                self.deprecation_comment_dict[class_id] = row['deprecation_comment']
                self.not_recommended_dict[class_id] = row['notRecommendedForAnnotation']

    async def filter_edam_key_value_pair(
        self: EdamFilter,
        key: str,
        value: str,
    ) -> list[Message] | None:
        """Filter for EDAM terms.

        Args:
        ----
            key (str): JSON key, e.g. `msmc//topic/0/uri`
            value (str): JSON value, e.g. `http://edamontology.org/operation_0324`

        Returns:
        -------
            list[Message] | None: Found errors

        """
        reports = []

        if value in self.is_obsolete_dict:
            if self.is_obsolete_dict[value]:
                reports.append(
                    Message(
                        "EDAM_OBSOLETE",
                        f'The term "{self.label_dict[value]}" at {key} has been marked as obsolete',
                        key,
                        Level.ReportMedium,
                    ),
                )
            elif self.not_recommended_dict[value]:
                reports.append(
                    Message(
                        "EDAM_NOT_RECOMMENDED",
                        f'The term "{self.label_dict[value]}" at {key} is no longer advised for use.',
                        key,
                        Level.ReportLow,
                    ),
                )
        else:
            reports.append(
                Message(
                    "EDAM_INVALID",
                    f'Specified term {value} at {key} not recognized in the EDAM ontology',
                    key,
                    Level.ReportMedium,
                ),
            )

        if reports == []:
            return None
        return reports

    def get_class_from_uri(self: EdamFilter, uri: str) -> owlready2.ThingClass | None:
        """Extract a class from the given ontology based on a URI.

        This function parses the URI to extract the class name and then retrieves
        the corresponding class from the provided ontology. It only processes URIs
        that contain '://edamontology.org/'.

        Arguments:
        ---------
        uri (str): The URI from which to extract the class name.

        Returns:
        -------
        owlready2.ThingClass | None: The ontology class if found, otherwise None.

        """
        if "://edamontology.org/" in uri:
            class_name = uri.split("/")[-1]
            return self.ontology[class_name]
        return None

    def check_topics(
        self: EdamFilter,
        edam_class: owlready2.ThingClass,
        json_topics: list,
        location: str,
    ) -> list[Message]:
        """Generate reports for a given class based on its topics compared against a list of JSON topics.

        This function checks if the topics associated with a given EDAM class (from its `is_a` attribute)
        are present in the provided list of JSON topics. It generates a report for each topic that
        is present in the class but not in the JSON topics.

        Arguments:
        ---------
        edam_class (ThingClass): The ontology class to check for topics.
        json_topics (list): A list of topics (in dict format) to compare against.
        location (str): JSON location.

        Returns:
        -------
        list[Message]: A list of Message objects representing the reports, empty if no discrepancies are found.

        """
        reports = []

        json_topic_uris = {x["uri"].split("/")[-1] for x in json_topics}

        for edam_property in edam_class.is_a:
            if not hasattr(edam_property, "property"):
                continue

            # TODO Replace with has_topic from CSV
            if edam_property.property == self.ontology["has_topic"]:
                topic_name = edam_property.value.name
                if topic_name not in json_topic_uris:
                    property_uri = f"http://edamontology.org/{edam_property.value.name}"
                    parent_uri = f"http://edamontology.org/{edam_class.name}"
                    reports.append(
                        Message(
                            "EDAM_TOPIC_DISCREPANCY",
                            #f"EDAM {self.label_dict[parent_uri]} ({parent_uri}) has topic {self.label_dict[property_uri]} ({property_uri}) but not in tool annotation.",
                            # TODO: add links to edam viewer in all edam related errors
                            f'Operation {self.label_dict[parent_uri]} expects topic {self.label_dict[property_uri]}.',
                            location,
                            Level.ReportMedium,
                        ),
                    )
        return reports

    def check_operation(
        self: EdamFilter,
        edam_class: owlready2.ThingClass,
        operations_json: list,
        location: str,
    ) -> list[Message]:
        reports = []

        # Combines inputs and outputs of all operations and flattens the 2d arrays

        json_inputs = sum([x["input"] if "input" in x else [] for x in operations_json], [])
        json_outputs = sum([x["output"] if "output" in x else [] for x in operations_json], [])

        for edam_property in edam_class.is_a:
            if not hasattr(edam_property, "property"):
                continue

            if edam_property.property == self.ontology["has_input"]:
                if edam_property.value not in json_inputs:
                    parent_uri = f"http://edamontology.org/{edam_class.name}"
                    property_uri = f"http://edamontology.org/{edam_property.value.name}"
                    reports.append(
                        Message(
                            "EDAM_INPUT_DISCREPANCY",
                            #f"EDAM operation {self.label_dict[parent_uri]} ({parent_uri}) has input {self.label_dict[property_uri]} ({property_uri}) but not in tool annotation.",
                            f'Operation {self.label_dict[parent_uri]} expects input {self.label_dict[property_uri]}.',
                            location,
                            Level.ReportMedium,
                        ),
                    )
            if edam_property.property == self.ontology["has_output"]:
                if edam_property.value not in json_outputs:
                    parent_uri = f"http://edamontology.org/{edam_class.name}"
                    property_uri = f"http://edamontology.org/{edam_property.value.name}"
                    reports.append(
                        Message(
                            "EDAM_OUTPUT_DISCREPANCY",
                            f"EDAM operation {self.label_dict[parent_uri]} ({parent_uri}) has output {self.label_dict[property_uri]} ({property_uri}) but not in tool annotation.",
                            location,
                            Level.ReportMedium,
                        ),
                    )

        # input_or_output is here just for grammar sake, don't want to say it;s in the output when it's in the input
        for (output, input_or_output) in zip(json_outputs + json_inputs, ['output']*len(json_outputs) + ['input']*len(json_inputs)):
            # This code validates that each specified format in the output data includes a 'format' dictionary which is appropriately restricted by its 'is_format_of' attribute
            if "data" in output and "format" in output:
                # Check is_format_of restriction in every format
                restrictions = []
                for format in output['format']:
                    cls = self.get_class_from_uri(format['uri'])
                    new_restrictions = [x.is_format_of if hasattr(x, "is_format_of") else [] for x in cls.ancestors()]
                    new_restrictions = [item for sublist in new_restrictions for item in sublist] # flatten list, e.g. [EDAM.data_2968]
                    restrictions.extend(new_restrictions)
                
                if restrictions == []:
                    continue

                # Check if there is atleast one format with the same daat
                data = self.get_class_from_uri(output['data']['uri'])
                expected_outputs = "/".join([self.label_dict[r.iri] for r in restrictions]) # e.g. `Image`
                operation_name = self.label_dict[edam_class.iri]
                if not data in restrictions:
                    reports.append(
                        Message(
                            "EDAM_FORMAT_DISCREPANCY",
                            f"Expected {input_or_output} {expected_outputs} because of the format of the operation {operation_name}.",
                            location,
                            Level.ReportMedium,
                        ),
                    )

        return reports

    async def filter_whole_json(self: EdamFilter, json: dict) -> list[Message] | None:
        logging.debug("checking EDAM")
        reports = []

        pairs = flatten_json_to_single_dict(json, parent_key=json["name"] + "/")

        if not 'function' in json or not json['function']:
            return None

        # Check for specific attributes in EDAM classes that are not present in
        # the tools annotations, e.g. It has EDAM.operation_2403 which has topic EDAM.topic_0080
        # however that is not present in the tools topics
        for function in json['function']:
            for operation in function['operation']:
                edam_class = self.get_class_from_uri(operation['uri'])
                location = [(x,y) for (x,y) in pairs.items() if y == operation['uri']][0][0]
                if edam_class:
                    if "topic" in json:
                        reports.extend(self.check_topics(edam_class, json["topic"], location))
                    if "function" in json:
                        reports.extend(self.check_operation(edam_class, json["function"], location))

        if reports == []:
            return None
        return reports


edam_filter = EdamFilter()
