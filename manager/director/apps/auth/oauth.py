# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, List, Optional, cast

from social_core.backends.oauth import BaseOAuth2
from social_core.pipeline.user import get_username as social_get_username
from social_core.strategy import BaseStrategy


def get_username(
    strategy: BaseStrategy, details: Dict[str, Any], *args: Any, user=None, **kwargs: Any
) -> Optional[Dict[str, str]]:
    result = social_get_username(strategy, details, user=user, *args, **kwargs)
    return cast(Optional[Dict[str, str]], result)


class IonOauth2(BaseOAuth2):  # pylint: disable=abstract-method
    name = "ion"
    AUTHORIZATION_URL = "https://ion.tjhsst.edu/oauth/authorize"
    ACCESS_TOKEN_URL = "https://ion.tjhsst.edu/oauth/token"
    ACCESS_TOKEN_METHOD = "POST"
    EXTRA_DATA = [("refresh_token", "refresh_token", True), ("expires_in", "expires")]

    def get_scope(self) -> List[str]:
        return ["read"]

    def get_user_details(self, response: Dict[str, Any]) -> Dict[str, Any]:
        profile = self.get_json(
            "https://ion.tjhsst.edu/api/profile", params={"access_token": response["access_token"]}
        )
        # fields used to populate/update User model
        data = {
            key: profile[key]
            for key in (
                "first_name", "last_name", "id", "is_student", "is_teacher", "graduation_year",
            )
        }
        data["username"] = profile["ion_username"]
        data["email"] = profile["tj_email"]
        return data

    def get_user_id(self, details: Dict[str, Any], response: Any) -> int:
        return cast(int, details["id"])
