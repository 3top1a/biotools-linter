#!/usr/bin/env python3

"""A rule-based checker for bio.tools tools 
"""

import argparse
import json
import logging
import os
import queue
import sys
import threading
from datetime import datetime, timezone

import colorlog
from flask import Flask, jsonify, render_template, request, session
from flask_socketio import SocketIO

from lib import Session


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Session):
            return vars(obj)

        # default, if not Delivery object. Caller's problem if this is not serialziable.
        return json.JSONEncoder.default(self, obj)


# Configure app
app = Flask(__name__, static_folder='website')
app.secret_key = os.urandom(24)  # Random secret key
socketio = SocketIO(app)


def validate_input(func):
    def wrapper(*args, **kwargs):
        if 'bioid' in request.args:
            bioid = request.args.get('bioid')
            if not bioid:
                return 'BioID parameter is missing.', 400
            elif not isinstance(bioid, str):
                return 'Invalid data type for name parameter.', 400
            elif len(bioid) > 100:
                return 'BioID parameter exceeds the maximum length limit of 100 characters.', 400

        if 'q' in request.args:
            q = request.args.get('q')
            if not q:
                return 'query (q) parameter is missing.', 400
            elif not isinstance(q, str):
                return 'Invalid data type for query parameter.', 400
            elif len(q) > 100:
                return 'q parameter exceeds the maximum length limit of 100 characters.', 400

        if 'page' in request.args:
            page = request.args.get('page')
            if not isinstance(page, int):
                return 'Invalid data type for page parameter.', 400

        return func(*args, **kwargs)
    return wrapper


@app.route("/search", methods=['POST'])
@validate_input
def search():
    """
    Route: /search
    Method: POST

    Endpoint for performing a search.

    Parameters:
    - q: The search query
    - page: The page number

    Returns:
    - JSON response containing search results information.
    """
    try:

        if 's' not in session:
            session['s'] = Encoder().encode(Session())

        s: Session = Session(**json.loads(session['s']))

        query = request.json['q']
        page = request.json['page']
        s.page = page

        s.search_api(query, page=page)

        list = s.return_project_list_json()

        t = 'single' if len(list) == 1 else 'list'

        output = ""
        for p in list:
            link = f"https://bio.tools/{p['biotoolsID']}"
            output += render_template("listing_template.html",
                                      name=p['name'], link=link, id=p['biotoolsID'])

        output = {
            'type': t,  # `single` - one project; `list` - multiple
            'len': len(list),
            'next': s.next_page_exists(),
            'previous': s.previous_page_exists(),
            'page': s.page,
            'o': output
        }
        return jsonify(output)
    except Exception as e:
        logging.error(e)
        return f"Error: {e}", 400


@app.route("/lint", methods=['POST'])
def lint_project():
    """
    Route: /lint
    Method: POST

    Endpoint for linting a specific project.
    Assumes requested project exists

    Parameters:
    - bioid: The project to lint

    Returns:
    - JSON response indicating the status of the linting process.
    """
    try:
        if 's' not in session:
            session['s'] = Encoder().encode(Session())

        s: Session = Session(**json.loads(session['s']))

        bioid = request.json['bioid']

        s.search_api(bioid)

        if 'next' in s.json:
            return jsonify({'error': 'inconclusive search'}), 400

        q = queue.Queue()
        s.lint_specific_project(s.json, q)
        # session['q'] = q

        socketio.emit('lint_report', {
            "text": "Starting linting",
            "time": datetime.now(timezone.utc).strftime("UTC %H:%M:%S"),
            "level": 'debug'
        })

        # Setup queue callback
        def message_receiver(message_channel):
            while True:
                message = message_channel.get()  # Blocks until a new message is received

                if message == "Finished linting":
                    socketio.emit('lint_report', {
                        "text": "Finished linting",
                        "time": datetime.now(timezone.utc).strftime("UTC %H:%M:%S"),
                        "level": 'debug'
                    })
                    return

                # Get the current timestamp
                timestamp = datetime.now(timezone.utc)

                # Format the timestamp
                formatted_timestamp = timestamp.strftime("%H:%M:%SUTC")

                # Add some info to the message
                m = {
                    "text": message,
                    "time": formatted_timestamp
                }

                socketio.emit('lint_report', m)
        receiver_thread = threading.Thread(target=message_receiver, args=[q])
        receiver_thread.start()

        return jsonify({'status': 'success'})
    except Exception as e:
        logging.error(e)
        return f"Error: {e}", 400


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    """
    Route: / or any path not previously defined
    Method: GET

    Catch-all route for serving static files or fallback to index.html.

    Parameters:
    - path: The requested path, not used

    Returns:
    - Always returns the content of index.html
    """
    if 's' not in session:
        session['s'] = Encoder().encode(Session())
    return app.send_static_file("index.html")


if __name__ == '__main__':
    # Configure logging
    logging.addLevelName(15, 'REPORT')
    logging.basicConfig(level=15, force=True)
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(message)s',
        log_colors={
            'DEBUG': 'thin',
            'INFO': 'reset',
            'REPORT': 'bold_green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red'
        },
        reset=True,
        style='%'
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
    parser.add_argument('--debug', '-d', action='store_true',
                        help="Debug flag for server")
    parser.add_argument('--port', '-p', default=8080, type=int,
                        help="Web port")
    parser.add_argument('--host', default="127.0.0.1",
                        help="The IP or hostname the server listens to")
    args = parser.parse_args(sys.argv[1:])
    port = args.port
    debug = args.debug
    host = args.host

    socketio.run(app, port=port, debug=debug, host=host)
