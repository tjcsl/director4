########
Overview
########

Director is built out of several parts that play different roles
in the grand scheme of things.

However, Director also requires a bit more prerequisite knowledge than basic Django and Flask skills (although those
are also neccessary). We'll talk a little bit about those first.

-------------
Prerequisites
-------------

.. note::

  The following is not meant to be a comprehensive guide, but rather a brief overview of the concepts.
  If you're interested in learning more, there are plenty of resources available online.


Web Requests: An Overview
~~~~~~~~~~~~~~~~~~~~~~~~~
You want to access a website. You type in the URL, hit enter, and the website appears.
How? When you hit enter, your browser sends a request to the server hosting the website.
The request goes through several layers of software before a response with the html/css/js
is received.

#. The request is first received by a server running a load balancer.
   The load balancer forwards the request to a server that can handle it.
   This way no one server is overloaded with requests while another is doing nothing.

   .. hint::

      `Nginx <https://www.nginx.com/>`_ is a commonly used load balancer, and the one used for Director sites.


#. A WSGI (or ASGI for async programs) server receives the request. WSGI is a standard specification for Python web servers
   to communicate with web applications. It basically translates the request into a format that the web server can understand.
   Common WSGI server implementations are `gunicorn <https://gunicorn.org/>`_ and `uwsgi <https://uwsgi-docs.readthedocs.io/en/latest/>`_,
   and these are often referred to as "application servers".
#. The web server (which is something like Django or Flask) processes the request, and communicates with the database.
   It then sends a response back to the server.
#. The server sends the response back to the load balancer.
#. The load balancer sends the response back to your browser.
#. The browser renders the response and displays the website.

We haven't mentioned caching above, and that's because there are several different caches!

.. note::

  The way that requests are cached isn't relevant, but we mention them for completeness
  (and because it's cool).

* Browser cache: The browser stores a copy of the (typically static) website so it doesn't have to send a request again.
  This is more common with static websites that don't change often, and is why if you reload too much and then change some CSS
  the site may not reflect the CSS change (Hard refresh with Ctrl+Shift+R fixes it).
* CDNs: Content Delivery Networks (CDNs) are services that cache static files (most commonly javascript and css) and serve them from a server
  closer to you. This reduces latency and speeds up the website.
* Server cache: This happens at a load balancer level, and can involve things like fragment caching (caching parts of a page),
  and object caching for the database.

  .. tip::

    Nginx can actually use caching to deliver stale content if fresh content isn't
    avaliable from the origin servers (``proxy_cache_use_stale``). This provides some extra fault tolerance.

Director puts each site behind a load balancer, using Nginx. As you explore the Orchestrator, you'll see the exact
Nginx configuration that is used.


Docker Swarm
~~~~~~~~~~~~
Director is able to handle different dependencies per site by using Docker containers
or each site. In order to manage these containers, Director uses Docker Swarm. Before we
start, lets talk a little bit about Docker.

- A *Docker Image* is a package with all the dependencies in an application.
- A *Docker Container* is an instance of a Docker Image that has been given a CPU and RAM to run.
  These containers are portable across all systems with Docker installed.

A ``Dockerfile`` is a set of instructions that tells Docker how to build an image. You start by pulling ``FROM``
a base image, and then you can ``RUN`` commands to install dependencies, ``COPY`` files into the container, and more.

Docker Swarm allows you to orchestrate multiple Docker containers. It does this by having two types of nodes:

- *Manager Nodes* are responsible for managing the swarm, and scheduling tasks.
- *Worker Nodes* are responsible for running the tasks. It is these nodes that run each container for each site.

Docker swarm makes it easier to do stuff like load balancing, managing multiple nodes (called clusters), and much more.
If you're interested in learning more, you can check out the `docs <https://docs.docker.com/engine/swarm/swarm-tutorial/>`_.



---------------------
Director Architecture
---------------------
Director is made out of four main parts.

- The Manager is responsible for the director website.
- The Orchestrator is responsible for the staticfiles and docker builds
  for user websites.
- The Router is responsible for routing traffic to the orchestrator.
- The Shell runs an ssh server using ``AsyncSSH`` to communicate with the Manager.


If you want to learn about each part in more detail, check out
the following articles (in the correct order):

- :doc:`manager`
- :doc:`orchestrator`
- :doc:`router_shell`


Manager
~~~~~~~

The Manager is a "typical" Django application - it's responsible for the UI
a TJ student would see when on director.

It uses Django Channels to handle websocket connections, and Celery to handle
long running tasks (e.g. creating sites). Effectively, it's the frontend of director.
It's where the database models for :class:`.Site` and :class:`.Operation` are located.

Orchestrator
~~~~~~~~~~~~

The Orchestrator is a Flask application that handles a lot of Nginx's configuration
for individual user sites.

Most often, these requests are things like changing the Nginx configuration,
updating Docker containers, or something similar. In fact, the Orchestrator
is where the setting of Director-specific environment variables happens!

It also uses a Websocket server for long running tasks.

It uses Nginx to serve static files and route incoming requests to the correct port
per site. To do this, it uses Docker to actually serve the site.

Communication
~~~~~~~~~~~~~

Frequently, one component needs to be able to make HTTP/Websocket requests to another component for various reasons.
What follows is a list of all the types of access that may be required.

- The manager should be able to make requests to all URLs on the orchestrator's Flask server.
- The manager should be able to make requests to all URLs on the orchestrator's Websocket server.
- The manager should be able to make requests to all URLs on the router's Flask server.
- The shell server should be able to make requests to all URLs with the prefix ``/shell-server/`` on the manager.
  No other client, especially regular web browsers, should be allowed to make requests to these URLs.
- The shell server should be able to make requests to all URLs with the prefix ``/ws/shell-server/`` on the orchestrator's Websocket server.
  It should not be allowed to make any other requests to the orchestrator or the router.


.. caution::

    These restrictions are not enforced by Director 4.0 itself. Instead, each component with an HTTP
    server should be behind a load balancer that enforces access restrictions.
