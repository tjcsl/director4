################
Router and Shell
################

If you haven't read :doc:`orchestrator` and :doc:`manager`,
it's recommended to read those first to get an idea of how
the router especially fits into the big picture.

Router
------
Each part of Director serves a purpose: the manager for the frontend,
the orchestrator for editing configs, and so on. The job of the
router is much like an internet router: it is supposed to forward
Nginx requests to the orchestrator. Additionally, it also
is responsible for generating *Let's Encrypt* certificates if
requested by the manager.

To be more specific, each :class:`.Site` has a custom nginx config stored in a separate
file (``site-{side-id}.conf`` at the time of writing). The router is responsible for managing
this file, making sure it is valid, and reloading nginx as needed.
This may be a little bit confusing because the Orchestrator also has a per-site Nginx config.
However, this nginx config is NOT the same: it's used to reroute requests to the orchestrator
app servers, and are stored in a different location then the orchestrators ``site-{site-id}.conf``.


