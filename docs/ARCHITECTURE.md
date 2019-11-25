# Architecture

Note: This is written as if it is completed and working, but currently a lot of it is not. As a result, this is all subject to change.

## Manager

The manager runs a Django web application. It uses Channels to handle websockets opened by the client, and Celery to perform potentially long-running tasks. Examples of long-running tasks include creating sites or editing parts of sites that require backend changes.

## Orchestrator

The orchestrator runs Nginx to serve static files and route incoming requests to the appropriate ports for each site. It uses Docker to actually serve the sites.

It also runs a Flask application that handles updating Nginx's configuration and create/manage Docker containers upon requests from the manager.

## Router

The router runs HAProxy to forward requests to the orchestrator(s), as well as a small Flask application to update HAProxy's configuration upon requests from the manager.
