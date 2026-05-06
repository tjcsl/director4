# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging
import logging.handlers

from flask import Flask, request

from . import settings
from .views.database import database_blueprint
from .views.docker import docker_blueprint
from .views.files import files as files_blueprint
from .views.nginx import nginx as nginx_blueprint

app = Flask(__name__)
app.register_blueprint(docker_blueprint)
app.register_blueprint(files_blueprint)
app.register_blueprint(nginx_blueprint)
app.register_blueprint(database_blueprint)

app.config.update(settings.FLASK_CONFIG)


def _copy_logger_handlers(target_logger: logging.Logger, source_logger: logging.Logger) -> None:
    existing_handler_ids = {id(handler) for handler in target_logger.handlers}
    for handler in source_logger.handlers:
        if id(handler) not in existing_handler_ids:
            target_logger.addHandler(handler)
            existing_handler_ids.add(id(handler))


if settings.LOG_FILE is not None:
    file_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=settings.LOG_FILE_ROTATE_SIZE,
        backupCount=settings.LOG_FILE_MAX_BACKUPS,
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-8s]: %(message)s"))
    file_handler.setLevel(settings.LOG_LEVEL)

    app.logger.addHandler(file_handler)  # pylint: disable=no-member
else:
    gunicorn_error_logger = logging.getLogger("gunicorn.error")
    if gunicorn_error_logger.handlers:
        app.logger.handlers = gunicorn_error_logger.handlers  # pylint: disable=no-member
        app.logger.setLevel(gunicorn_error_logger.level)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-8s]: %(message)s"))
        stream_handler.setLevel(settings.LOG_LEVEL)
        app.logger.addHandler(stream_handler)  # pylint: disable=no-member
        app.logger.setLevel(settings.LOG_LEVEL)

gunicorn_access_logger = logging.getLogger("gunicorn.access")
if gunicorn_access_logger.handlers:
    _copy_logger_handlers(app.logger, gunicorn_access_logger)  # pylint: disable=no-member
    app.logger.setLevel(min(app.logger.level, gunicorn_access_logger.level))

app.logger.propagate = False  # pylint: disable=no-member


@app.route("/ping")
def ping_page() -> str:
    """Checks whether the orchestrator is functional.

    Returns a provided message or else "Pong".
    """

    return request.args.get("message", "Pong")


if __name__ == "__main__":
    app.run()
