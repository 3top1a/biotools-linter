#!/usr/bin/env python3
"""A rule-based checker for bio.tools tools."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
import os
import sys
from collections.abc import Sequence
from queue import Queue

import colorlog
from db import DatabaseConnection
from lib import Session, single_tool_to_search_json
from utils import unflatten_json_from_single_dict

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
        help="Database connection details in the format postgres://username:passwd@IP/database. Alternatively, set this using the DATABASE_URL environment variable, however this argument overwrites it.",
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
        "--json",
        action="store_true",
        help="Reads tool JSON from STDIN and analyzes it.",
    )
    parser.add_argument(
        "--biotools-format",
        action="store_true",
        help="JSON mode output mimics the output from bio.tools validation API.",
    )
    parser.add_argument(
        "--page",
        "-p",
        default=1,
        type=int,
        help="Set the page number for search results. The default value is 1.",
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
    if args.name is None and args.lint_all is False and args.json is False:
        logging.critical(
            "Please specify tools name, pass in --lint-all or --json to continue.")
        sys.exit(1)

    # Require page > 0
    if args.page is not None and args.page <= 0:
        logging.critical("Please specify a valid page (pages start from 1)")
        sys.exit(1)

    return args


async def main(argv: Sequence[str]) -> int:
    """Execute the main functionality of the tool.

    Attributes
    ----------
        arguments (dict): A dictionary containing command-line arguments.

    Returns
    -------
        int: Status code. 0 means success, non zero values signify failiure.

    Raises
    ------
        None

    """
    args: argparse.Namespace = parse_arguments(argv)
    database_credentials: str | None = (
        args.db if args.db is not None else (
            os.environ.get("DATABASE_URL", None))
    )

    # Configure logging
    configure_logging(args.no_color, args.log_level)

    session = Session()
    db = DatabaseConnection(
        database_credentials, database_credentials is None or not database_credentials or database_credentials == "ignore")
    message_queue = Queue()
    returned_at_least_one_error: bool = False

    # Start linting, switch modes
    if args.json:
        input_json = "\n".join(sys.stdin.readlines())
        json_data = {"x": single_tool_to_search_json(json.loads(input_json))}
        session = Session(json_data)

        if session.get_total_tool_count() != 1:
            logging.critical("Could not load JSON.")
            return 1

        for tool in session.return_tool_list_json():
            name = tool["biotoolsID"]
            if name is None:
                logging.critical("Could not load JSON.")
                return 1
            db.drop_rows_with_tool_name(name)

        await session.lint_all_tools(return_q=message_queue)
        json_queue = Queue()
        json_queue.queue = copy.deepcopy(message_queue.queue)
        returned_at_least_one_error = db.insert_from_queue(message_queue)

        json_list = []
        while json_queue.qsize() != 0:
            json_list.append(json_queue.get())
        json_list = [x.__dict__ for x in json_list if x.code != "LINT-F"]

        if args.biotools_format:
            # Mimic the way the bio.tools validate API works
            if json_list == []:
                print(input_json)
            else:
                errors = {}
                for error in json_list:
                    slug = error['code']
                    if slug in ["PMCID_BUT_NOT_DOI", "PMID_BUT_NOT_DOI", "DOI_BUT_NOT_PMCID", "DOI_BUT_NOT_PMID", "PMCID_BUT_NOT_PMID"]:
                        slug = "PMID,_PMCID_and_DOI_conversion"
                    if slug in ["PMID_DISCREPANCY", "PMCID_DISCREPANCY", "DOI_DISCREPANCY"]:
                        slug = "PMID,_PMCID_and_DOI_discrepancy"
                    error_docs_url = f"https://biotools-linter.biodata.ceitec.cz/docs#{slug}"
                    errors.update(unflatten_json_from_single_dict(
                        {error["location"].split("//")[1]: [f'{error["body"]} <a href="{error_docs_url}">More info.</a>']},
                    ))

                print(json.dumps(errors))
        else:
            print(json.dumps(json_list))

        db.commit()

    elif args.lint_all:
        # Try to lint all tools on bio.tools
        page = args.page if args.page else 1
        processed_tools = 10 * (page - 1)

        session.search_api("*", page)
        count = session.json["*"]["count"]
        logging.info(f"Linting {count} tools")

        while session.next_args.page_exists() or page == 1:
            # Dump cache so it doesn't OOM
            session.clear_cache()

            session.search_api_multiple_pages("*", page, page + 10)
            processed_tools += 10
            logging.info(
                f"Page: {page} => {page + 10}, Progress: {processed_tools / count}%",
            )

            # Delete old entries from table
            for tool in session.return_tool_list_json():
                name = tool["biotoolsID"]
                db.drop_rows_with_tool_name(name)

            await session.lint_all_tools(return_q=message_queue)
            page += 10
            returned_at_least_one_error = db.insert_from_queue(message_queue)

            db.commit()
    else:
        # Lint specific tools(s)
        if args.name == "-":
            # Pipe from stdin
            for line in sys.stdin:
                if line.strip() != "":
                    session.search_api(line.strip(), args.page)
        elif args.exact:
            session.search_api_exact_match(args.name)
        else:
            session.search_api(args.name, args.page)

        count = session.get_total_tool_count()

        if count == 0:
            logging.critical(f"Found {count} tools, exiting")
            return 1

        logging.info(f"Found {count} tools")

        # Delete old entries from table
        for tool in session.return_tool_list_json():
            name = tool["biotoolsID"]
            db.drop_rows_with_tool_name(name)

        await session.lint_all_tools(return_q=message_queue)
        returned_at_least_one_error = db.insert_from_queue(message_queue)

        db.commit()

    db.close()

    if session.next_page_exists():
        logging.info(
            f"You can also search the next page (page {int(args.page) + 1})")
    if session.previous_page_exists():
        logging.info(
            f"You can also search the previous page (page {int(args.page) - 1})")

    if returned_at_least_one_error and args.exit_on_error:
        return 254
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
