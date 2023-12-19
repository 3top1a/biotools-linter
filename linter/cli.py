#!/usr/bin/env python3
"""A rule-based checker for bio.tools tools."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from queue import Queue

import colorlog
from db import DatabaseConnection
from lib import Session

REPORT = 15


def configure_logging(color: bool, log_level: str) -> None:
    """Configure logging.

    Args:
    ----
        color (bool): Show colors or not
        log_level (int): What level to log
    """
    logging.addLevelName(REPORT, "REPORT")
    logging.basicConfig(level=log_level, force=True)
    if color:
        log_format = (
            "%(log_color)s%(asctime)s %(name)s %(levelname)s %(filename)s@%(lineno)d - %(message)s"
            if log_level == "DEBUG"
            else "%(log_color)s%(message)s"
        )
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
        log_format = (
            "%(asctime)s %(name)s %(levelname)s %(filename)s@%(lineno)d - %(message)s"
            if log_level == "DEBUG"
            else "%(levelname)s%(message)s"
        )
        formatter = logging.Formatter(log_format)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.removeHandler(root_logger.handlers[0])
        root_logger.addHandler(console_handler)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments. Hard exits when arguments are not valid.

    Args:
    ----
        arguments (Sequence[str]): Input argument sequence

    Returns:
    -------
        argparse.Namespace: Output arguments
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "name",
        help="Specify the name of the tool. Use '-' to read names of multiple tools from stdin.",
        nargs="?",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "REPORT", "WARNING", "ERROR"],
        default="REPORT",
        help="Choose the logging level. 'REPORT' is the default.",
    )
    parser.add_argument(
        "--db",
        default=None,
        required=False,
        help="Provide the database connection string in the format: postgres://username:passwd@IP/database. Alternatively, set this using the DATABASE_URL environment variable.",
    )
    parser.add_argument(
        "--lint-all",
        action="store_true",
        help="Enable this option to lint all tools available in the biotools API.",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Enable this option to treat the input as an exact name of the tool, bypassing the search functionality.",
    )
    parser.add_argument(
        "--page",
        "-p",
        default=1,
        type=int,
        help="Set the page number for search results. The default value is 1.",
    )
    parser.add_argument(
        "--threads",
        default=4,
        type=int,
        help="Determine the number of concurrent threads for linting. For example, using 8 threads allows 8 tools to be linted simultaneously. The default setting is 4 threads.",
    )
    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Enable this option to make the program exit with error code 1 if any errors are encountered during execution.",
    )
    parser.add_argument(
        "--no-color",
        action="store_false",
        help="Disable colored output in the console. By default, colored output is enabled.",
    )

    args = parser.parse_args(arguments)

    # Check for correct arguments
    # Require name or --lint-all
    if args.name is None and args.lint_all is False:
        logging.critical("Please specify tools name or pass in --lint-all")
        sys.exit(1)

    # Require page > 0
    if args.page is not None and args.page <= 0:
        logging.critical("Please specify a valid page (pages start from 1)")
        sys.exit(1)

    return args


def main(argv: Sequence[str]) -> int:
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
    args: argparse.Namespace = parse_arguments(argv)

    exit_on_error: str = args.exit_on_error
    database_credentials: str = (
        os.environ["DATABASE_URL"] if "DATABASE_URL" in os.environ else args.db
    )
    lint_all: str = args.lint_all
    threads: int = args.threads
    tool_name: str = args.name
    exact: str = args.exact
    page: int = args.page

    # Configure logging
    configure_logging(args.no_color, args.log_level)

    session = Session()
    db = DatabaseConnection(database_credentials, database_credentials is None)
    message_queue = Queue()
    returned_at_least_one_error: bool = False

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
                db.drop_rows_with_tool_name(name)

            session.lint_all_tools(return_q=message_queue, threads=threads)
            page += 10
            returned_at_least_one_error = db.insert_from_queue(message_queue)

            db.commit()
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
            db.drop_rows_with_tool_name(name)

        session.lint_all_tools(return_q=message_queue, threads=threads)
        returned_at_least_one_error = db.insert_from_queue(message_queue)

        db.commit()

    db.close()

    if session.next_page_exists():
        logging.info(f"You can also search the next page (page {int(page) + 1})")
    if session.previous_page_exists():
        logging.info(f"You can also search the previous page (page {int(page) - 1})")

    if returned_at_least_one_error and exit_on_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
