# Architecture

Note: This is written as if it is completed and working, but currently a lot of it is not. As a result, this is all subject to change.

## Manager

The manager runs a Django web application. It uses Channels to handle websockets opened by the client, and Celery to perform potentially long-running tasks. Examples of long-running tasks include creating sites or editing parts of sites that require backend changes.

## Orchestrator

The orchestrator runs Nginx to serve static files and route incoming requests to the appropriate ports for each site. It uses Docker to actually serve the sites.

It also runs a Flask application that handles updating Nginx's configuration, creating/updating Docker containers, etc. upon requests from the manager, as well as a Websocket server to handle interactive/long-running tasks.

## Router

The router runs Nginx to forward requests to the orchestrator(s), as well as a small Flask application to update Nginx's configuration and generate Let's Encrypt certificates upon requests from the manager.

## Shell

The shell server runs an SSH server using AsyncSSH. It communicates with the mamager

## Communication between servers

Frequently, one component needs to be able to make HTTP/Websocket requests to another component for various reasons. What follows is a list of all the types of access that may be required.

- The manager should be able to make requests to all URLs on the orchestrator's Flask server.
- The manager should be able to make requests to all URLs on the orchestrator's Websocket server.
- The manager should be able to make requests to all URLs on the router's Flask server.
- The shell server should be able to make requests to all URLs with the prefix `/shell-server/` on the manager. No other client, especially regular web browsers, should be allowed to make requests to these URLs.
- The shell server should be able to make requests to all URLs with the prefix `/ws/shell-server/` on the orchestrator's Websocket server. It should not be allowed to make any other requests to the orchestrator or the router.

Note: These restrictions are not enforced by Director 4.0 itself. Instead, each component with an HTTP server should be behind a load balancer that enforces access restrictions.
