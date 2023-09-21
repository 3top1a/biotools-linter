"""A file to generate statistics for the server."""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys

import lib
import psycopg2
from psycopg2.extensions import parse_dsn


def main():
    logging.basicConfig(force=True, level="INFO")
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.removeHandler(root_logger.handlers[0])
    root_logger.addHandler(console_handler)

    if len(sys.argv) != 2:
        logging.critical("Please specify output file")
        return
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

    URL_INVALID = count_error("URL_INVALID")
    URL_PERMANENT_REDIRECT = count_error("URL_PERMANENT_REDIRECT")
    URL_BAD_STATUS = count_error("URL_BAD_STATUS")
    URL_NO_SSL = count_error("URL_NO_SSL")
    URL_UNUSED_SSL = count_error("URL_UNUSED_SSL")
    URL_TIMEOUT = count_error("URL_TIMEOUT")
    URL_SSL_ERROR = count_error("URL_SSL_ERROR")
    URL_CONN_ERROR = count_error("URL_CONN_ERROR")
    URL_LINTER_ERROR = count_error("URL_LINTER_ERROR")
    EDAM_OBSOLETE = count_error("EDAM_OBSOLETE")
    EDAM_NOT_RECOMMENDED = count_error("EDAM_NOT_RECOMMENDED")
    EDAM_INVALID = count_error("EDAM_INVALID")
    EDAM_GENERIC = count_error("EDAM_GENERIC")

    logging.info(
        "%d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d",
        URL_INVALID,
        URL_PERMANENT_REDIRECT,
        URL_BAD_STATUS,
        URL_NO_SSL,
        URL_UNUSED_SSL,
        URL_TIMEOUT,
        URL_SSL_ERROR,
        URL_CONN_ERROR,
        URL_LINTER_ERROR,
        EDAM_OBSOLETE,
        EDAM_NOT_RECOMMENDED,
        EDAM_INVALID,
        EDAM_GENERIC,
    )

    with open(output_file) as json_file:
        data = json.load(json_file)

    new_data_entry = {
        "time": time,
        "total_count_on_biotools": total_count_on_biotools,
        "total_errors": total_errors,
        "unique_tools": unique_tools,
        "error_types": {
            "URL_INVALID": URL_INVALID,
            "URL_PERMANENT_REDIRECT": URL_PERMANENT_REDIRECT,
            "URL_BAD_STATUS": URL_BAD_STATUS,
            "URL_NO_SSL": URL_NO_SSL,
            "URL_UNUSED_SSL": URL_UNUSED_SSL,
            "URL_TIMEOUT": URL_TIMEOUT,
            "URL_SSL_ERROR": URL_SSL_ERROR,
            "URL_CONN_ERROR": URL_CONN_ERROR,
            "URL_LINTER_ERROR": URL_LINTER_ERROR,
            "EDAM_OBSOLETE": EDAM_OBSOLETE,
            "EDAM_NOT_RECOMMENDED": EDAM_NOT_RECOMMENDED,
            "EDAM_INVALID": EDAM_INVALID,
            "EDAM_GENERIC": EDAM_GENERIC,
        },
    }
    data["data"].append(new_data_entry)

    # Step 3: Save the updated data back to the JSON file
    with open(output_file, "w") as json_file:
        json.dump(data, json_file, indent=2)

    logging.info("Appended to the json file")


if __name__ == "__main__":
    main()
