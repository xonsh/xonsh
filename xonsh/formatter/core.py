"""Token-stream based formatting engine for xonsh source.

Why tokens, not AST
-------------------
xonsh has no xonsh-specific AST nodes — ``$(ls)`` parses to a regular
``Call(__xonsh__.subproc_capture_stdout, ...)``, ``${VAR}`` to a
``Subscript`` of ``__xonsh__.env``, and so on. Round-tripping through the
AST would lose the original syntactic form (was it ``$(...)`` or
``$[...]``?), drop comments, and erase the user's line breaks. Working
on the raw token stream from :mod:`xonsh.parsers.tokenize` keeps every
character of the source available — including ``COMMENT`` and ``NL``
tokens that the parser-facing lexer normally filters out.

What the formatter changes
--------------------------
* normalizes indentation to a configurable indent string (4 spaces);
* strips trailing whitespace from each line;
* ensures the file ends with exactly one ``\\n``;
* collapses runs of blank lines (max 2 at module top level, max 1
  nested);
* leaves ``#``-comment bodies untouched — commented-out code stays
  byte-for-byte (``#def foo():`` is *not* rewritten to ``# def …``);
* normalizes the *padding* before an inline comment to two spaces;
* forces a single space around top-level ``=`` (assignment) but leaves
  ``f(x=1)`` / ``def f(x=1)`` / ``lambda x=1:`` untouched, and is
  suppressed in subprocess statements (``--flag=value`` stays glued);
* forces single spaces around augmented assignments, ``==``, ``!=``,
  ``<=``, ``>=``, ``->``, and ``:=``;
* normalizes ``,`` and ``;`` to be followed by exactly one space (or a
  newline / closer);
* collapses runs of inter-arg whitespace inside subprocess statements
  (``echo a   b`` → ``echo a b``); macros (``name!`` and
  ``name!(...)``) are exempt and keep their bodies verbatim;
* normalizes ``\\``-newline continuation indentation to one indent
  unit past the statement's base (subprocess) or preserves the user's
  intentional alignment (Python — ``or`` lined up under ``if``, etc.);
* preserves all xonsh-specific syntax verbatim — ``$()``, ``!()``,
  ``${...}``, ``$[]``, ``![]``, ``@()``, ``@$()``, IO redirects,
  ``&&`` / ``||``, search-path globs, f-strings.

What it deliberately leaves alone
---------------------------------
Long-line splitting, magic trailing comma, quote normalization, and
import sorting are out of scope for this MVP — those are stylistic
rewrites that need richer context than a single token-stream pass.
"""

from __future__ import annotations

import io

from xonsh.parsers.tokenize import (
    COMMENT,
    DEDENT,
    DOLLARNAME,
    ENCODING,
    ENDMARKER,
    ERRORTOKEN,
    FSTRING_END,
    FSTRING_MIDDLE,
    FSTRING_START,
    INDENT,
    NAME,
    NEWLINE,
    NL,
    NUMBER,
    OP,
    SEARCHPATH,
    STRING,
    TokenError,
    tokenize,
)

DEFAULT_INDENT = "    "

# Bracket-like openers (Python + xonsh subprocess).
_OPENERS = frozenset(("(", "[", "{", "$(", "$[", "${", "!(", "![", "@(", "@!(", "@$("))
_CLOSERS = frozenset((")", "]", "}"))

# Operators that always take a space on each side in Python mode.
_ALWAYS_SPACED = frozenset(
    (
        "==",
        "!=",
        "<=",
        ">=",
        "->",
        ":=",
        "+=",
        "-=",
        "*=",
        "/=",
        "//=",
        "%=",
        "**=",
        "@=",
        "|=",
        "&=",
        "^=",
        "<<=",
        ">>=",
    )
)

# Python keywords that must be followed by whitespace before the next
# meaningful token (excludes ``:`` / closers, which are handled by
# their own rules so that e.g. ``else:`` stays glued). Soft keywords
# (``match``, ``case``, ``type``) are deliberately omitted: they only
# act like keywords in specific syntactic positions, and forcing a
# space after them would mangle uses like ``add_argument(type=int)``.
_PY_KEYWORDS = frozenset(
    (
        "and",
        "as",
        "assert",
        "async",
        "await",
        "class",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    )
)

