# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

# import logging
import json

from flask import Flask, request  # , jsonify, redirect, url_for

from .configs.nginx import update_nginx_config
from .containers.containers import demo_main

# from flask_cors import CORS

app = Flask(__name__)

# CORS(app)


@app.route("/")
def index_page():
    return "Hello World!!"


@app.route("/ping")
def ping_page():
    return "{}\n".format(request.args.get("message", "Pong"))


@app.route("/sites/<int:site_id>/update-nginx")
def update_nginx_page(site_id: int):
    if "data" not in request.args:
        return "Error", 400

    try:
        result = update_nginx_config(site_id, json.loads(request.args["data"]))
    except BaseException:  # pylint: disable=broad-except
        return "Error", 500
    else:
        if result is None:
            return "Success"
        else:
            return result, 500


@app.route("/check-port/<int:port>")
def check_port_page():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("", 8081))
            sock.listen(0)
    except OSError:
        return "ERR"
    else:
        return ""


@app.route("/demo", methods=["GET", "POST"])
def demo_page():
    return str(demo_main())


if __name__ == "__main__":
    app.run()
