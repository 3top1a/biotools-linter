"""A script to generate statistics for the server."""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys

import lib
import psycopg2
from psycopg2.extensions import parse_dsn

ERROR_TYPES = [
    "URL_INVALID",
    "URL_PERMANENT_REDIRECT",
    "URL_BAD_STATUS",
    "URL_NO_SSL",
    "URL_UNUSED_SSL",
    "URL_TIMEOUT",
    "URL_SSL_ERROR",
    "URL_CONN_ERROR",
    "URL_LINTER_ERROR",
    "EDAM_OBSOLETE",
    "EDAM_NOT_RECOMMENDED",
    "EDAM_INVALID",
    "EDAM_GENERIC",
    "DOI_BUT_NOT_PMID",
    "DOI_BUT_NOT_PMCID",
    "PMID_BUT_NOT_DOI",
    "PMCID_BUT_NOT_DOI",
    "URL_TOO_MANY_REDIRECTS",
]

SEVERITY_LEVELS = {
    "LinterError": 2,
    "ReportHigh": 5,
    "ReportMedium": 6,
    "ReportLow": 7,
    "ReportCritical": 8,
}

def main() -> int:
    logging.basicConfig(force=True, level="INFO")
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.removeHandler(root_logger.handlers[0])
    root_logger.addHandler(console_handler)

    if len(sys.argv) != 2:
        logging.critical("Please specify output file. Must exist and cannot be blank, only empty JSON.")
        logging.critical("Usage: python linter/statistics.py ~/data.json")
        return 1
    output_file = sys.argv[1]

    if not os.path.exists(output_file):
        with open(output_file, "w") as file:
            file.write('{"data": []}')

    time = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    # Connect to DB
    database_creds = os.environ["DATABASE_URL"]
    export_db_connection = psycopg2.connect(**parse_dsn(database_creds))
    cursor = export_db_connection.cursor()

    # Get the total tools on biotools
    session = lib.Session()
    session.search_api("*", 1)
    total_count_on_biotools = session.json["*"]["count"]
    logging.info(f"Total on biotools: {total_count_on_biotools}")

    # Get total errors
    cursor.execute("SELECT COUNT(*) FROM messages")
    total_errors = cursor.fetchone()[0]
    logging.info(f"Total errors in DB: {total_errors}")

    # Get total unique tools names
    cursor.execute("SELECT COUNT(DISTINCT tool) FROM messages")
    unique_tools = cursor.fetchone()[0]
    logging.info(f"Unique tools in DB: {unique_tools}")

    # Count each error
    def count_error(e: str) -> int:
        cursor.execute("SELECT COUNT(*) FROM messages where code = %s", (e, ))
        return cursor.fetchone()[0]

    # Count each severity
    def count_severity(e: str) -> int:
        cursor.execute("SELECT COUNT(*) FROM messages where level = %s", (e, ))
        return cursor.fetchone()[0]

    # Get error codes
    error_code_and_count_dict = {}
    for code in ERROR_TYPES:
        error_code_and_count_dict[code] = count_error(code)
        logging.info(f"{code}: {error_code_and_count_dict[code]}")

    # Get severity
    for sev_id_dict in SEVERITY_LEVELS:
        SEVERITY_LEVELS[sev_id_dict] = count_severity(SEVERITY_LEVELS[sev_id_dict])
        logging.info(f"{sev_id_dict}: {SEVERITY_LEVELS[sev_id_dict]}")

    with open(output_file) as json_file:
        data = json.load(json_file)

    new_data_entry = {
        "time": time,
        "total_count_on_biotools": total_count_on_biotools,
        "total_errors": total_errors,
        "unique_tools": unique_tools,
        "error_types": error_code_and_count_dict,
        "severity": SEVERITY_LEVELS,
    }
    data["data"].append(new_data_entry)

    # Step 3: Save the updated data back to the JSON file
    with open(output_file, "w") as json_file:
        json.dump(data, json_file, indent=2)

    logging.info("Appended to the json file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
