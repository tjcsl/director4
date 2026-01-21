############
Orchestrator
############

The orchestrator is responsible for the
high-level Nginx commands, as well as managing the docker containers.

If you have not yet read :doc:`manager`, you should probably read that first.

Nginx
-----
The Orchestrator manages it's own Nginx config to deal
with incoming requests at ``site-{site-id}.conf``. This config is
separate from the router's Nginx config, so we'll spend a moment talking
about some features and how the Orchestrator works with it.

If the website type is ``static``, the Nginx config is where the files in ``/public``
are served from:

.. code-block:: nginx

   server {
      # ...

      location / {
        root site_dir/public;
      }
   }

Note that Jinja is used for turning a template into a functional Nginx configuration.
The data to populate the template is NOT from the orchestrator, but rather from
a request from the Manager to the Orchestrator. Importantly, the Manager can send a
post request with the field ``custom_nginx_config`` to inject any other nginx configuration
needed.

When updating the Nginx config, the orchestrator first moves the old configuration into
``site-{site-id}.conf.bak``. Only if that succeeds will it write the new configuration.

Hosting a website
-----------------
When creating a site, the manager sends a request to the orchestrator to generate a ``nginx.conf``
configuration, which is then moved to ``/data/nginx/director.d/``. The ``nginx.conf`` running the balancer
has a line that looks like::

  include /data/nginx/director.d/*.conf

This is the magic line that actually hosts the sites on the internet.
