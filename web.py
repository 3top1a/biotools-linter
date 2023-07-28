#!/usr/bin/env python3
"""A rule-based checker for bio.tools tools."""

import argparse
import logging
import os
import queue
import sys
from typing import TYPE_CHECKING

import colorlog
from flask import Flask, Response, jsonify, render_template, request, session

from lib import Session

if TYPE_CHECKING:
    from message import Message

# Configure app
app = Flask(__name__, static_folder="website")
app.secret_key = os.urandom(24)  # Random secret key


@app.route("/search/<path:path>")
def serve_search(path: str) -> Response:
    """Serve search path."""
    if "s" not in session:
        session["s"] = vars(Session())
    s: Session = Session(session["s"])

    if path == "" or path is None:
        return render_template("error.html",
                               error="Please input a valid name"), 400

    page = request.args.get("page", default=1, type=int)
    if page < 1:
        return render_template("error.html", error="Invalid page"), 400

    s.search_api(path, page)

    project_list = s.return_project_list_json()

    search_output_html = ""
    for p in project_list:
        link = f"https://bio.tools/{p['biotoolsID']}"
        search_output_html += render_template("listing_template.html",
                                              name=p["name"],
                                              link=link,
                                              id=p["biotoolsID"])

    can_next = s.next_page_exists()
    can_previous = s.previous_page_exists()
    count = s.total_project_count()

    logging.debug(f"Requested search for {path}")
    return render_template("search.html",
                           name=path,
                           page=page,
                           can_next=can_next,
                           can_previous=can_previous,
                           output_html=search_output_html,
                           count=count)


@app.route("/lint/<path:path>")
def serve_lint(path: str) -> Response:
    """Serve lint path."""
    if "s" not in session:
        session["s"] = vars(Session())
    logging.debug(f"Requested lint of {path}")

    s: Session = Session(session["s"])
    s.search_api(path)

    if "next" in s.json:
        return render_template("error.html", error="Inconclusive search"), 400

    q = queue.Queue()
    for name in s.return_project_list_json():
        s.lint_specific_project(name, q)

    output_html = ""
    lints_complete = 0
    while True:
        message: Message = q.get()  # Blocks until a new message is received

        if message.code == "LINT-F":
            lints_complete += 1
            output_html += render_template("message.html",
                                        text=message.body,
                                        level=message.level.value)
            if lints_complete == s.total_project_count():
                break
            else:
                continue

        output_html += render_template("message.html",
                                       text=message.message_to_string(),
                                       level=message.level.value)

    return render_template("lint.html", output_html=output_html)


@app.route("/api/<path:path>")
def serve_lint_api(path: str) -> Response:
    """Serve API lint path."""
    if "s" not in session:
        session["s"] = vars(Session())
    logging.debug(f"Requested API lint of {path}")

    s: Session = Session(session["s"])
    s.search_api(path)

    if "next" in s.json:
        return jsonify({"error": "Inconclusive search"}), 400

    q = queue.Queue()
    s.lint_specific_project(s.json, q)

    messages = []
    while True:
        message: Message = q.get()  # Blocks until a new message is received

        if message.code == "LINT-F":
            break

        messages.append(message.message_to_json())

    return jsonify({"messages": messages})


@app.route("/")
def serve_index() -> Response:
    """Serve index."""
    if "s" not in session:
        session["s"] = vars(Session())
    logging.debug("Requested index")
    return render_template("index.html")


if __name__ == "__main__":
    # Configure logging
    logging.addLevelName(15, "REPORT")
    logging.basicConfig(level=15, force=True)
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

    # Configure parser
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--debug",
                        "-d",
                        action="store_true",
                        help="Debug flag for server")
    parser.add_argument("--port",
                        "-p",
                        default=8080,
                        type=int,
                        help="Web port")
    parser.add_argument("--host",
                        default="127.0.0.1",
                        help="The IP or hostname the server listens to")
    args = parser.parse_args(sys.argv[1:])
    port: int = args.port
    debug: bool = args.debug
    host: str = args.host

    if debug:
        app.run(port=port, debug=debug, host=host)
    else:
        from waitress import serve
        serve(app, port=port, host=host)
