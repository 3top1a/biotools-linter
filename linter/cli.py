#!/usr/bin/env python3
"""A rule-based checker for bio.tools tools."""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
from collections.abc import Sequence
from queue import Queue

import colorlog
import psycopg2
from lib import Session
from message import Level, Message
from psycopg2.extensions import parse_dsn

REPORT = 15


def db_drop_rows_with_tool_name(name: str, export_db_cursor: psycopg2.cursor) -> None:
    if export_db_cursor is None:
        return

    delete_query = "DELETE FROM messages WHERE tool = %s;"
    export_db_cursor.execute(delete_query, (name,))


def db_insert_queue_into_database(queue: Queue, sql_cursor: psycopg2.cursor | None) -> bool:
    """Insert message queue into database.

    Args:
    ----
        queue (Queue): Queue
        sql_cursor (psycopg2.cursor | None): SQL database cursor

    Returns:
    -------
        bool (bool): True if any messages have been received.
    """
    logging.info("Sending messages to database")

    return_value = False

    while not queue.empty():
        item: Message = queue.get()
        return_value = True

        # Export
        if sql_cursor and item.level != Level.LinterInternal:
            insert_query = "INSERT INTO messages (time, tool, code, location, text, level) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING;"
            # Replace 'data' with your actual data variables
            data = (
                int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp()),
                item.tool,
                item.code,
                item.location,
                item.body,
                int(item.level),
            )
            sql_cursor.execute(insert_query, data)

    return return_value


def configure_logging(color: bool, log_level: int) -> None:
    """Configure logging.

    Args:
    ----
        color (bool): Show colors or not
        log_level (int): What level to log
    """
    logging.addLevelName(REPORT, "REPORT")
    logging.basicConfig(level=log_level, force=True)
    if color:
        log_format = "%(log_color)s%(asctime)s %(name)s %(levelname)s %(filename)s@%(lineno)d - %(message)s" if log_level == 10 else "%(log_color)s%(message)s"
        formatter = colorlog.ColoredFormatter(
            log_format,
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
    else:
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.removeHandler(root_logger.handlers[0])
        root_logger.addHandler(console_handler)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
    ----
        arguments (Sequence[str]): Input argument sequence

    Returns:
    -------
        argparse.Namespace: Output arguments
    """
    # TODO Better argument help strings
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "name",
        help="Tool name. use `-` to read multiple tools from stdin",
        nargs="?",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "REPORT", "WARNING", "ERROR"],
        default="REPORT",
        help="Set the logging level (default: REPORT)",
    )
    parser.add_argument(
        "--db",
        default=None,
        required=False,
        help="Database connection (postgres://username:passwd@IP/database). Can also be in DATABASE_URL variable",
    )
    parser.add_argument(
        "--lint-all",
        action="store_true",
        help="Lint all tools in the biotools API",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Treat the input as an exact tool name, do not search",
    )
    parser.add_argument(
        "--page",
        "-p",
        default=1,
        type=int,
        help="Sets the page of the search",
    )
    parser.add_argument(
        "--threads",
        default=4,
        type=int,
        help="How many threads to use when linting, eg. 8 threads will lint 8 tools at the same time. Default is 4",
    )
    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Return error code 1 if there are any errors found",
    )
    parser.add_argument(
        "--no-color",
        action="store_false",
        help="Don't print colored output",
    )

    return parser.parse_args(arguments)


def main(args: Sequence[str]) -> int:
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
    args = parse_arguments(args)

    exit_on_error = args.exit_on_error
    database_credentials = (
        os.environ["DATABASE_URL"] if "DATABASE_URL" in os.environ else args.db
    )
    lint_all = args.lint_all
    threads = args.threads
    tool_name = args.name
    exact = args.exact
    page = args.page

    # Configure logging
    configure_logging(args.no_color, args.log_level)

    # Check for correct arguments
    # Require name or --lint-all
    if tool_name is None and lint_all is False:
        logging.critical("Please specify tools name or pass in --lint-all")
        return 1
    # Require page > 0
    if page <= 0:
        logging.critical("Please specify a valid page")
        return 1

    session = Session()
    message_queue = Queue()
    returned_at_least_one_error: bool = False

    # Initialize exporting, create table if it doesn't exist
    export_db_connection: psycopg2.connection | None = None
    export_db_cursor = None
    if database_credentials:
        export_db_connection = psycopg2.connect(**parse_dsn(database_credentials))
        export_db_cursor = export_db_connection.cursor()

        # Create table query
        create_table_query = "CREATE TABLE IF NOT EXISTS messages ( id SERIAL PRIMARY KEY, time BIGINT NOT NULL, tool TEXT NOT NULL, code TEXT NOT NULL, location TEXT NOT NULL, text TEXT NOT NULL, level INTEGER NOT NULL );"
        export_db_cursor.execute(create_table_query)

    # Start linting loop
    if lint_all:
        # Try to lint all tools on bio.tools
        page = page if page else 1
        processed_tools = 10 * (page - 1)

        session.search_api("*", page)
        count = session.json["*"]["count"]
        logging.info(f"Linting {count} tools")

        while session.next_page_exists() or page == 1:
            # Dump cache so it doesn't OOM
            session.clear_cache()

            session.search_api_multiple_pages("*", page, page + 10)
            processed_tools += 10
            logging.info(
                f"Page: {page} => {page + 10}, Progress: {processed_tools / count}%"
            )

            # Delete old entries from table
            for tool in session.return_tool_list_json():
                name = tool["biotoolsID"]
                db_drop_rows_with_tool_name(name, export_db_cursor)

            session.lint_all_tools(return_q=message_queue, threads=threads)
            page += 10
            returned_at_least_one_error = db_insert_queue_into_database(message_queue, export_db_cursor)
            if export_db_connection:
                export_db_connection.commit()
    else:
        # Lint specific tools(s)
        if tool_name == "-":
            # Pipe from stdin
            for line in sys.stdin:
                if line.strip() != "":
                    session.search_api(line.strip(), page)
        elif exact:
            session.search_api_exact_match(tool_name)
        else:
            session.search_api(tool_name, page)

        count = session.get_total_tool_count()

        if count == 0:
            logging.critical(f"Found {count} tools, exiting")
            return 1

        logging.info(f"Found {count} tools")

        # Delete old entries from table
        for tool in session.return_tool_list_json():
            name = tool["biotoolsID"]
            db_drop_rows_with_tool_name(name, export_db_cursor)

        session.lint_all_tools(return_q=message_queue, threads=threads)
        returned_at_least_one_error = db_insert_queue_into_database(message_queue, export_db_cursor)
        if export_db_connection:
            export_db_connection.commit()

    if export_db_connection:
        export_db_connection.commit()
        export_db_connection.close()

    if session.next_page_exists():
        logging.info(f"You can also search the next page (page {int(page) + 1})")
    if session.previous_page_exists():
        logging.info(f"You can also search the previous page (page {int(page) - 1})")

    if returned_at_least_one_error and exit_on_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
