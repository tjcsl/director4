# Management node

This subdirectory contains the code for Director 4.0's management node. It is a Django application that uses Channels and Celery.

## Developement

This section lists some things to watch out for when developing.

*Because it makes things easier, "MAY, "MUST," "SHOULD," etc. are interpreted as defined in [RFC 2219](https://tools.ietf.org/html/rfc2119).*

- In production, static files under `static/vendor` MAY have a significantly longer expiration time set. This reduces load on the server for static files that do not change frequently.
  To avoid conflicts, developers SHOULD embed the version (or some unique string derived from it) of the vendored dependency in some part of the URL to access it. For example, jQuery is currently located in `static/vendor/jquery-3.4.1.min.js`.
- Travis is set up on this repository, and the build enforces very strict formatting and code styling. Run `scripts/format.sh` and `scripts/check.sh` locally before you push.
