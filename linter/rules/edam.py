from __future__ import annotations

import csv
import logging
import os
import sys

from message import Level, Message

from .url import req_session

initialized: bool = False
# Dictionary whether class ID is obselete
is_obsolete_dict: dict[str, bool] = {}
not_recommended_dict: dict[str, bool] = {}
deprication_comment_dict: dict[str, str] = {}
label_dict: dict[str, str] = {}

def initialize() -> None:
    """Initialize EDAM filter."""
    if initialized:
        return

    if not os.path.exists("EDAM.csv"):
        logging.info("Downloading EDAM definition")

        definition = req_session.get("https://edamontology.org/EDAM.csv")
        if not definition.ok:
            logging.exception("Unable to download EDAM definition (https://edamontology.org/EDAM.csv)")
            sys.exit(1)

        with open("EDAM.csv", "w") as f:
            f.write(definition.text)
            f.close()

    # Parse into usable data format
    with open("EDAM.csv") as csv_file:
        csv_reader = csv.reader(csv_file)
        next(csv_reader, None)  # skip the headers

        # printing data line by line
        for line in csv_reader:
            if line is None:
                continue

            class_id = line[0]
            label = line[1]
            obsolete = line[4] == "TRUE"
            obsolete_comment = line[11]
            not_recommended = line[75]

            is_obsolete_dict[class_id] = obsolete
            label_dict[class_id] = label
            deprication_comment_dict[class_id] = obsolete_comment
            not_recommended_dict[class_id] = not_recommended

def filter_edam(key: str, value: str) -> list[Message] | None:
    reports = []

    if value in is_obsolete_dict:
        if is_obsolete_dict[value]:
            reports.append(
                Message(
                    "EDAM_OBSOLETE",
                    f"EDAM {label_dict[value]} at {key} is obsolete. ({deprication_comment_dict[value]})",
                    key,
                    Level.ReportMedium))
        elif not_recommended_dict[value]:
                reports.append(
                    Message(
                        "EDAM_NOT_RECOMMENDED",
                        f"EDAM {label_dict[value]} at {key} is not recommended.",
                        key,
                        Level.ReportLow))
    else:
        reports.append(
            Message(
                "EDAM_INVALID",
                f"EDAM {value} at {key} is not a valid class ID.",
                key,
                Level.ReportMedium))

    # TODO(3top1a) make sure term is not high level (output: Data, input: Data)
    # TODO(3top1a) make sure term is in correct key (data -!> operation)

    if reports == []:
        return None
    return reports
