# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging

from flask import Flask, jsonify, redirect, request, url_for

# from flask_cors import CORS

try:
    from secret import *
except ValueError:
    pass

app = Flask(__name__)

# CORS(app)


@app.route("/")
def index_page():
    return "Hello World!!"


if __name__ == "__main__":
    app.run()
