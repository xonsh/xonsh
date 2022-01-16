"""A sphinx extension to process jinja/rst template

Usage:
    define the context variable needed by the document inside
    ``jinja_contexts`` variable in ``conf.py``
"""

# https://www.ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/

from pathlib import Path

import jinja2

from . import rst_helpers, utils


def rstjinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # Make sure we're outputting HTML
    if app.builder.format != "html":
        return

    print(docname)
    page_ctx = app.config.jinja_contexts.get(docname)
    if page_ctx is not None:
        ctx = {
            "rst": rst_helpers,
        }
        ctx.update(page_ctx)
        environment = jinja2.Environment(
            trim_blocks=True,
            lstrip_blocks=True,
        )

        src = source[0]
        rendered = environment.from_string(src).render(**ctx)
        # rendered = app.builder.templates.render_string(src, ctx)
        source[0] = rendered

        # for debugging purpose write output
        Path(utils.docs_dir / "_build" / f"{docname}.rst.out").write_text(rendered)


def setup(app):
    app.connect("source-read", rstjinja)

    # rst files can define the context with their names to be pre-processed with jinja
    app.add_config_value(
        "jinja_contexts",
        {},
        rebuild="",  # no need for rebuild. only the source changes
        # rebuild="env",  # no need for rebuild. only the source changes
    )
