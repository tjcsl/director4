# Director 4.0: Scaling Website Management for the Masses

[![Travis CI](https://api.travis-ci.com/tjresearch/research-theo_john.svg?branch=master)](https://travis-ci.com/tjresearch/research-theo_john)

## Overview
Our project is to develop a website management and hosting platform (based on the [current Director platform](https://github.com/tjcsl/director)) that is designed to scale. It is intended to replace the current Director platform which has problems.

It is composed of three primary components:
* `orchestrator`: The code that orchestrates the Docker containers
* `manager`: The Django web application
* `balancer`: (NOT STARTED)

## Architecture
A full description of the project's architecture can be found in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Requirements

### Software Requirements
* [Docker Engine](https://docs.docker.com/engine/): Used by the orchestrator to host sites
* [Python 3.7+](https://www.python.org/): Used by all components
* [RabbitMQ](https://www.rabbitmq.com/): Used by the manager/orchestrator to broker messages for long-running tasks
* [Celery](http://www.celeryproject.org/): Used by the manager/orchestrator to manage long-running tasks
* [Redis](https://redis.io/): Used by the manager to cache data
* [PostgreSQL](https://www.postgresql.org/): Used by the manager as the relational database
* [Nginx](https://nginx.org/): Used by the manager/orchestrator as a reverse proxy
* [HAProxy](https://www.haproxy.org/): Used by the balancer to balance incoming web traffic

Each of the three components has specific Python dependencies described in each `Pipfile`.

## Hardware/Resource Requirements

We recommend that you have a server for each component to replicate an actual production environment.

The resources (storage, memory, CPU, and network) required to run Director 4.0 depend on the number of sites being run, user load, request count, and other factors.

## Setup

We use Vagrant for providing a partial replica of a production environment. See [docs/SETUP.md](docs/SETUP.md) for details.

## Screenshots

*IN PROGRESS*

## Licensing
This code is released under the MIT License as described in [LICENSE](LICENSE).

## Acknowledgments
The authors of Director 4.0 would like to acknowledge the [contributors](https://github.com/tjcsl/director/graphs/contributors) to the [TJHSST Director](https://github.com/tjcsl/director) application for providing inspiration for this project.

The authors of Director 4.0 would also like to acknowledge the support of the TJHSST Computer Systems Lab, especially research advisor Dr. Patrick White for his guidance and mentoring.

## Authors
- [@theo-o](https://github.com/theo-o)
- [@anonymoose2](https://github.com/anonymoose2)
