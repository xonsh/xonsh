"""Implements helper class for parsing Xonsh syntax within f-strings."""

import re
from ast import parse as pyparse

from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers import ast
from xonsh.platform import PYTHON_VERSION_INFO


@lazyobject
def RE_FSTR_FIELD_WRAPPER():
    return re.compile(r"(__xonsh__\.eval_fstring_field\((\d+)\))\s*[^=]")


@lazyobject
def RE_FSTR_SELF_DOC_FIELD_WRAPPER():
    return re.compile(r"(__xonsh__\.eval_fstring_field\((\d+)\)\s*)=")


@lazyobject
def RE_XONSH_EXPR():
    """Matches xonsh-specific expressions: $NAME, $(...), ${...}, $[...],
    @(...), @$(...), @!(...), !(...), ![...]."""
    # Order matters: @$(...) and @!(...) must be tried before @(...).
    return re.compile(
        r"\$\w+"  # $NAME
        r"|\$\([^)]*\)"  # $(...)
        r"|\$\{[^}]*\}"  # ${...}
        r"|\$\[[^\]]*\]"  # $[...]
        r"|@\$\([^)]*\)"  # @$(...)
        r"|@!\([^)]*\)"  # @!(...)
        r"|@\([^)]*\)"  # @(...)
        r"|!\([^)]*\)"  # !(...)
        r"|!\[[^\]]*\]"  # ![...]
    )


def _extract_xonsh_expr(template, pos):
    """Extract a xonsh expression from template starting at or near pos."""
    m = RE_XONSH_EXPR.match(template, pos)
    if m is not None:
        return m.group()
    # The offset may point past a leading space: `{ $HOME }`
    if pos > 0:
        m = RE_XONSH_EXPR.match(template, pos - 1)
        if m is not None:
            return m.group()
    return None


