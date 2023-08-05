#!/usr/bin/env python3
"""A rule-based checker for bio.tools tools."""

import argparse
import logging
import os
from queue import Queue
import sys
from collections.abc import Sequence

import colorlog
from lib import Session
from message import Message

REPORT = 15


def main(arguments: Sequence[str]) -> None:
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
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "REPORT", "WARNING", "ERROR"],
        default="REPORT",
        help="Set the logging level (default: REPORT)")
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
        "How many threads to use when linting, eg. 8 threads will lint 8 projects at the same time"
    )
    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Return error code 1 if there are any errors found")

    # Name is not required if we are linting all
    if not parser.parse_args(arguments).lint_all:
        parser.add_argument("name",
                            help="Tool name")
        tool_name = parser.parse_args(arguments).args.name


    args = parser.parse_args(arguments)
    exit_on_error = args.exit_on_error
    lint_all = args.lint_all
    threads = args.threads
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

    session = Session()
    return_queue = Queue()

    if lint_all:
        page = 1
        while session.next_page_exists() or page == 1:
            session.search_api("*", page)
            count = session.total_project_count()
            logging.info(f"Found {count} projects on page {page}")
            session.lint_all_projects(return_q=return_queue, threads=threads)
            page += 1
    else:
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

    if session.next_page_exists():
        logging.info(
            f"You can also search the next page (page {int(page) + 1})")
    if session.previous_page_exists():
        logging.info(
            f"You can also search the previous page (page {int(page) - 1})")

    if returned_atleast_one_error and exit_on_error:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
