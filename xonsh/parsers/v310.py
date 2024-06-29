# type: ignore
# TODO: remove line above once mypy understands the match statement

"""Handles changes since PY310

handle
- import-alias requiring lineno
- match statement
"""

import ast

from xonsh.parsers.ply import yacc
from xonsh.parsers.v39 import Parser as ThreeNineParser


class Parser(ThreeNineParser):
    def p_import_from_post_times(self, p):
        """import_from_post : TIMES"""
        p[0] = [ast.alias(name=p[1], asname=None, **self.get_line_cols(p, 1))]

    def p_import_as_name(self, p):
        """import_as_name : name_str as_name_opt"""
        self.p_dotted_as_name(p)

    def p_dotted_as_name(self, p: yacc.YaccProduction):
        """dotted_as_name : dotted_name as_name_opt"""
        alias_idx = 2
        p[0] = ast.alias(
            name=p[1], asname=p[alias_idx], **self.get_line_cols(p, alias_idx)
        )

    @staticmethod
    def get_line_cols(p: yacc.YaccProduction, idx: int):
        line_no, end_line_no = p.linespan(idx)
        col_offset, end_col_offset = p.lexspan(idx)
        return dict(
            lineno=line_no,
            end_lineno=end_line_no,
            col_offset=col_offset,
            end_col_offset=end_col_offset,
        )

    def _set_error_at_production_index(self, msg, p, i):
        error_loc = self.get_line_cols(p, i)
        err_lineno = error_loc["lineno"]
        err_column = error_loc["col_offset"] + 1
        self._set_error(msg, self.currloc(lineno=err_lineno, column=err_column))

    def p_compound_stmt_match(self, p):
        """
        compound_stmt : match_stmt
        """
        p[0] = p[1]

    def p_match_stmt(self, p):
        """
        match_stmt : match_tok subject_expr COLON NEWLINE INDENT case_block_list_nonempty DEDENT
        """

        _, _, subject_expr, _, _, _, case_block_list_nonempty, _ = p

        p[0] = [
            ast.Match(
                **self.get_line_cols(p, 1),
                subject=subject_expr,
                cases=case_block_list_nonempty,
            )
        ]

    # case blocks
    def p_case_block(self, p):
        """
        case_block : case_tok patterns COLON suite
                   | case_tok patterns IF test COLON suite
        """

        loc = self.get_line_cols(p, 1)
        match list(p):
            case [_, _, pattern, _, suite]:
                p[0] = ast.match_case(pattern=pattern, body=suite, **loc)
            case [_, _, pattern, _, guard, _, suite]:
                p[0] = ast.match_case(pattern=pattern, body=suite, guard=guard, **loc)
            case _:
                raise AssertionError()

    def p_case_block_list_nonempty(self, p):
        """
        case_block_list_nonempty : case_block
                                 | case_block case_block_list_nonempty
        """
        match list(p):
            case [_, case_block]:
                p[0] = [case_block]
            case [_, case_block, case_block_list_nonempty]:
                p[0] = [case_block] + case_block_list_nonempty
            case _:
                raise AssertionError()

    # subject expression
    def p_subject_expr_single_value(self, p):
        """
        subject_expr : test_or_star_expr comma_opt
        """

        match list(p):
            case [_, test_or_star_expr, None]:
                # single value
                p[0] = test_or_star_expr
            case [_, test_or_star_expr, ","]:
                # tuple with one element
                p[0] = ast.Tuple(
                    elts=[test_or_star_expr], ctx=ast.Load(), **self.get_line_cols(p, 1)
                )
            case _:
                raise AssertionError()

    def p_subject_expr_multiple_values(self, p):
        """
        subject_expr : test_or_star_expr comma_test_or_star_expr_list comma_opt
        """

        match list(p):
            case [_, test_or_star_expr, comma_test_or_star_expr_list, "," | None]:
                # tuple with more than one element
                p[0] = ast.Tuple(
                    elts=[test_or_star_expr] + comma_test_or_star_expr_list,
                    ctx=ast.Load(),
                    **self.get_line_cols(p, 1),
                )
            case _:
                raise AssertionError()

    # patterns
    def p_closed_pattern(self, p):
        """
        closed_pattern : literal_pattern
                       | capture_and_wildcard_pattern
                       | group_pattern
                       | sequence_pattern
                       | value_pattern
                       | class_pattern
                       | mapping_pattern
        """
        # productions from closed_pattern to regex_pattern and safe_transform_pattern are located below

        p[0] = p[1]

    def p_patterns(self, p):
        """
        patterns : pattern
                 | open_sequence_pattern
        """
        p[0] = p[1]

    def p_pattern(self, p):
        """
        pattern : or_pattern
                | as_pattern
        """
        p[0] = p[1]

    def p_or_pattern(self, p):
        """
        or_pattern : or_pattern_list
        """

        _, or_pattern_list = p

        match or_pattern_list:
            case [single_value]:
                p[0] = single_value
            case multiple_values:
                p[0] = ast.MatchOr(patterns=multiple_values, **self.get_line_cols(p, 1))

    def p_or_pattern_list(self, p):
        """
        or_pattern_list : closed_pattern
                        | closed_pattern PIPE or_pattern_list
        """
        match list(p):
            case [_, closed_pattern]:
                p[0] = [closed_pattern]
            case [_, closed_pattern, "|", or_pattern_list]:
                p[0] = [closed_pattern] + or_pattern_list

    # group pattern
    def p_group_pattern(self, p):
        """
        group_pattern : LPAREN pattern RPAREN
        """
        _, _, pattern, _ = p
        p[0] = pattern

    # literal pattern
    def p_literal_pattern(self, p):
        """
        literal_pattern : literal_expr
        """

        match p[1]:
            case None | True | False:
                p[0] = ast.MatchSingleton(value=p[1], **self.get_line_cols(p, 1))
            case _:
                p[0] = ast.MatchValue(value=p[1], **self.get_line_cols(p, 1))

    def p_literal_expr_number_or_string_literal_list(self, p):
        """
        literal_expr : complex_number
                     | string_literal_list
        """

        p[0] = p[1]

        match p[1]:
            case ast.JoinedStr():
                raise AssertionError("patterns may not match formatted string literals")
                # TODO: raise SyntaxError instead
                # (doing so currently somehow causes an IndexError in tools.py:get_logical_line)

        # TODO: f"hi" "hi" does not parse in xonsh

    def p_literal_expr_none_or_true_or_false(self, p):
        """
        literal_expr : none_tok
                     | true_tok
                     | false_tok
        """

        match p[1].value:
            case "None":
                value = None
            case "True":
                value = True
            case "False":
                value = False
            case _:
                raise AssertionError()

        p[0] = value

    def p_complex_number(self, p):
        """
        complex_number : number
                       | MINUS number
                       | number PLUS number
                       | number MINUS number
                       | MINUS number PLUS number
                       | MINUS number MINUS number
        """

        ops = {"+": ast.Add(), "-": ast.Sub()}
        build_complex = False
        loc = self.get_line_cols(p, 1)

        match list(p):
            case [_, x]:
                p[0] = x
            case [_, "-", x]:
                p[0] = ast.UnaryOp(op=ast.USub(), operand=x, **loc)
            case [_, left, ("+" | "-") as op_char, right]:
                build_complex = True
                negate_left_side = False
            case [_, "-", left, ("+" | "-") as op_char, right]:
                build_complex = True
                negate_left_side = True
            case _:
                raise AssertionError()

        if build_complex:
            # TODO raise syntax error instead (see reason in p_literal_expr_number_or_string_literal_list)
            assert isinstance(
                right.value, complex
            ), "right part of complex literal must be imaginary"

            if negate_left_side:
                left = ast.UnaryOp(op=ast.USub(), operand=left, **loc)

            p[0] = ast.BinOp(left=left, op=ops[op_char], right=right, **loc)

    # capture- and wildcard-pattern
    def p_as_pattern(self, p):
        """
        as_pattern : or_pattern AS capture_target_name
        """

        _, or_pattern, _, name = p

        p[0] = ast.MatchAs(pattern=or_pattern, name=name, **self.get_line_cols(p, 1))

    def p_capture_target_name(self, p):
        """
        capture_target_name : name_str
        """
        name = p[1]
        if name == "_":
            self._set_error_at_production_index(
                "can't capture name '_' in patterns", p, 1
            )
        p[0] = name

    def p_capture_and_wildcard_pattern(self, p):
        """
        capture_and_wildcard_pattern : name_str
        """
        # TODO: according to the spec we would need the negative lookahead !('.' | '(' | '=')
        # (also in p_star_pattern, p_value_pattern)
        # but parsing seems to work just fine

        _, name = p

        target = name if name != "_" else None

        p[0] = ast.MatchAs(name=target, **self.get_line_cols(p, 1))

    # sequence pattern
    def p_sequence_pattern_square_brackets(self, p):
        """
        sequence_pattern : LBRACKET maybe_sequence_pattern RBRACKET
                         | LBRACKET RBRACKET
                         | LPAREN open_sequence_pattern RPAREN
                         | LPAREN RPAREN
        """

        match list(p):
            case [_, _, ast.MatchSequence() as seq, _]:
                p[0] = seq
            case [_, _, single_item, _]:
                p[0] = ast.MatchSequence(
                    patterns=[single_item], **self.get_line_cols(p, 1)
                )
            case [_, _, _]:
                p[0] = ast.MatchSequence(patterns=[], **self.get_line_cols(p, 1))
            case _:
                raise AssertionError()

    def p_maybe_sequence_pattern(self, p):
        """
        maybe_sequence_pattern : maybe_star_pattern comma_opt
                               | maybe_star_pattern COMMA maybe_sequence_pattern
        """

        match list(p):
            case [_, maybe_star_pattern, ","]:
                p[0] = ast.MatchSequence(
                    patterns=[maybe_star_pattern], **self.get_line_cols(p, 1)
                )
            case [_, maybe_star_pattern, None]:
                p[0] = maybe_star_pattern
            case [
                _,
                maybe_star_pattern,
                ",",
                ast.MatchSequence(patterns=list(maybe_sequence_pattern)),
            ]:
                p[0] = ast.MatchSequence(
                    patterns=[maybe_star_pattern] + maybe_sequence_pattern,
                    **self.get_line_cols(p, 1),
                )
            case [_, maybe_star_pattern, ",", maybe_sequence_pattern]:
                p[0] = ast.MatchSequence(
                    patterns=[maybe_star_pattern, maybe_sequence_pattern],
                    **self.get_line_cols(p, 1),
                )
            case _:
                raise AssertionError()

    def p_open_sequence_pattern(self, p):
        """
        open_sequence_pattern : maybe_star_pattern COMMA
                              | maybe_star_pattern COMMA maybe_sequence_pattern
        """
        self.p_maybe_sequence_pattern(p)

    def p_maybe_star_pattern(self, p):
        """
        maybe_star_pattern : pattern
                           | star_pattern
        """

        p[0] = p[1]

    def p_star_pattern(self, p):
        """
        star_pattern : TIMES name_str
        """

        _, _, name = p
        target = name if name != "_" else None

        p[0] = ast.MatchStar(name=target, **self.get_line_cols(p, 1))

    def p_value_pattern(self, p):
        """
        value_pattern : attr_name_with
        """

        p[0] = ast.MatchValue(value=p[1], **self.get_line_cols(p, 1))

    # This is implemented via this 'chain' grammer since implementing the grammar from the spec verbatim leads to bad parser states (regarding comma tokens)
    def p_class_pattern(self, p):
        """
        class_pattern : attr_name LPAREN class_pattern_positional_part_start RPAREN
        """

        positional_patterns, keyword_patterns_key_value_tuple_list = p[3]

        if keyword_patterns_key_value_tuple_list:
            # transpose, e.g. [ (a, 1), (b, 2) ] to [a, b], [1, 2]
            kwd_attrs, kwd_patterns = list(zip(*keyword_patterns_key_value_tuple_list))
        else:
            kwd_attrs, kwd_patterns = [], []

        p[0] = ast.MatchClass(
            cls=p[1],
            patterns=positional_patterns,
            kwd_attrs=list(kwd_attrs),
            kwd_patterns=list(kwd_patterns),
            **self.get_line_cols(p, 1),
        )

    # returns ( [pattern], [ (name, pattern) ]  )
    def p_class_pattern_positional_part_start(self, p):
        """
        class_pattern_positional_part_start :
                                            | pattern
                                            | pattern COMMA class_pattern_positional_part
                                            | name_str EQUALS pattern
                                            | name_str EQUALS pattern COMMA class_pattern_keyword_part
        """

        match list(p):
            case [_]:
                p[0] = ([], [])
            case [_, pattern]:
                p[0] = ([pattern], [])
            case [_, pattern, ",", (names, patterns)]:
                p[0] = ([pattern] + names, patterns)
            case [_, name, "=", pattern]:
                p[0] = ([], [(name, pattern)])
            case [_, name, "=", pattern, ",", class_pattern_keyword_part]:
                p[0] = ([], [(name, pattern)] + class_pattern_keyword_part)
            case _:
                raise AssertionError()

    # returns ( [pattern], [ (name, pattern) ]  )
    def p_class_pattern_positional_part_skip(self, p):
        """
        class_pattern_positional_part : class_pattern_keyword_part
        """
        p[0] = ([], p[1])

    # returns ( [pattern], [ (name, pattern) ]  )
    def p_class_pattern_positional_part(self, p):
        """
        class_pattern_positional_part : pattern
                                      | pattern COMMA class_pattern_positional_part
        """

        match list(p):
            case [_, pattern]:
                p[0] = ([pattern], [])
            case [_, pattern, ",", (names, patterns)]:
                p[0] = ([pattern] + names, patterns)
            case _:
                raise AssertionError()

    # returns [ (name, pattern) ]
    def p_class_pattern_keyword_part(self, p):
        """
        class_pattern_keyword_part :
                                   | COMMA
                                   | name_str EQUALS pattern
                                   | name_str EQUALS pattern COMMA class_pattern_keyword_part
        """

        match list(p):
            case [_] | [_, ","]:
                p[0] = []
            case [_, name, "=", pattern]:
                p[0] = [(name, pattern)]
            case [_, name, "=", pattern, ",", class_pattern_keyword_part]:
                p[0] = [(name, pattern)] + class_pattern_keyword_part
            case _:
                raise AssertionError()

    # Mapping pattern

    def p_mapping_pattern(self, p):
        """
        mapping_pattern : LBRACE mapping_pattern_args_start RBRACE
        """

        _, _, (keys, patterns, rest), _ = p

        p[0] = ast.MatchMapping(
            keys=keys, patterns=patterns, rest=rest, **self.get_line_cols(p, 1)
        )

    # see p_class_pattern for rationale
    def p_mapping_pattern_args_start(self, p):
        """
        mapping_pattern_args_start :
                                   | key_value_pattern
                                   | key_value_pattern COMMA mapping_pattern_args_item_part
                                   | double_star_pattern
        """
        match list(p):
            case [_]:
                p[0] = [], [], None
            case [_, (key, value)]:
                p[0] = [key], [value], None
            case [_, (key, value), ",", (keys, values, rest)]:
                p[0] = [key] + keys, [value] + values, rest
            case [_, str(double_star_pattern)]:
                p[0] = [], [], double_star_pattern
            case _:
                raise AssertionError()

    def p_mapping_pattern_args_item_part_skip(self, p):
        """
        mapping_pattern_args_item_part :
                                       | double_star_pattern
        """
        match list(p):
            case [_]:
                p[0] = [], [], None
            case [_, rest]:
                p[0] = [], [], rest
            case _:
                raise AssertionError()

    def p_mapping_pattern_args_item_part(self, p):
        """
        mapping_pattern_args_item_part : key_value_pattern
                                       | key_value_pattern COMMA mapping_pattern_args_item_part
        """
        match list(p):
            case [_, (key, value)]:
                p[0] = [key], [value], None
            case [_, (key, value), ",", (keys, values, rest)]:
                p[0] = [key] + keys, [value] + values, rest
            case _:
                raise AssertionError()

    def p_double_star_pattern(self, p):
        """
        double_star_pattern : POW capture_target_name comma_opt
        """
        p[0] = p[2]

    def p_key_value_pattern(self, p):
        """
        key_value_pattern : literal_expr COLON pattern
                          | attr_name_with COLON pattern
        """
        _, key, _, value = p
        p[0] = key, value
