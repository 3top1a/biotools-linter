"""EDAMontology rules, learn more at `https://edamontology.org/page`."""

from __future__ import annotations

import csv
import logging
import os
import sys

import owlready2
from message import Level, Message

from .url import req_session


class EdamFilter:
    def __init__(self: EdamFilter) -> None:
        """Initialize EDAM filter. Returns early if already initialized."""
        # Simple dicts, replace?
        self.is_obsolete_dict: dict[str, bool] = {}
        self.not_recommended_dict: dict[str, bool] = {}
        self.deprecation_comment_dict: dict[str, str] = {}
        self.label_dict: dict[str, str] = {}
        self.ontology = None

        self.download_file("EDAM.csv", "https://edamontology.org/EDAM.csv")
        self.download_file("EDAM.owl", "https://edamontology.org/EDAM.owl")

        self.parse_csv("EDAM.csv")
        self.load_ontology("EDAM.owl")

    def download_file(self: EdamFilter, filename: str, url: str) -> None:
        """Download file helper."""
        if not os.path.exists(filename):
            logging.info(f"Downloading {filename}")
            response = req_session.get(url)
            if not response.ok:
                logging.exception(f"Unable to download {url}")
                sys.exit(1)
            with open(filename, "w") as file:
                file.write(response.text)

    def parse_csv(self, filename):
        with open(filename) as csv_file:
            csv_reader = csv.reader(csv_file)
            next(csv_reader, None)  # skip the headers
            for line in csv_reader:
                if line:
                    class_id, label, obsolete, obsolete_comment, not_recommended = (
                        line[0], line[1], line[4] == "TRUE", line[11], line[75])
                    self.is_obsolete_dict[class_id] = obsolete
                    self.label_dict[class_id] = label
                    self.deprecation_comment_dict[class_id] = obsolete_comment
                    self.not_recommended_dict[class_id] = not_recommended

    def load_ontology(self: EdamFilter, filename: str):
        self.ontology = owlready2.get_ontology(filename).load()

    def filter_edam(self: EdamFilter, key: str, value: str) -> list[Message] | None:
        reports = []

        if value in self.is_obsolete_dict:
            if self.is_obsolete_dict[value]:
                reports.append(
                    Message(
                        "EDAM_OBSOLETE",
                        f'EDAM "{self.label_dict[value]}" at {key} is obsolete. ({self.deprecation_comment_dict[value]})',
                        key,
                        Level.ReportMedium))
            elif self.not_recommended_dict[value]:
                    reports.append(
                        Message(
                            "EDAM_NOT_RECOMMENDED",
                            f'EDAM "{self.label_dict[value]}" at {key} is not recommended for usage.',
                            key,
                            Level.ReportLow))
        else:
            reports.append(
                Message(
                    "EDAM_INVALID",
                    f"EDAM {value} at {key} is not a valid class ID.",
                    key,
                    Level.ReportMedium))

        high_level = ["http://edamontology.org/data_0006", "http://edamontology.org/format_1915", "http://edamontology.org/operation_0004", "http://edamontology.org/topic_0003"]

        # make sure term is not high level (output: Data, input: Data)
        # Maybe rewrite?
        if value in high_level:
            reports.append(
                Message(
                    "EDAM_GENERIC",
                    f'EDAM "{self.label_dict[value]}" at {key} is too generic, consider filling in a more specific value.',
                    key,
                    Level.ReportMedium))

        # TODO(3top1a): make sure term is in correct key (data -!> operation)

        if reports == []:
            return None
        return reports

edam_filter = EdamFilter()