# Names that, when they lead a logical line, mark it as a Python
# statement rather than a subprocess command. Includes hard keywords
# above plus the Python literal names (``True``/``False``/``None``)
# and the soft keywords used for ``match`` / ``type`` statements.
# A bare name followed by ``=`` etc. is independently caught by the
# operator-after-name check, so this set only needs the names that
# would otherwise appear before another NAME and get misclassified.
_LINE_START_PYTHON_NAMES = _PY_KEYWORDS | frozenset(
    {"True", "False", "None", "match", "case", "type"}
)

# Operators that, when they follow the leading NAME of a line,
# definitively mark the line as Python (assignment / call / member
# access / arithmetic / comparison / etc.). Anything not in this set
# (NAME, NUMBER, STRING, ``-``, ``!``, …) suggests a subprocess
# command.
_PY_AFTER_LEADING_NAME = frozenset(
    {
        "(",
        "[",
        ".",
        "=",
        ",",
        ":",
        ";",
        "+=",
        "-=",
        "*=",
        "/=",
        "//=",
        "%=",
        "**=",
        "@=",
        "|=",
        "&=",
        "^=",
        "<<=",
        ">>=",
        "==",
        "!=",
        "<",
        "<=",
        ">",
        ">=",
        ":=",
        "+",
        "*",
        "/",
        "//",
        "%",
        "**",
        "<<",
        ">>",
        "&",
        "|",
        "^",
        "->",
    }
)

# Word-like operators that, when they appear as the SECOND token after
# a leading NAME, mean the line is a Python expression (``x and y``,
# ``x or y``, ``x is None``, ``x in s``, ``x not in s``).
_PY_INFIX_KEYWORDS = frozenset({"and", "or", "is", "in", "not"})


class FormatError(Exception):
    """Raised when the source cannot be tokenized."""


def format_source(src: str, *, indent: str = DEFAULT_INDENT) -> str:
    """Return ``src`` reformatted as xonsh source code.

    Parameters
    ----------
    src
        The xonsh source code to format.
    indent
        The string used per indent level. Defaults to four spaces.
    """
    return _Formatter(src, indent=indent).run()


