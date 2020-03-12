# Docker Image Registry

## Motivation

The Docker image registry allows us to store Docker images in a central location.

## Considerations

When deciding the set up for storing Docker images, we took the following items into account:

* **security and secure defaults**
* **integration with our custom orchestrator and Docker**
* **ease of deployment**
* **ease of use by end-users**
* **ease of administration**
* **capability to meed the needs of thousands of sites** 

## Kraken

[Kraken][1] is a peer-to-peer-powered Docker registry that focuses on scalability and availability in a hybrid cloud environment. It was created and currently maintained by Uber. A tech talk on Kraken is [available here][2] and an introductory blog post by the developers is [available here][3]. Although the peer-to-peer nature is appealing, we decided to not use it in our initial deployment of Director 4.0 due to the added complexity of the Kraken setup.

## Docker Registry Software

The upstream Docker registry ([GitHub repo][4]; [upstream docs][5]) is a
> stateless, highly scalable server side application that stores and lets you distribute Docker images.

It is developed by the same developers as Docker.

### Setup

See the Vagrant provision script for more information.

### API
Docker Registry is managed [via a HTTP API][7] that is exposed at the `/v2` endpoint.

Note: The specification is not that real well organized/informative. See the code comments for a better explaination.

[1]: https://github.com/uber/kraken
[2]: https://www.youtube.com/watch?v=waVtYYSXkXU
[4]: https://github.com/docker/distribution
[5]: https://docs.docker.com/registry/
[6]: https://www.digitalocean.com/community/tutorials/how-to-set-up-a-private-docker-registry-on-ubuntu-18-04
[7]: https://docs.docker.com/registry/spec/api
