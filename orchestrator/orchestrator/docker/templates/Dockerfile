FROM {{ parent_name|default("alpine", boolean=True) }}

MAINTAINER {{ maintainer }}

{% if parent_setup_command -%}
{# We run this separately so that Docker can cache the layer. It effectively becomes another image that the site's image is inheriting from. #}
RUN {{ parent_setup_command }}
{% endif %}

{% if install_command -%}
RUN apt-get --allow-releaseinfo-change update -y
RUN {{ install_command }}
{% endif %}
