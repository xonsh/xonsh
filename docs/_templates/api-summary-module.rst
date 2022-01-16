{{ fullname | escape | underline}}

.. currentmodule:: xonsh.xoreutils.cat

.. automodule:: {{ fullname }}
    :members:
    :undoc-members:
    :inherited-members:

{%- block modules %}
{%- if modules %}
.. rubric:: Modules

.. autosummary::
   :toctree:
   :template: api-summary-module.rst
   :recursive:
{% for item in modules %}
   {{ item }}
{% endfor %}
{% endif %}
{% endblock %}