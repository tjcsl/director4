FROM {{ parent|default("alpine", boolean=True) }}

MAINTAINER {{ maintainer }}

{% if full_install_command %}
RUN {{ full_install_command }}
{% endif %}
