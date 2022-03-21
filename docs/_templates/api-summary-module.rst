{{ fullname | escape | underline}}

{# module level doc #}
.. currentmodule:: {{ fullname }}

.. automodule:: {{ fullname }}
    :members:
    :undoc-members:
    :inherited-members:

{%- block modules %}
{%- if modules %}

.. autosummary::
   :toctree:
   :template: api-summary-module.rst
   :recursive:
{% for item in modules %}
   {{ item }}
{% endfor %}
{% endif %}
{% endblock %}
