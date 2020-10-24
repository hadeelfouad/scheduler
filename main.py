import os
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from controllers import api

app = Flask(__name__)
app.register_blueprint(api, url_prefix='/api')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get("MAX_CONTENT_LENGTH", 1024*1024))

@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        return jsonify(error=e.description), e.code
    return jsonify(error=str(e)), code


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
