########
Overview
########

Director is built out of several parts that play different roles
in the grand scheme of things.

- The Manager is responsible for the director website.
- The Orchestrator is responsible for the staticfiles and docker builds
  for user websites.
- The Router is responsible for routing traffic to the orchestrator.
- The Shell runs an ssh server using ``AsyncSSH`` to communicate with the Manager.

-------
Manager
-------

The Manager is a "typical" Django application - it's responsible for the UI
a TJ student would see when on director.

It uses Django Channels to handle websocket connections, and Celery to handle
long running tasks (e.g. creating sites). Effectively, it's the frontend of director.
It's where the database models for :class:`.Site` and :class:`.Operation` are located.

------------
Orchestrator
------------

The Orchestrator is a Flask application that handles a lot of Nginx's configuration
for individual user sites. You will often find the manager making requests to
``"/sites/<int:site_id>/something"`` - that's the orchestrator (specifically the nginx
blueprint).
Most often, these requests are things like changing the Nginx configuration,
updating Docker containers, or something similar.

It also uses a Websocket server for long running tasks.

It uses Nginx to serve static files and route incoming requests to the correct port
per site. To do this, it uses Docker to actually serve the site.

------
Router
------



