"""PEP 701 f-string grammar rules for the PLY parser (Python 3.12+).

Provides a mixin class ``FStringRules`` with all ``p_fstring_*`` methods
that assemble FSTRING_START / FSTRING_MIDDLE / FSTRING_END tokens into
``ast.JoinedStr`` and ``ast.FormattedValue`` AST nodes.
"""

from ast import parse as pyparse
from ast import unparse as ast_unparse

from xonsh.parsers import ast
from xonsh.parsers.ast import xonsh_call


class FStringRules:
    """Mixin providing PEP 701 f-string grammar rules for the xonsh PLY parser."""

    def p_string_literal_fstring(self, p):
        """string_literal : fstring_expr"""
        p[0] = p[1]

    def p_fstring_expr(self, p):
        """fstring_expr : FSTRING_START fstring_content FSTRING_END"""
        s1 = p.slice[1]
        fstart = s1.value
        prefix = fstart.rstrip("'\"").lower()
        quote = fstart[len(fstart.rstrip("'\"")):]
        is_raw = "r" in prefix
        values = p[2]
        # Process escape sequences in FSTRING_MIDDLE Constant values
        if not is_raw:
            for node in values:
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    try:
                        node.value = pyparse(
                            quote + node.value + quote
                        ).body[0].value.value
                    except SyntaxError:
                        pass
        s = ast.JoinedStr(
            values=values, lineno=s1.lineno, col_offset=s1.lexpos,
        )
        if "p" in prefix:
            p[0] = xonsh_call(
                "__xonsh__.path_literal", [s],
                lineno=s1.lineno, col=s1.lexpos,
            )
        else:
            p[0] = s

    def p_fstring_content_empty(self, p):
        """fstring_content : empty"""
        p[0] = []

    def p_fstring_content_middle(self, p):
        """fstring_content : fstring_content FSTRING_MIDDLE"""
        s = p.slice[2]
        node = ast.Constant(
            value=p[2], lineno=s.lineno, col_offset=s.lexpos,
        )
        p[0] = p[1] + [node]

    def p_fstring_content_replacement(self, p):
        """fstring_content : fstring_content LBRACE testlist_comp fstring_conversion fstring_format_spec RBRACE"""
        conversion = p[4]
        format_spec = p[5]
        s2 = p.slice[2]
        fv = ast.FormattedValue(
            value=p[3],
            conversion=conversion,
            format_spec=format_spec,
            lineno=s2.lineno,
            col_offset=s2.lexpos,
        )
        p[0] = p[1] + [fv]

    def p_fstring_content_replacement_selfdoc(self, p):
        """fstring_content : fstring_content LBRACE testlist_comp EQUALS fstring_conversion fstring_format_spec RBRACE"""
        # Self-documenting expression: f"{expr=}"
        # Produces the text "expr=" followed by the formatted value
        conversion = p[5]
        format_spec = p[6]
        s2 = p.slice[2]
        expr_text = ast_unparse(p[3]) + "="
        text_node = ast.Constant(
            value=expr_text,
            lineno=s2.lineno, col_offset=s2.lexpos,
        )
        # Default to repr conversion only when no format spec is given
        if conversion == -1 and format_spec is None:
            conversion = ord("r")
        fv = ast.FormattedValue(
            value=p[3],
            conversion=conversion,
            format_spec=format_spec,
            lineno=s2.lineno,
            col_offset=s2.lexpos,
        )
        p[0] = p[1] + [text_node, fv]

    def p_fstring_conversion_empty(self, p):
        """fstring_conversion : empty"""
        p[0] = -1

    def p_fstring_conversion(self, p):
        """fstring_conversion : BANG NAME"""
        p[0] = ord(p[2])

    def p_fstring_format_spec_empty(self, p):
        """fstring_format_spec : empty"""
        p[0] = None

    def p_fstring_format_spec(self, p):
        """fstring_format_spec : COLON fstring_format_content"""
        # Format spec values don't need escape processing —
        # they are interpreted literally by the format() function.
        s1 = p.slice[1]
        p[0] = ast.JoinedStr(
            values=p[2], lineno=s1.lineno, col_offset=s1.lexpos,
        )

    def p_fstring_format_content_empty(self, p):
        """fstring_format_content : empty"""
        p[0] = []

    def p_fstring_format_content_middle(self, p):
        """fstring_format_content : fstring_format_content FSTRING_MIDDLE"""
        s = p.slice[2]
        node = ast.Constant(
            value=p[2], lineno=s.lineno, col_offset=s.lexpos,
        )
        p[0] = p[1] + [node]

    def p_fstring_format_content_field(self, p):
        """fstring_format_content : fstring_format_content LBRACE testlist_comp RBRACE"""
        s2 = p.slice[2]
        fv = ast.FormattedValue(
            value=p[3], conversion=-1, format_spec=None,
            lineno=s2.lineno, col_offset=s2.lexpos,
        )
        p[0] = p[1] + [fv]