class _Formatter:
    """One-shot formatter; instantiate per-source-string."""

    def __init__(self, src: str, *, indent: str = DEFAULT_INDENT) -> None:
        # The tokenizer expects a trailing newline to produce a clean
        # final NEWLINE/ENDMARKER. Empty input is handled by the
        # short-circuit in :meth:`run`.
        if src and not src.endswith("\n"):
            src = src + "\n"
        self._src = src
        # Cached split of source by line, used by the continuation-line
        # branch in :meth:`run` to recover the original hanging indent
        # of an expression broken across lines inside brackets.
        self._src_lines = src.split("\n")
        self._indent_str = indent
        # Width (in source characters) of one indent level in the input.
        # Resolved lazily from the first indented line we see so that
        # comment-column → indent-level conversion is accurate for
        # tab-indented or 2-space sources, not just 4-space ones.
        self._src_indent_width: int | None = None

        # State for the emit pass.
        self._out: list[str] = []
        self._indent_level = 0
        # Stack of opener strings — top tells us which kind of bracket
        # we're currently inside ("[" means slice context for ``:``).
        self._brackets: list[str] = []
        # Number of unfinished ``lambda`` parameter lists. Bumped when
        # the keyword is emitted, decremented on the matching ``:``.
        # Used to keep ``lambda x=1: x`` and ``lambda: x`` unmodified.
        self._lambda_depth = 0
        # True at the start of every physical line (before indent has
        # been emitted). Becomes False after the first token on a line.
        self._line_start = True
        # Pending blank lines accumulated from NL tokens — applied
        # (capped) when the next real token arrives.
        self._pending_blanks = 0
        # When the current logical statement looks like a subprocess
        # command (``echo 1 2 --flag=value`` and friends), the
        # Python-mode ``=`` rule is suppressed (``--flag=value`` is
        # one argument, not an assignment) and ``\``-newline
        # continuations get a normalized indent. Detected via
        # lookahead at line-start; reset on ``NEWLINE``.
        self._subproc_line = False
        # Alias-macro statement (``name! raw text``) — the args after
        # the bang are raw text whose whitespace must be preserved
        # exactly. Separate from ``_subproc_line`` because regular
        # subprocess commands collapse runs of inter-arg whitespace
        # while macros must not.
        self._macro_alias_line = False
        # Paren depth at which we entered an active function-macro
        # call (``name!(args)``). Inside a macro the args are raw
        # strings — preserve their whitespace exactly. ``0`` means
        # "not in a macro".
        self._macro_until_depth = 0

    @property
    def _paren_depth(self) -> int:
        return len(self._brackets)

    def run(self) -> str:
        if not self._src:
            return ""

        tokens = list(self._iter_tokens())
        prev = None  # last emitted real (non-structural) token

        for i, tok in enumerate(tokens):
            ttype = tok.type

            if ttype == ENCODING:
                continue
            if ttype == ENDMARKER:
                break

            if ttype == INDENT:
                # The first INDENT we see authoritatively defines the
                # source's indent step (one tab, four spaces, two
                # spaces, …). This is more reliable than scanning
                # ``self._src_lines`` for indented prose, which would
                # be fooled by docstring wrap-continuations.
                if self._src_indent_width is None:
                    self._src_indent_width = len(tok.string) or len(self._indent_str)
                self._indent_level += 1
                continue
            if ttype == DEDENT:
                self._indent_level -= 1
                continue

            if ttype == NEWLINE:
                # End of a logical statement.
                self._out.append("\n")
                self._line_start = True
                self._pending_blanks = 0
                self._subproc_line = False
                self._macro_alias_line = False
                continue

            if ttype == NL:
                if self._line_start:
                    # Blank line between statements — defer until we
                    # know whether the next token is at top level or
                    # nested, so the cap can be applied correctly.
                    self._pending_blanks += 1
                else:
                    # Implicit line continuation inside brackets.
                    self._out.append("\n")
                    self._line_start = True
                continue

            # A real token (or a leading comment). Flush blank lines,
            # emit indent if at line start, then the inter-token gap.
            if self._line_start:
                if self._paren_depth > 0:
                    # Continuation line inside brackets — preserve the
                    # source's leading whitespace verbatim so hanging
                    # indents and visual alignment of multi-line
                    # imports / calls / collections survive untouched.
                    self._flush_blank_lines(self._indent_level)
                    line = self._src_lines[tok.start[0] - 1]
                    self._out.append(line[: tok.start[1]])
                else:
                    level = (
                        self._comment_indent(tok)
                        if ttype == COMMENT
                        else self._indent_level
                    )
                    self._flush_blank_lines(level)
                    self._out.append(self._indent_str * max(level, 0))
                    # Decide whether this statement is a subprocess
                    # command and/or an alias-macro line — comments
                    # don't change either decision.
                    if ttype != COMMENT:
                        self._subproc_line = self._is_subproc_statement(tokens, i)
                        self._macro_alias_line = self._is_alias_macro_line(tokens, i)
                self._line_start = False
            else:
                self._out.append(self._space_between(prev, tok))

            self._out.append(self._render_token(tok))
            self._update_state(tok)
            # Function-macro entry: ``name!(`` with no gap turns the
            # body into raw arguments. Recognised once we've seen the
            # ``!(`` opener (so paren depth has just been pushed).
            if (
                tok.type == OP
                and tok.string == "!("
                and prev is not None
                and prev.type == NAME
                and prev.end == tok.start
            ):
                self._macro_until_depth = self._paren_depth
            # Macro exit: dropped below the depth we entered at.
            if self._macro_until_depth and self._paren_depth < self._macro_until_depth:
                self._macro_until_depth = 0
            prev = tok

        return self._finalize("".join(self._out))

    def _comment_indent(self, tok) -> int:
        """Indent level for a leading-line comment, derived from its
        source column.

        The tokenizer associates comments with whatever block was open
        when they were lexed — a trailing comment whose source column
        sits at the *outer* level still arrives *before* the matching
        DEDENTs, and a comment that opens a new body arrives *before*
        the matching INDENT. Both cases mean ``self._indent_level`` is
        a poor signal for where to render the comment.

        The most reliable signal is the comment's own source column.
        We translate that column into an indent level by walking the
        line's leading whitespace character-by-character: each ``\\t``
        counts as one level (regardless of the spaces-based source
        indent width), each space counts as ``1 / source_width`` of a
        level. This is what makes mixed tab/space sources Just Work —
        a comment indented with a single tab in a file whose other
        lines use four-space indents still resolves to level 1, which
        matches the user's clear visual intent.
        """
        col = tok.start[1]
        if col == 0:
            return 0
        width = self._source_indent_width()
        if width <= 0:
            return 0
        line = self._src_lines[tok.start[0] - 1]
        leading = line[:col]
        levels = 0.0
        for ch in leading:
            if ch == "\t":
                levels += 1
            elif ch == " ":
                levels += 1.0 / width
            else:
                # Non-whitespace before ``col`` shouldn't happen for a
                # leading-line comment, but guard against weird inputs.
                break
        return max(round(levels), 0)

    def _source_indent_width(self) -> int:
        """Return the source's indent step in characters (4, 2, 1=tab,
        …). Set by the run loop on the first ``INDENT`` token; falls
        back to ``len(self._indent_str)`` for files with no indented
        blocks (e.g. a single-line module).
        """
        if self._src_indent_width is None:
            self._src_indent_width = len(self._indent_str) or 4
        return self._src_indent_width

    # ---------------------------------------------------------------
    # Token iteration
    # ---------------------------------------------------------------
    def _iter_tokens(self):
        readline = io.BytesIO(self._src.encode("utf-8")).readline
        try:
            yield from tokenize(readline, tolerant=False)
        except (TokenError, IndentationError) as exc:
            raise FormatError(str(exc)) from exc

    # ---------------------------------------------------------------
    # Per-token state updates (paren / lambda tracking)
    # ---------------------------------------------------------------
    def _update_state(self, tok) -> None:
        ttype, tstr = tok.type, tok.string
        if ttype == OP:
            if tstr in _OPENERS:
                self._brackets.append(tstr)
            elif tstr in _CLOSERS and self._brackets:
                self._brackets.pop()
            elif tstr == ":" and self._lambda_depth > 0:
                # Close the most recent lambda parameter scope. The
                # ``:`` belongs to the lambda regardless of any
                # enclosing parens, so we always decrement on the
                # first ``:`` after a ``lambda``.
                self._lambda_depth -= 1
        elif ttype == NAME and tstr == "lambda":
            self._lambda_depth += 1

    # ---------------------------------------------------------------
    # Blank-line handling
    # ---------------------------------------------------------------
    def _flush_blank_lines(self, target_level: int) -> None:
        if self._pending_blanks <= 0:
            return
        # Cap depends on the destination level, not on the current
        # ``_indent_level``: a top-level comment that arrives before
        # the matching DEDENTs should still get up to two blank lines
        # of separation, even though ``_indent_level`` is still > 0
        # while we process it.
        cap = 2 if target_level == 0 else 1
        for _ in range(min(self._pending_blanks, cap)):
            self._out.append("\n")
        self._pending_blanks = 0

    # ---------------------------------------------------------------
    # Inter-token spacing
    # ---------------------------------------------------------------
    def _space_between(self, prev, cur) -> str:
        pt, ps = prev.type, prev.string
        ct, cs = cur.type, cur.string

        # f-string segments are always glued — *before* any other
        # rule, including the subproc/macro verbatim modes below. The
        # xonsh tokenizer reports unreliable (often inverted) source
        # positions for multi-line ``FSTRING_MIDDLE`` tokens; if a
        # verbatim-mode ``_raw_between`` were allowed to consult those
        # positions it would synthesize a "gap" that re-emits the
        # f-string body, duplicating its content. Always glue.
        if ct in (FSTRING_MIDDLE, FSTRING_END):
            return ""
        if pt in (FSTRING_START, FSTRING_MIDDLE):
            return ""

        # Bang macro marker glued to its lead token — alias macros
        # (``name!``), block macros (``with! ctx:``), and friends. The
        # ``!`` is an ``ERRORTOKEN`` from the tokenizer's perspective,
        # so without this rule the keyword-force-space below would
        # turn ``with! qwe:`` into ``with ! qwe:``.
        if ct == ERRORTOKEN and cs == "!" and prev.end == cur.start:
            return ""

        # Macro bodies — both alias macros (``name! raw text`` until
        # NEWLINE) and function macros (``name!(args)`` until the
        # matching paren) — are full source-verbatim: their arguments
        # are raw text and any whitespace the user typed is part of
        # the call. Regular top-level subprocess statements
        # (``echo 1 2 --flag=value``) do *not* go through this path —
        # users expect runs of whitespace between args collapsed, the
        # same way ``$(...)`` captures normalize their content.
        # Subproc-specific quirks (``=`` flag values, ``\\\n``
        # continuations) are handled below by targeted rules.
        if self._macro_until_depth > 0 or self._macro_alias_line:
            return self._raw_between(prev, cur)

        # ``\\\n`` line continuation. Subprocess commands always use
        # one indent unit past the statement's base — the original
        # column carries no meaning to the shell. Python statements
        # preserve the user's intentional vertical alignment (an
        # ``or`` lined up under its ``if``, etc.), rescaled to the
        # formatter's indent width so that alignment survives indent
        # normalization (12-space, tabs, 2-space → 4-space).
        if pt == ERRORTOKEN and ps in ("\\\n", "\\\r\n"):
            if self._subproc_line:
                return self._indent_str * (self._indent_level + 1)
            src_w = self._source_indent_width()
            src_base = self._indent_level * src_w
            visual_chars = max(cur.start[1] - src_base, 0)
            levels = visual_chars / src_w if src_w else 0
            new_base = self._indent_level * len(self._indent_str)
            out_offset = round(levels * len(self._indent_str))
            return " " * (new_base + out_offset)

        # Inline comments get two spaces of leading padding (PEP 8) —
        # checked before the bracket-glue rules so that a trailing
        # comment immediately after ``(`` (line-continuation comment)
        # keeps its visual offset from the opener.
        if ct == COMMENT:
            return "  "

        # Bracket adjacency: glue.
        if ps in _OPENERS:
            return ""
        if cs in _CLOSERS:
            return ""

        # Comma / semicolon: never a space before, exactly one after.
        if cs == "," or cs == ";":
            return ""
        if ps == "," or ps == ";":
            return " "

        # ``:`` rules. Annotations / dict entries / lambda terminators
        # never want a space *before* the colon. Slice colons (inside
        # ``[]``) glue on both sides; everything else gets a space
        # after.
        if cs == ":":
            return ""
        if ps == ":":
            if self._brackets and self._brackets[-1] == "[":
                return ""
            return " "

        # ``=`` rule. At statement level (no enclosing parens, no open
        # lambda parameter list) it's always an assignment and gets
        # spaces; otherwise it's a kwarg / default / annotated default
        # and stays glued. Suppressed in subprocess context, where
        # ``--flag=value`` is one argument and a user-written
        # ``--flag = value`` should stay as-typed — fall through to
        # the original-gap default below.
        if (
            (ps == "=" or cs == "=")
            and self._paren_depth == 0
            and self._lambda_depth == 0
            and not self._subproc_line
        ):
            return " "

        # Always-spaced operators (==, !=, augmented assigns, …).
        if ps in _ALWAYS_SPACED or cs in _ALWAYS_SPACED:
            return " "

        # Force a space after a Python keyword so ``if(x):`` becomes
        # ``if (x):`` — but not before ``:`` or a closer (handled
        # earlier).
        if pt == NAME and ps in _PY_KEYWORDS:
            return " "

        # Default: preserve the original gap, normalized to exactly
        # one space (collapses runs of whitespace) or none.
        if prev.end[0] != cur.start[0]:
            return " "
        return " " if cur.start[1] > prev.end[1] else ""

    # ---------------------------------------------------------------
    # Token rendering
    # ---------------------------------------------------------------
    def _render_token(self, tok) -> str:
        if tok.type == COMMENT:
            return _format_comment(tok.string)
        if tok.type == FSTRING_MIDDLE:
            # ``tok.string`` for ``FSTRING_MIDDLE`` is the *decoded*
            # value: source ``{{`` collapses to ``{``, ``}}`` to ``}``,
            # ``\n`` to a real newline, and so on. Re-emitting the
            # decoded form would silently change the f-string's value
            # (``f"{{x}}"`` → ``f"{x}"`` is a different format string).
            # When the tokenizer's reported source span is large enough
            # to actually contain the decoded value, we extract the
            # original characters and round-trip is exact. xonsh's
            # tokenizer reports bogus end positions for multi-line
            # ``FSTRING_MIDDLE`` tokens (the entire fragment is
            # squashed onto one logical line), so in that case fall
            # back to re-escaping braces on the decoded value —
            # preserves ``{{``/``}}`` for multi-line triple-quoted
            # literals at the cost of not preserving rarer ``\``
            # escapes inside them.
            if self._fstring_span_reliable(tok):
                src = self._source_slice(tok)
                if src is not None:
                    return src
            return tok.string.replace("{", "{{").replace("}", "}}")
        return tok.string

    # ---------------------------------------------------------------
    # Subprocess-statement / macro detection
    # ---------------------------------------------------------------
    def _is_alias_macro_line(self, tokens: list, start_idx: int) -> bool:
        """``name! raw text`` form — a NAME directly followed by a
        ``!`` ``ERRORTOKEN`` (no whitespace between them) treats the
        rest of the logical line as raw macro arguments."""
        if start_idx >= len(tokens):
            return False
        first = tokens[start_idx]
        if first.type != NAME:
            return False
        if first.string in _LINE_START_PYTHON_NAMES:
            return False
        for j in range(start_idx + 1, len(tokens)):
            t = tokens[j]
            if t.type in (COMMENT, NL):
                continue
            return t.type == ERRORTOKEN and t.string == "!" and t.start == first.end
        return False

    def _is_subproc_statement(self, tokens: list, start_idx: int) -> bool:
        """Heuristic: does the logical line starting at ``tokens[start_idx]``
        look like a *bare* subprocess command (``echo 1 2 --flag=val``)
        rather than a Python statement?

        The xonsh parser performs the real subprocess-vs-Python decision
        based on the runtime ``aliases`` table and ``$PATH`` — neither
        is available to a static formatter. The static heuristic here
        only catches the bare-command form: a NAME at line start that
        is *not* a Python keyword/literal/soft-keyword AND whose next
        non-trivial token is something a Python statement wouldn't put
        there (another NAME, a NUMBER, a STRING, ``-flag``, alias-macro
        ``!``, …).

        Lines that *begin* with a subprocess capture (``$(...)``,
        ``!(...)``, ``${...}``, ``@$(...)``, …) are intentionally
        excluded — those are Python expressions whose value happens to
        be a captured pipeline. Their *contents* get normalized by the
        regular paren-aware rules (multi-space inside ``$(...)``
        collapses to one), while nothing meaningful is gained from
        forcing the entire enclosing statement into verbatim mode.

        Anything else (assignment, function call, attribute access,
        infix operator, bare expression, decorated def, …) is left to
        the Python formatter.
        """
        if start_idx >= len(tokens):
            return False
        first = tokens[start_idx]
        if first.type != NAME:
            return False
        if first.string in _LINE_START_PYTHON_NAMES:
            return False
        # Find the next non-trivial token on the same statement.
        second = None
        for j in range(start_idx + 1, len(tokens)):
            t = tokens[j]
            if t.type in (COMMENT, NL):
                continue
            second = t
            break
        if second is None or second.type == NEWLINE:
            return False  # bare ``name`` — Python expression statement
        if second.type == OP:
            if second.string in _PY_AFTER_LEADING_NAME:
                return False
            if second.string == "-":
                return self._dash_looks_like_subproc_flag(tokens, j, second)
            # ``name!(`` macro-call opens here; the call itself is a
            # Python expression at the outer level (the body becomes
            # raw via :attr:`_macro_until_depth` once entered).
            if second.string in {"!(", "![", "?", "??"}:
                return False
        if second.type == ERRORTOKEN and second.string == "!":
            # Alias macro form: ``echo! raw stuff`` — subprocess.
            return True
        if second.type == NAME:
            # Python infix word operators (``x and y``, ``x is None``,
            # ``x in s``, ``x not in s``) keep the line in Python mode.
            if second.string in _PY_INFIX_KEYWORDS:
                return False
            return True
        if second.type in (NUMBER, STRING, FSTRING_START, SEARCHPATH, DOLLARNAME):
            return True
        return False

    def _dash_looks_like_subproc_flag(
        self, tokens: list, dash_idx: int, dash_tok
    ) -> bool:
        """``cmd -flag`` vs ``x - 1``: peek at the token after ``-``."""
        for j in range(dash_idx + 1, len(tokens)):
            t = tokens[j]
            if t.type in (COMMENT, NL):
                continue
            if t.type == OP and t.string == "-":
                return True  # ``--flag``
            if t.type == NAME and t.start == dash_tok.end:
                return True  # ``-flag`` (no space — attached short flag)
            return False
        return False

    def _raw_between(self, prev, cur) -> str:
        """Original source text between ``prev``'s emitted end and
        ``cur.start``.

        We compute ``prev``'s effective end from its ``string`` rather
        than blindly trusting ``prev.end``: tokens whose value carries
        an embedded newline (notably the ``\\\\\\n`` line-continuation
        ``ERRORTOKEN`` xonsh emits in subprocess context) report an
        end position that lies on the *previous* logical line. Without
        this adjustment the multi-line branch below would re-emit the
        line break that the token already wrote.

        Special case: a subprocess line-continuation backslash-newline
        ``\\\\\\n`` arrives as an ``ERRORTOKEN``. Its value already
        ends with a real newline, so we're now positioned at column 0
        of the continuation line; whatever leading whitespace the user
        typed there is just visual indent. Replace it with one level
        past the statement's base indent so multi-line subprocess
        commands look consistently indented regardless of how the user
        aligned them in the source.
        """
        if prev.type == ERRORTOKEN and prev.string in ("\\\n", "\\\r\n"):
            return self._indent_str * (self._indent_level + 1)

        s_line, s_col = self._real_end(prev)
        e_line, e_col = cur.start
        if s_line == e_line:
            if e_col < s_col:
                return ""
            return self._src_lines[s_line - 1][s_col:e_col]
        if e_line < s_line:
            return " "
        parts = [self._src_lines[s_line - 1][s_col:]]
        for ln in range(s_line, e_line - 1):
            parts.append("\n")
            parts.append(self._src_lines[ln])
        parts.append("\n")
        parts.append(self._src_lines[e_line - 1][:e_col])
        return "".join(parts)

    @staticmethod
    def _real_end(tok) -> tuple[int, int]:
        """Position immediately after ``tok.string`` is fully emitted,
        accounting for embedded newlines in the value."""
        s_line, s_col = tok.start
        nl = tok.string.count("\n")
        if nl == 0:
            return (s_line, s_col + len(tok.string))
        tail = tok.string.rsplit("\n", 1)[-1]
        return (s_line + nl, len(tail))

    def _fstring_span_reliable(self, tok) -> bool:
        """True if the token's reported source span is at least as
        wide as its decoded value — the simplest cross-check that
        catches the xonsh multi-line ``FSTRING_MIDDLE`` quirk."""
        s_line, s_col = tok.start
        e_line, e_col = tok.end
        if e_line < s_line:
            return False
        if e_line > s_line:
            return True
        return e_col - s_col >= len(tok.string)

    def _source_slice(self, tok) -> str | None:
        """Return the original source text covered by a token, or
        ``None`` if the token's reported span is incoherent (a known
        quirk for multi-line f-string fragments — see callers)."""
        s_line, s_col = tok.start
        e_line, e_col = tok.end
        if s_line == e_line:
            if e_col < s_col:
                return None
            return self._src_lines[s_line - 1][s_col:e_col]
        if e_line < s_line:
            return None
        parts = [self._src_lines[s_line - 1][s_col:]]
        for ln in range(s_line, e_line - 1):
            parts.append(self._src_lines[ln])
        parts.append(self._src_lines[e_line - 1][:e_col])
        return "\n".join(parts)

    # ---------------------------------------------------------------
    # Final cleanup
    # ---------------------------------------------------------------
    def _finalize(self, text: str) -> str:
        # Strip trailing whitespace from each line without disturbing
        # line endings inside string literals (those came through as
        # part of STRING token text and are emitted unchanged here).
        lines = text.split("\n")
        # ``split`` keeps a trailing empty element when the text ended
        # with ``\n``; rstrip-ing it is harmless.
        cleaned = [ln.rstrip(" \t") for ln in lines]
        text = "\n".join(cleaned)
        # Collapse any trailing blank lines down to a single newline.
        text = text.rstrip("\n") + "\n"
        return text


def _format_comment(text: str) -> str:
    """Return a comment token's text unchanged, save for one defensive
    cleanup.

    The formatter intentionally does not rewrite the body of a comment
    — including not inserting a space after ``#`` for ``#text`` style
    comments. Users routinely keep commented-out code verbatim
    (``#def foo():``) and expect the formatter to leave it alone.

    The only adjustment is an ``lstrip``: xonsh's tokenizer
    occasionally emits a COMMENT token whose value carries a stray
    leading space (a state-contamination quirk after a ``$(...)``
    capture inside a string literal). The caller has already inserted
    the correct preceding whitespace via
    :meth:`_Formatter._space_between`, so any leading space on the
    value would double-count.
    """
    return text.lstrip()
