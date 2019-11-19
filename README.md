# Director 4.0: Scaling Website Management for the Masses

[![Travis CI](https://api.travis-ci.com/tjresearch/research-theo_john.svg?branch=master)](https://travis-ci.com/tjresearch/research-theo_john)

## Overview
Our project is to develop a website management and hosting platform (based on the [current Director platform](https://github.com/tjcsl/director) that is designed to scale. It is intended to replace the current Director platform which has problems.

## Architecture
Director 4.0 is designed to be "sharded" and non-monolithic.

### Application Servers
Hosts the actual sites. The sites are not directly accessible to users. Depending on the site type, they are either hosted in a directory (static) or a Docker container (dynamic). Docker containers are a critical component on this server. An `orchestrator` orchestrates these containers in coordination with the manager.

### Management Server
Hosts the Django web interface for the application. Supervises site placement in coordination with the application servers.

### Load Balancing Servers
Using modern, open source load balancing technologies ([HAProxy](https://www.haproxy.org/)/[Nginx](https://nginx.org/)), distributes incoming traffic to the appropriate application servers.

## Licensing
This code is released under the MIT License as described in [LICENSE](LICENSE).

## Acknowledgments
The authors of Director 4.0 would like to acknowledge the [contributors](https://github.com/tjcsl/director/graphs/contributors) to the [TJHSST Director](https://github.com/tjcsl/director) application for providing inspiration for this project.

The authors of Director 4.0 would also like to acknowledge the support of the TJHSST Computer Systems Lab, especially research advisor Dr. Patrick White.

## Authors
- @theo-o
- @anonymoose2
