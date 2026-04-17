"""Wrap every Sphinx code block with schema.org/SoftwareSourceCode microdata.

Emits for each ``.. code-block::`` / ``.. sourcecode::`` / ``::`` directive::

    <div itemscope itemtype="https://schema.org/SoftwareSourceCode" class="highlight-<lang> ...">
      <meta itemprop="programmingLanguage" content="<lang>">
      <meta itemprop="name" content="<Section Title> example">
      <div class="highlight"><pre><code itemprop="text">...highlighted code...</code></pre></div>
    </div>

The language meta maps xonsh-flavored lexers (``python``, ``xonshcon``) to
``xonsh`` so AI crawlers and search engines see the actual shell language.
The name meta is derived from the nearest enclosing section's title with
``" example"`` appended — skipped if the block has no section ancestor.
No-op for parsed-literal blocks (those are verbatim text, not code).
"""

import html
import re

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.writers.html5 import HTML5Translator

SCHEMA_TYPE = "https://schema.org/SoftwareSourceCode"

# xonsh code blocks use the `python` lexer (for Python mode) or `xonshcon`
# (for the mock REPL transcript lexer). Both are semantically xonsh code.
_LANG_MAP = {
    "python": "xonsh",
    "xonshcon": "xonsh",
}

_ORIGINAL_VISIT_LITERAL_BLOCK = HTML5Translator.visit_literal_block

# Wrap the (single) <pre>…</pre> emitted by Pygments with a <code itemprop="text">
# marker so the inner text is machine-identifiable as the source-code payload.
_PRE_RE = re.compile(r"<pre([^>]*)>(.*?)</pre>", re.DOTALL)


def _nearest_section_title(node: nodes.Node) -> str | None:
    current = node.parent
    while current is not None:
        if isinstance(current, nodes.section):
            for child in current.children:
                if isinstance(child, nodes.title):
                    return child.astext()
            break
        current = current.parent
    return None


def _patched_visit_literal_block(self, node: nodes.literal_block) -> None:
    len_before = len(self.body)
    try:
        _ORIGINAL_VISIT_LITERAL_BLOCK(self, node)
    except nodes.SkipNode:
        # Build microdata tags to inject. Skip programmingLanguage when the
        # block has no explicit language — "default" carries no information.
        raw_lang = node.get("language") or ""
        meta_tags: list[str] = []
        prog_lang = _LANG_MAP.get(raw_lang, raw_lang)
        if prog_lang and prog_lang != "default":
            meta_tags.append(
                f'<meta itemprop="programmingLanguage" content="{html.escape(prog_lang, quote=True)}">'
            )
        section_title = _nearest_section_title(node)
        if section_title:
            name = f"{section_title} example"
            meta_tags.append(
                f'<meta itemprop="name" content="{html.escape(name, quote=True)}">'
            )
        meta_html = "".join(meta_tags)

        for i in range(len_before, len(self.body)):
            chunk = self.body[i]
            if not chunk.startswith('<div class="highlight-'):
                continue
            # 1) Promote the outer wrapper div to itemscope.
            chunk = chunk.replace(
                '<div class="highlight-',
                f'<div itemscope itemtype="{SCHEMA_TYPE}" class="highlight-',
                1,
            )
            # 2) Inject <meta> tags right after the outer div's `>`.
            if meta_html:
                # The first ">" in `chunk` now ends the outer opening tag we
                # just rewrote (itemtype/class attribute values contain no
                # ">", so this replacement is unambiguous).
                chunk = chunk.replace(">", f">{meta_html}", 1)
            # 3) Wrap the <pre>…</pre> body with <code itemprop="text">.
            chunk = _PRE_RE.sub(
                r'<pre\1><code itemprop="text">\2</code></pre>', chunk, count=1
            )
            self.body[i] = chunk
            break
        raise
    # Parsed-literal path — leave <pre> alone; not a code sample.


def setup(app: Sphinx) -> dict:
    # Monkey-patch instead of registering a new translator subclass: other
    # extensions / themes (Furo included) can still layer their own overrides.
    HTML5Translator.visit_literal_block = _patched_visit_literal_block
    return {
        "version": "1.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
