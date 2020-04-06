# Management node

This subdirectory contains the code for Director 4.0's management node. It is a Django application that uses Channels and Celery.

## Developement

This section lists some things to watch out for when developing.

*Because it makes things easier, "MAY, "MUST," "SHOULD," etc. are interpreted as defined in [RFC 2219](https://tools.ietf.org/html/rfc2119).*

- In production, static files under `static/vendor` MAY have a significantly longer expiration time set. This reduces load on the server for static files that do not change frequently.
  - You can use `scripts/update-vendor.py` to download the latest vendored dependencies.
- Travis is set up on this repository, and the build enforces very strict formatting and code styling. Run `scripts/format.sh` and `scripts/check.sh` locally before you push.
