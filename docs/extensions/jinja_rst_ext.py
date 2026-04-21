"""A sphinx extension to process jinja/rst template

Usage:
    define the context variable needed by the document inside
    ``jinja_contexts`` variable in ``conf.py``
"""

# https://www.ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/

import re
from pathlib import Path

import jinja2
from docutils import nodes
from sphinx.transforms import SphinxTransform

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
        out_path = Path(utils.docs_dir / "_build" / f"{docname}.rst.out")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered)


class FixEnvVarSectionIds(SphinxTransform):
    """Replace auto-generated section IDs for env vars with variable names.

    Sphinx generates IDs like ``xonsh-capture-always`` from the title text.
    This transform changes them to ``XONSH_CAPTURE_ALWAYS`` so that both the
    page anchors and the right-side TOC use the actual variable name.

    Runs as a transform (not an event handler) to guarantee execution before
    TocTreeCollector builds the sidebar TOC.
    """

    # After InternalTargets (priority 500) which merges .. _label: into sections
    default_priority = 600

    def apply(self):
        for section in self.document.findall(nodes.section):
            if not section.children:
                continue
            title_node = section.children[0]
            if not isinstance(title_node, nodes.title):
                continue
            title_text = title_node.astext()
            if not title_text.startswith("$"):
                continue

            var_name = title_text[1:]  # e.g. XONSH_CAPTURE_ALWAYS
            # Sanitize special chars (e.g. w*DIRS$ -> w_DIRS_)
            var_name = re.sub(r"[^\w]", "_", var_name)
            # Canonical old-style ID for backward compat with existing URLs
            old_style_id = var_name.lower().replace("_", "-")

            old_ids = set(section.get("ids", []))
            for old_id in old_ids:
                self.document.ids.pop(old_id, None)

            section["ids"] = [var_name, old_style_id]
            for sid in section["ids"]:
                self.document.ids[sid] = section

            # Update ALL nameids entries that pointed to old IDs,
            # including the .. _label: target and the title-derived name.
            for name, nid in list(self.document.nameids.items()):
                if nid in old_ids:
                    self.document.nameids[name] = var_name


def setup(app):
    app.connect("source-read", rstjinja)
    app.add_transform(FixEnvVarSectionIds)

    # rst files can define the context with their names to be pre-processed with jinja
    app.add_config_value(
        "jinja_contexts",
        {},
        rebuild="",  # no need for rebuild. only the source changes
        # rebuild="env",  # no need for rebuild. only the source changes
    )