class FStringAdaptor:
    """Helper for parsing Xonsh syntax within f-strings."""

    def __init__(self, fstring, prefix, filename=None):
        """Parses an f-string containing special Xonsh syntax and returns
        ast.JoinedStr AST node instance representing the input string.

        Parameters
        ----------
        fstring : str
            The input f-string.
        prefix : str
            Prefix of the f-string (e.g. "fr").
        filename : str, optional
            File from which the code was read or any string describing
            origin of the code.
        """
        self.fstring = fstring
        self.prefix = prefix
        self.filename = filename
        self.fields = {}
        self._field_counter = 0
        self.repl = ""
        self.res = None

    def _patch_special_syntax(self):
        """Takes an fstring (and its prefix, ie "f") that may contain
        xonsh expressions as its field values and substitues them for
        a call to __xonsh__.eval_fstring_field as needed.
        """
        prelen = len(self.prefix)
        quote = self.fstring[prelen]
        if self.fstring[prelen + 1] == quote:
            quote *= 3
        template = self.fstring[prelen + len(quote) : -len(quote)]
        while True:
            repl = self.prefix + quote + template + quote
            try:
                res = pyparse(repl)
                break
            except SyntaxError as e:
                # The e.text attribute is expected to contain the failing
                # expression, e.g. "($HOME)" for f"{$HOME}" string.
                if PYTHON_VERSION_INFO < (3, 12):
                    if (e.text is None) or (e.text[0] != "("):
                        raise

                    error_expr = e.text.strip()[1:-1]
                    epos = template.find(error_expr)
                    if epos < 0:
                        raise
                else:
                    # Python 3.12+ reports the error with offset pointing
                    # to the '$' character. e.text is the failing source
                    # line, e.offset is 1-based within that line, and
                    # e.lineno indicates which line (for multi-line strings).
                    if e.text is None or e.offset is None:
                        raise
                    # Find the error position within e.text
                    err_col = e.offset - 1  # 0-based column in e.text
                    # For line 1, skip the prefix and opening quote
                    if e.lineno == 1:
                        err_col -= prelen + len(quote)
                    # Locate the corresponding position in template
                    if e.lineno == 1:
                        epos = err_col
                    else:
                        # Skip to the start of line e.lineno within template
                        line_start = 0
                        for _ in range(e.lineno - 1):
                            nl = template.find("\n", line_start)
                            if nl < 0:
                                break
                            line_start = nl + 1
                        epos = line_start + err_col
                    if epos < 0 or epos >= len(template):
                        raise
                    # Extract xonsh expression at this position
                    error_expr = _extract_xonsh_expr(template, epos)
                    if error_expr is None:
                        raise
                    epos = template.find(error_expr, max(0, epos - 1))

            # We can only get here in the case of handled SyntaxError.
            # Patch the last error and start over.
            xonsh_field = (error_expr, self.filename if self.filename else None)
            self._field_counter += 1
            field_id = self._field_counter
            self.fields[field_id] = xonsh_field
            eval_field = f"__xonsh__.eval_fstring_field({field_id})"
            template = template[:epos] + eval_field + template[epos + len(error_expr) :]

        self.repl = repl
        self.res = res.body[0].value

    def _unpatch_strings(self):
        """Reverts false-positive field matches within strings."""
        reparse = False
        for node in ast.walk(self.res):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
            elif ast.is_const_str(node):
                value = node.value
            else:
                continue

            match = RE_FSTR_FIELD_WRAPPER.search(value)
            if match is None:
                continue
            field = self.fields.pop(int(match.group(2)), None)
            if field is None:
                continue
            self.repl = self.repl.replace(match.group(1), field[0], 1)
            reparse = True

        if reparse:
            self.res = pyparse(self.repl).body[0].value

    def _unpatch_selfdoc_strings(self):
        """Reverts false-positive matches within Python 3.8 sef-documenting
        f-string expressions."""
        for node in ast.walk(self.res):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
            elif ast.is_const_str(node):
                value = node.value
            else:
                continue

            match = RE_FSTR_SELF_DOC_FIELD_WRAPPER.search(value)
            if match is None:
                continue
            field = self.fields.get(int(match.group(2)), None)
            if field is None:
                continue
            value = value.replace(match.group(1), field[0], 1)

            node.value = value

    def _fix_eval_field_params(self):
        """Replace f-string field ID placeholders with the actual field
        expressions."""
        for node in ast.walk(self.res):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "__xonsh__"
                and node.func.attr == "eval_fstring_field"
                and len(node.args) > 0
            ):
                continue

            if PYTHON_VERSION_INFO > (3, 8):
                if isinstance(node.args[0], ast.Constant) and isinstance(
                    node.args[0].value, int
                ):
                    field = self.fields.pop(node.args[0].value, None)
                    if field is None:
                        continue
                    lineno = node.args[0].lineno
                    col_offset = node.args[0].col_offset
                    field_node = ast.Tuple(
                        elts=[
                            ast.Constant(
                                value=field[0], lineno=lineno, col_offset=col_offset
                            ),
                            ast.Constant(
                                value=field[1], lineno=lineno, col_offset=col_offset
                            ),
                        ],
                        ctx=ast.Load(),
                        lineno=lineno,
                        col_offset=col_offset,
                    )
                    node.args[0] = field_node
            elif ast.is_const_num(node.args[0]):
                field = self.fields.pop(node.args[0].value, None)
                if field is None:
                    continue
                lineno = node.args[0].lineno
                col_offset = node.args[0].col_offset
                elts = [ast.const_str(s=field[0], lineno=lineno, col_offset=col_offset)]
                if field[1] is not None:
                    elts.append(
                        ast.const_str(s=field[1], lineno=lineno, col_offset=col_offset)
                    )
                else:
                    elts.append(
                        ast.const_name(value=None, lineno=lineno, col_offset=col_offset)
                    )
                field_node = ast.Tuple(
                    elts=elts, ctx=ast.Load(), lineno=lineno, col_offset=col_offset
                )
                node.args[0] = field_node

    def run(self):
        """Runs the parser. Returns ast.JoinedStr instance."""
        self._patch_special_syntax()
        self._unpatch_strings()
        if PYTHON_VERSION_INFO > (3, 8):
            self._unpatch_selfdoc_strings()
        self._fix_eval_field_params()
        assert len(self.fields) == 0
        return self.res
