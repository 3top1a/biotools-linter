#!/usr/bin/env python3
"""A rule-based checker for bio.tools tools."""

import argparse
import logging
import sys
import os
from collections.abc import Sequence
from queue import Queue
from typing import TYPE_CHECKING

import colorlog
import psycopg2
from lib import Session

if TYPE_CHECKING:
    from message import Message

REPORT = 15


def main(arguments: Sequence[str]) -> int:
    """Execute the main functionality of the tool.

    Attributes
    ----------
        arguments (dict): A dictionary containing command-line arguments.

    Returns
    -------
        None

    Raises
    ------
        None

    """
    # Configure parser
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="Tool name", nargs="?")
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "REPORT", "WARNING", "ERROR"],
        default="REPORT",
        help="Set the logging level (default: REPORT)")
    parser.add_argument("--db",
                        default=None,
                        required=False,
                        help="Database connection (host:port:database:user:password). Can also be in DB_CREDS variable")
    parser.add_argument(
        "--lint-all",
        action="store_true",
        help="Lint all available projects returned by the biotools API")
    parser.add_argument("--page",
                        "-p",
                        default=1,
                        type=int,
                        help="Sets the page of the search")
    parser.add_argument(
        "--threads",
        default=4,
        type=int,
        help=
        "How many threads to use when linting, eg. 8 threads will lint 8 projects at the same time",
    )
    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Return error code 1 if there are any errors found")

    args = parser.parse_args(arguments)
    exit_on_error = args.exit_on_error
    database_creds = args.db if args.db else os.environ["DB_CREDS"]
    lint_all = args.lint_all
    threads = args.threads
    tool_name = args.name
    page = args.page

    # Configure logging
    logging.addLevelName(REPORT, "REPORT")
    logging.basicConfig(level=args.log_level, force=True)
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(message)s",
        log_colors={
            "DEBUG": "thin",
            "INFO": "reset",
            "REPORT": "bold_green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
        reset=True,
        style="%",
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.removeHandler(root_logger.handlers[0])
    root_logger.addHandler(console_handler)

    # Require name or --lint-all
    if tool_name is None and lint_all is False:
        logging.critical("Please specify tools name or pass in --lint-all")
        sys.exit(1)

    session = Session()
    return_queue = Queue()

    # Initialize exporting, create table if it doesn't exist
    export_db_connection = None
    export_db_cursor = None

    if database_creds:
        export_db_connection = psycopg2.connect(
            host=database_creds.split(":")[0],
            port=database_creds.split(":")[1],
            database=database_creds.split(":")[2],
            user=database_creds.split(":")[3],
            password=database_creds.split(":")[4],
            )
        export_db_cursor = export_db_connection.cursor()

        # Create table
        create_table_query = "CREATE TABLE IF NOT EXISTS messages ( id SERIAL PRIMARY KEY, project TEXT, code TEXT, body TEXT UNIQUE );"
        export_db_cursor.execute(create_table_query)

    # Start linting loop
    if lint_all:
        # Try to lint all projects on bio.tools
        page = 1
        while session.next_page_exists() or page == 1:
            session.search_api("*", page)
            count = session.total_project_count()
            logging.info(f"Found {count} projects on page {page}")
            session.lint_all_projects(return_q=return_queue, threads=threads)
            page += 1
    else:
        # Lint specific project(s)
        session.search_api(tool_name, page)
        count = session.total_project_count()
        logging.info(f"Found {count} projects")
        session.lint_all_projects(return_q=return_queue, threads=threads)

    # Convert queue to list
    returned_atleast_one_error: bool = False
    while not return_queue.empty():
        item: Message = return_queue.get()
        if item.level == 1 and not returned_atleast_one_error:
            returned_atleast_one_error = True

        # Export
        if database_creds and item.level == 1:
            insert_query = "INSERT INTO messages (project, code, body) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;"
            # Replace 'data' with your actual data variables
            data = (item.project, item.code, item.body)
            export_db_cursor.execute(insert_query, data)

    if export_db_connection:
        export_db_connection.commit()
        export_db_connection.close()

    if session.next_page_exists():
        logging.info(
            f"You can also search the next page (page {int(page) + 1})")
    if session.previous_page_exists():
        logging.info(
            f"You can also search the previous page (page {int(page) - 1})")

    if returned_atleast_one_error and exit_on_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
