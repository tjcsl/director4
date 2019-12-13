# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

# import logging

from flask import Flask, request  # , jsonify, redirect, url_for

from .containers.containers import demo_main

# from flask_cors import CORS

# pylint: disable=pointless-string-statement
"""
try:
    from secret import *
except ValueError:
    pass
"""

app = Flask(__name__)

# CORS(app)


@app.route("/")
def index_page():
    return "Hello World!!"


@app.route("/ping")
def ping_page():
    return "{}\n".format(request.args.get("message", "Pong"))


@app.route("/demo", methods=["GET", "POST"])
def demo_page():
    return str(demo_main())


if __name__ == "__main__":
    app.run()
