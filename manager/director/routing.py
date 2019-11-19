from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

from django.urls import path

from director.apps.sites.consumers import SiteConsumer

application = ProtocolTypeRouter(
    {
        "websocket": AuthMiddlewareStack(
            URLRouter(
                [
                    # URLRouter just takes standard Django path() or url() entries.
                    path("sites/<int:site_id>/", SiteConsumer),
                ]
            )
        )
    }
)
