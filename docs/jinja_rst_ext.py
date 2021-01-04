"""A sphinx extension to process jinja/rst template"""

# https://www.ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/

from pathlib import Path

import jinja2

cur_dir = Path(__file__).parent.resolve()


def rstjinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # Make sure we're outputting HTML
    if app.builder.format != "html":
        return

    ctx = app.config.jinja_contexts.get(docname)
    if ctx is not None:
        environment = jinja2.Environment(
            trim_blocks=True,
            lstrip_blocks=True,
        )

        src = source[0]
        if "content" in src:
            file_path = cur_dir / f"{docname}.jinja2"
            if file_path.exists():
                ctx["content"] = environment.from_string(file_path.read_text()).render(
                    **ctx
                )

        rendered = app.builder.templates.render_string(src, ctx)
        source[0] = rendered

        # for debugging purpose write output
        # Path(cur_dir / "_build" / f"{docname}.rst.out").write_text(rendered)


def setup(app):
    app.connect("source-read", rstjinja)

    # rst files can define the context with their names to be pre-processed with jinja
    app.add_config_value("jinja_contexts", {}, "env")
