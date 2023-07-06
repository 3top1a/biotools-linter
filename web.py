from flask import Flask, jsonify, session, request, render_template
from lib import Session
from json import JSONEncoder

# Custom encoder to encode Session objects
class SessionJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Session):
            # Serialize your custom session object here
            # For example, you can convert it to a dictionary
            return obj.to_dict()
        return super().default(obj)


app = Flask(__name__, static_folder='website')
app.secret_key = 'your_secret_key'  # Change this to a secret key of your choice
app.json_encoder = SessionJSONEncoder  # Use the custom JSONEncoder

@app.route("/heartbeat")
def heartbeat():
    return jsonify({"status": "healthy"})


@app.route("/search", methods=['POST'])
def search():
    if not 's' in session:
        session['s'] = Session()
    
    s: Session = Session(**session['s'])

    query = request.json['q']
    page = request.json['page']
    s.page = page

    s.search_api(query, page = page)

    list = s.return_project_list()

    t = 'single' if len(list) == 1 else 'list'

    output = ""
    for p in list:
        link = f"https://bio.tools/{p['biotoolsID']}"
        output += render_template("listing_template.html", name=p['name'], link=link)
    
    output = {
        'type': t, # `single` - one project; `list` - multiple
        'len': len(list),
        'next': s.next_page_exists(),
        'previous': s.previous_page_exists(),
        'page': s.page,
        'o': output
    }
    return jsonify(output)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    if not 's' in session:
        session['s'] = Session()
    return app.send_static_file("index.html")


if __name__ == '__main__':
    app.run(debug=True)
