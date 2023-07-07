from flask import Flask, jsonify, session, request, render_template
from lib import Session
from json import JSONEncoder
import os
import queue
from flask_socketio import SocketIO
import threading
from datetime import datetime, timezone
import logging
import colorlog

class SessionJSONEncoder(JSONEncoder):
    # Custom encoder to encode Session objects
    def default(self, obj):
        if isinstance(obj, Session):
            # Serialize your custom session object here
            # For example, you can convert it to a dictionary
            return obj.to_dict()
        return super().default(obj)

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


# Configure app
app = Flask(__name__, static_folder='website')
app.secret_key = os.urandom(24)  # Random secret key
app.json_encoder = SessionJSONEncoder  # Use the custom JSONEncoder
socketio = SocketIO(app)

@app.route("/search", methods=['POST'])
def search():
    if 's' not in session:
        session['s'] = Session()

    s: Session = Session(session['s']['page'], session['s']['json'])

    query = request.json['q']
    page = request.json['page']
    s.page = page

    s.search_api(query, page=page)

    list = s.return_project_list()

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

@app.route("/lint", methods=['POST'])
def lint():
    """
        Assumes project exists
    """
    if 's' not in session:
        session['s'] = Session()

    s: Session = Session(**session['s'])

    project = request.json['project']

    s.search_api(project)

    if 'next' in s.json:
        return jsonify({'error': 'inconclusive search'})

    q = queue.Queue()
    s.lint_specific_project(s.json, q)
    #session['q'] = q

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

@socketio.on('disconnect')
def handle_disconnect():
    #q: queue.Queue = session['q']
    #q.put("KILL_QUEUE")
    #q.empty()
    pass

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    if 's' not in session:
        session['s'] = Session()
    return app.send_static_file("index.html")


if __name__ == '__main__':
    #app.run(debug=True)
    socketio.run(app)

