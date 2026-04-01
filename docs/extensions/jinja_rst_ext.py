"""A sphinx extension to process jinja/rst template

Usage:
    define the context variable needed by the document inside
    ``jinja_contexts`` variable in ``conf.py``
"""

# https://www.ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/

from pathlib import Path

import jinja2
from docutils import nodes

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


def fix_envvar_section_ids(app, doctree):
    """Replace auto-generated section IDs for env vars with variable names.

    Sphinx generates IDs like ``xonsh-capture-always`` from the title text.
    This handler changes them to ``XONSH_CAPTURE_ALWAYS`` (the actual variable name).
    """
    for section in doctree.traverse(nodes.section):
        if not section.children:
            continue
        title_node = section.children[0]
        if not isinstance(title_node, nodes.title):
            continue
        title_text = title_node.astext()
        if not title_text.startswith("$"):
            continue

        var_name = title_text[1:]  # e.g. XONSH_CAPTURE_ALWAYS
        # Canonical old-style ID for backward compat with existing URLs
        old_style_id = var_name.lower().replace("_", "-")

        for old_id in section.get("ids", []):
            doctree.ids.pop(old_id, None)

        section["ids"] = [var_name, old_style_id]
        for sid in section["ids"]:
            doctree.ids[sid] = section

        # Update nameids so cross-references resolve to the new primary ID
        for name in section.get("names", []):
            doctree.nameids[name] = var_name


def setup(app):
    app.connect("source-read", rstjinja)
    app.connect("doctree-read", fix_envvar_section_ids)

    # rst files can define the context with their names to be pre-processed with jinja
    app.add_config_value(
        "jinja_contexts",
        {},
        rebuild="",  # no need for rebuild. only the source changes
        # rebuild="env",  # no need for rebuild. only the source changes
    )
