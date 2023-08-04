#!/usr/bin/env python3

"""A rule-based checker for bio.tools tools."""

import argparse
import logging
import sys
from collections.abc import Sequence

import colorlog
from lib import Session

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
    parser.add_argument("name", help="Tool name")
    parser.add_argument("--log-level", "-l",
                        choices=["DEBUG", "INFO", "REPORT", "WARNING", "ERROR"],
                        default="REPORT",
                        help="Set the logging level (default: INFO)")
    parser.add_argument("--page", "-p", default=1, type=int,
                        help="Sets the page of the search")
    args = parser.parse_args(arguments)
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

    session = Session()
    session.search_api(tool_name, page)
    count = session.total_project_count()
    logging.info(f"Found {count} projects")
    session.lint_all_projects()

    if session.next_page_exists():
        logging.info(
            f"You can also search the next page (page {int(page) + 1})")
    if session.previous_page_exists():
        logging.info(
            f"You can also search the previous page (page {int(page) - 1})")


if __name__ == "__main__":
    main(sys.argv[1:])
