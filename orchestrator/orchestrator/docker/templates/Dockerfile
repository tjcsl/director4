{% if parent %}
FROM {{ parent }}
{% else %}
FROM alpine
{% endif %}

MAINTAINER {{ maintainer }}

{% if full_install_command %}
RUN {{ full_install_command }}
{% endif %}
