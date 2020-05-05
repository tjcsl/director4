# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors
import traceback
from typing import Tuple, Union

from flask import Blueprint, current_app

from ....docker.registry import get_registry_images
from ..exceptions import OrchestratorActionError

api = Blueprint("api", __name__)


@api.route("/registry/api/images", method=["GET"])
def get_registry_images_page() -> Union[str, Tuple[str, int]]:
    """Returns Docker registry images.

    Returns in JSON format.
    """

    try:
        images = get_registry_images()
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return str(images)
