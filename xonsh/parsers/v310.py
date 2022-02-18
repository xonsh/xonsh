"""Handles changes since PY310

handle
- import-alias requiring lineno
- match statement
- xonsh additions to pythons match statement
"""

import ast
import uuid

from xonsh.parsers.base import RE_SEARCHPATH
from xonsh.parsers.v39 import Parser as ThreeNineParser
from xonsh.ply.ply import yacc


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

    @staticmethod
    def _walk_ast_including_xonsh_patterns(root, /, only_xonsh_patterns):

        for child in ast.walk(root):
            match child:
                case ast.MatchValue(
                    __xonsh_match_pattern__=subpattern
                ) as xonsh_pattern:
                    yield xonsh_pattern

                    if subpattern is not None:
                        yield from Parser._walk_ast_including_xonsh_patterns(
                            subpattern, only_xonsh_patterns
                        )
                case non_xonsh_node:
                    if not only_xonsh_patterns:
                        yield non_xonsh_node

    @staticmethod
    def _get_match_target_names_of_node(node):
        match node:
            case ast.MatchAs(name=name) if name is not None:
                return [name]
            case ast.MatchMapping(rest=name) if name is not None:
                return [name]
            case ast.MatchStar(name=name) if name is not None:
                return [name]
        return []

    @staticmethod
    def _get_match_target_names_below_node(root):
        names = set()

        for child in Parser._walk_ast_including_xonsh_patterns(
            root, only_xonsh_patterns=False
        ):
            if new_names := Parser._get_match_target_names_of_node(child):
                names.update(new_names)

        return names

    @staticmethod
    def _xonsh_pattern_has_sub_xonsh_pattern(xonsh_pattern):
        if xonsh_pattern.__xonsh_match_pattern__ is None:
            return False
        else:
            return (
                len(
                    list(
                        Parser._walk_ast_including_xonsh_patterns(
                            xonsh_pattern.__xonsh_match_pattern__,
                            only_xonsh_patterns=True,
                        )
                    )
                )
                != 0
            )

    @staticmethod
    def _node_contains_xonsh_pattern(node):
        return (
            len(
                list(
                    Parser._walk_ast_including_xonsh_patterns(
                        node, only_xonsh_patterns=True
                    )
                )
            )
            != 0
        )

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

        match_loc = self.get_line_cols(p, 1)

        p[0] = self.compile_match_statement(
            subject_expr, case_block_list_nonempty, match_loc
        )

    def compile_match_statement(self, subject_expr, cases, match_loc):
        """
        Compile match statements that may contain xonsh-special patterns to regular python
        If no special patterns occur, produce exactly the ast python would produce
        """

        match_stmt = ast.Match(**match_loc, subject=subject_expr, cases=cases)

        # name to use in compiled (throw-away) classes and values
        prefix = f"_{uuid.uuid4().hex}"

        # identify all match targets (i.e. names that may be assigned during a match)
        match_targets = []
        for case in match_stmt.cases:
            match_targets.extend(Parser._get_match_target_names_below_node(case))

        # collect key-value pairs of the generated variables that will later be stored in the attribute proxy
        matcher_proxy_init_keywords = []

        # compile expression patterns by assigning a key-name to each expression that will be stored in the attribute proxy
        name_counter = 0
        for case in match_stmt.cases:
            for node in Parser._walk_ast_including_xonsh_patterns(
                case, only_xonsh_patterns=False
            ):
                match node:
                    case ast.Attribute(__xonsh_match_object__=key_expr) as attr:
                        del attr.__xonsh_match_object__

                        attr.value = ast.Name(
                            id=f"{prefix}_attribute_proxy", ctx=ast.Load()
                        )
                        attr.attr = f"injected_attribute_{name_counter}"
                        attr.ctx = ast.Load()

                        name_counter += 1

                        keyword = ast.keyword(arg=attr.attr, value=key_expr)

                        matcher_proxy_init_keywords.append(keyword)

        # compute all matched variable names for each safe transformer pattern
        for case in match_stmt.cases:
            for xonsh_pattern in Parser._walk_ast_including_xonsh_patterns(
                case, only_xonsh_patterns=True
            ):
                xonsh_pattern.__xonsh_match_names__ = (
                    Parser._get_match_target_names_below_node(xonsh_pattern)
                )

        # assign attribute names of attribute proxy to safe transformer occurrences (similar to what is done above for expression patterns)
        name_counter = 0
        for case in match_stmt.cases:
            for xonsh_pattern in Parser._walk_ast_including_xonsh_patterns(
                case, only_xonsh_patterns=True
            ):

                xonsh_pattern.value = ast.Attribute(
                    value=ast.Name(id=f"{prefix}_attribute_proxy", ctx=ast.Load()),
                    attr=f"pattern_{name_counter}",
                    ctx=ast.Load(),
                )

                name_counter += 1

            ast.fix_missing_locations(case)

        # iteratively prune the tree from the leaves upwards by replacing safe transformer patterns by corresponding attribute lookups
        # and generate the necessary proxy classes along the way
        matcher_class_defs = []
        class_names = []
        for case in match_stmt.cases:
            while Parser._node_contains_xonsh_pattern(case):
                # find xonsh pattern that has no xonsh pattern below
                for xonsh_pattern in Parser._walk_ast_including_xonsh_patterns(
                    case, only_xonsh_patterns=True
                ):
                    if Parser._xonsh_pattern_has_sub_xonsh_pattern(xonsh_pattern):
                        continue
                    else:

                        subpattern, match_object, match_names = (
                            xonsh_pattern.__xonsh_match_pattern__,
                            xonsh_pattern.__xonsh_match_object__,
                            xonsh_pattern.__xonsh_match_names__,
                        )

                        # transform xonsh_pattern into a regular pattern
                        del xonsh_pattern.__xonsh_match_pattern__
                        del xonsh_pattern.__xonsh_match_object__
                        del xonsh_pattern.__xonsh_match_names__

                        class_name = prefix + "_" + xonsh_pattern.value.attr + "_class"
                        class_names.append(class_name)

                        class_def = Parser._build_matcher_class(
                            prefix,
                            class_name,
                            subpattern,
                            match_object,
                            match_names,
                            match_loc,
                        )
                        matcher_class_defs.append(class_def)

                        keyword = ast.keyword(
                            arg=xonsh_pattern.value.attr,
                            value=ast.Call(
                                func=ast.Name(id=class_name, ctx=ast.Load()),
                                args=[],
                                keywords=[],
                            ),
                        )

                        matcher_proxy_init_keywords.append(keyword)

        transformer_patterns_used = bool(matcher_proxy_init_keywords)

        # statement to add our generated attributes to the attribute proxy
        matcher_proxy_update_stmt = ast.Assign(
            targets=[ast.Name(id=f"{prefix}_attribute_proxy", ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="__xonsh__", ctx=ast.Load()),
                    attr="MatchProxyDict",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=matcher_proxy_init_keywords,
            ),
        )

        # statement to delete our single use proxy class definitions
        class_del_stmts = (
            [
                ast.Delete(
                    **match_loc,
                    targets=[
                        ast.Name(id=class_name, ctx=ast.Del())
                        for class_name in class_names
                    ],
                )
            ]
            if class_names
            else []
        )

        # Generate setter closures
        generate_setters = [
            ast.Assign(
                targets=[ast.Name(id=f"{prefix}_setters", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="dict", ctx=ast.Load()), args=[], keywords=[]
                ),
            )
        ]

        for name in match_targets:
            generate_setters.extend(Parser.generate_setter_closure(prefix, name))

        # if we generated classes, add a try block to ensure the generated variables get deleted eventually
        if transformer_patterns_used:

            match_proxy_init_and_match = [
                *matcher_class_defs,
                *generate_setters,
                matcher_proxy_update_stmt,
                *class_del_stmts,
                match_stmt,
            ]

            cleanup_try = ast.Try(
                **match_loc,
                body=match_proxy_init_and_match,
                handlers=[],
                orelse=[],
                finalbody=[
                    ast.If(
                        test=ast.Compare(
                            left=ast.Constant(value=f"{prefix}_attribute_proxy"),
                            ops=[ast.In()],
                            comparators=[
                                ast.Call(
                                    func=ast.Name(id="locals", ctx=ast.Load()),
                                    args=[],
                                    keywords=[],
                                )
                            ],
                        ),
                        body=[
                            ast.Delete(
                                targets=[
                                    ast.Name(
                                        id=f"{prefix}_attribute_proxy", ctx=ast.Del()
                                    ),
                                ]
                            )
                        ],
                        orelse=[],
                    ),
                    ast.If(
                        test=ast.Compare(
                            left=ast.Constant(value=f"{prefix}_setters"),
                            ops=[ast.In()],
                            comparators=[
                                ast.Call(
                                    func=ast.Name(id="locals", ctx=ast.Load()),
                                    args=[],
                                    keywords=[],
                                )
                            ],
                        ),
                        body=[
                            ast.Delete(
                                targets=[
                                    ast.Name(id=f"{prefix}_setters", ctx=ast.Del()),
                                ]
                            )
                        ],
                        orelse=[],
                    ),
                ],
            )

            compiled_match_stmt = [cleanup_try]

        else:
            compiled_match_stmt = [match_stmt]

        for stmt in compiled_match_stmt:
            ast.fix_missing_locations(stmt)

        if __xonsh__.env["XONSH_DEBUG"]:
            print("*" * 70)
            print("# Generated match-statement code:")
            print(ast.unparse(compiled_match_stmt))
            print("*" * 70)

        return compiled_match_stmt

    # convert nonlocal statements that refer to the global scope that were defined during match-code generation to global statements
    # (see generate_setter_closure)
    def p_start_symbols(self, p):
        """
        start_symbols : single_input
                      | file_input
                      | eval_input
                      | empty
        """
        assert Parser.p_start_symbols.__doc__ == ThreeNineParser.p_start_symbols.__doc__

        p[0] = p[1]

        if p[0] == None:
            return

        # mark all nonlocal statements that were generated by generate_setter_closure that are below some function that was not generated by generate_setter_closure
        for node in ast.walk(p[0]):
            match node:
                # TODO proper check
                case ast.FunctionDef(
                    name=name
                ) as non_setter_closure if not "_xonsh_setter_closure_" in name:
                    for sub_non_setter_closure in ast.walk(non_setter_closure):
                        match sub_non_setter_closure:
                            case ast.Nonlocal(__xonsh__=True) as nonlocal_:
                                nonlocal_.__marked__ = True

        class RewriteNonlocal(ast.NodeTransformer):
            def visit_Nonlocal(self, node):

                # only modify nonlocals generated by generate_setter_closure
                if not hasattr(node, "__xonsh__"):
                    return node

                # replace nonlocals in global scope with gloabls
                if not hasattr(node, "__marked__"):
                    return ast.Global(names=node.names)
                else:
                    del node.__marked__, node.__xonsh__
                    return node

        p[0] = ast.fix_missing_locations(RewriteNonlocal().visit(p[0]))

    @staticmethod
    def generate_setter_closure(prefix, varname):
        """
        Generate a setter method for a particular variable in local scope that can be passed to other scopes.
        This is done this way, because
          -) changes to a locals() dict will not propagate if locals() does not refer to the global scope
          -) modifying the stack via the inspect module is not reliable due to optimizations in cpython

        This will generate 'nonlocal' statements. If the generated code is used in the global namespace, the nonlocal statement will raise a SyntaxError and should be replaced by a 'global' statement
        Since this information is not available in this context, the nonlocal -> global transformation is conducted after parsing has finished in p_start_symbols
        """

        funcname = f"{prefix}_xonsh_setter_closure_{varname}"
        return [
            ast.If(
                test=ast.Constant(value=False),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=varname, ctx=ast.Store())],
                        value=ast.Constant(value=None),
                    )
                ],
                orelse=[],
            ),
            ast.FunctionDef(
                name=funcname,
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg=f"{prefix}_new_value")],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=[
                    ast.Nonlocal(__xonsh__=True, names=[varname]),
                    ast.Assign(
                        targets=[ast.Name(id=varname, ctx=ast.Store())],
                        value=ast.Name(id=f"{prefix}_new_value", ctx=ast.Load()),
                    ),
                ],
                decorator_list=[],
            ),
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id=f"{prefix}_setters", ctx=ast.Load()),
                        slice=ast.Constant(value=varname),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id=funcname, ctx=ast.Load()),
            ),
            ast.Delete(targets=[ast.Name(id=funcname, ctx=ast.Del())]),
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
                assert False

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
                assert False

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
                assert False

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
                assert False

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

                       | expression_pattern
                       | predicate_pattern
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

                assert False, "patterns may not match formatted string literals"
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
                assert False

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
                assert False

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
                assert False

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
                assert False

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
                assert False

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
                assert False

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
                assert False

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
                assert False

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
                assert False

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
                assert False

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

    def p_key_value_pattern_expr(self, p):
        """
        key_value_pattern : expression_pattern COLON pattern
        """
        _, expression_pattern, _, value = p

        key_expr_injected_attribute = expression_pattern.value

        p[0] = key_expr_injected_attribute, value

    # Xonsh-specific patterns

    # Regex pattern
    def p_regex_pattern(self, p):
        """
        closed_pattern : SEARCHPATH
                       | closed_pattern RARROW SEARCHPATH
        """

        match list(p):
            case [_, searchpath]:
                subpattern = None
            case [_, subpattern, _, searchpath]:
                pass
            case _:
                assert False

        searchfunc, regex_pattern = RE_SEARCHPATH.match(searchpath).groups()

        if searchfunc:
            searchfunc = searchfunc.strip("@")
            searchfunc_node = ast.Name(id=searchfunc, ctx=ast.Load())
        else:
            searchfunc_node = ast.Attribute(
                value=ast.Name(id="__xonsh__", ctx=ast.Load()),
                attr="build_regex_match_transformer",
                ctx=ast.Load(),
            )

        # Regex patterns are implemented via safe transform pattern
        match_object = ast.Call(
            func=searchfunc_node,
            args=[
                ast.Constant(value=regex_pattern),
                ast.Constant(value=bool(subpattern)),
            ],
            keywords=[],
        )

        p[0] = ast.MatchValue(
            value=None,
            __xonsh_match_object__=match_object,
            __xonsh_match_pattern__=subpattern,
            **self.get_line_cols(p, 1),
        )

    # Safe transform pattern
    def p_safe_transform_pattern(self, p):
        """
        closed_pattern : closed_pattern RARROW test
        """
        _, pattern, _, transformer_expr = p
        p[0] = ast.MatchValue(
            value=None,
            __xonsh_match_object__=transformer_expr,
            __xonsh_match_pattern__=pattern,
            **self.get_line_cols(p, 1),
        )

    # Expression pattern
    def p_expression_pattern(self, p):
        """
        expression_pattern : dollar_rule_atom
                           | atom_dname
                           | AT_LPAREN test RPAREN
        """

        loc = self.get_line_cols(p, 1)
        match list(p):
            case [_, expr]:
                pass
            case [_, _, expr, _]:
                pass

        p[0] = ast.MatchValue(
            value=ast.Attribute(__xonsh_match_object__=expr, **loc),
            **loc,
        )

    @staticmethod
    def _build_matcher_class(
        prefix, class_name, subpattern, match_object, match_names, loc
    ):
        """
        Generates single-use classes with special __eq__ hook to enable safe transformer and expression patterns via attribute lookup patterns
        (I.e. the special pattern will be replaced by an attribute name)
        Exceptions deriving from Exception will be caught and reported as match-failure. (BaseExceptions are not caught)

        Run xonsh with XONSH_DEBUG >= 0 to see the generated code on stdout.

        prefix ... the unique prefix used only for the current match statement
        class_name ... unique (throw-away)class name
        match_object ... ast node describing the transformer to use for the safe transformer patterns
                        For example, for predicate patterns this will be the ast node corresponding to the expression '__xonsh__.build_predicate_match_transformer(some_predicate)'
        subpattern ... If specified, transformer(other) in __eq__ will be matched against this to determine equality (exceptions during pattern matching will be ignored), otherwise other == transformer(other) is used
        match_names ... used if subpattern is given: store these names (captured) by subpattern to local scope
        """
        class_def = ast.ClassDef(
            **loc,
            name=class_name,
            bases=[ast.Name(id="object", ctx=ast.Load())],
            keywords=[],
            body=[
                ast.FunctionDef(
                    name="__eq__",
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[ast.arg(arg="self"), ast.arg(arg="other")],
                        kwonlyargs=[],
                        kw_defaults=[],
                        defaults=[],
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id="transformer", ctx=ast.Store())],
                            value=match_object,
                        ),
                        ast.Try(
                            body=[
                                ast.Match(
                                    subject=ast.Call(
                                        func=ast.Name(id="transformer", ctx=ast.Load()),
                                        args=[ast.Name(id="other", ctx=ast.Load())],
                                        keywords=[],
                                    ),
                                    cases=[
                                        ast.match_case(
                                            pattern=subpattern,
                                            body=[
                                                *[
                                                    ast.Expr(
                                                        value=ast.Call(
                                                            func=ast.Subscript(
                                                                value=ast.Name(
                                                                    id=f"{prefix}_setters",
                                                                    ctx=ast.Load(),
                                                                ),
                                                                slice=ast.Constant(
                                                                    value=name
                                                                ),
                                                                ctx=ast.Load(),
                                                            ),
                                                            args=[
                                                                ast.Name(
                                                                    id=name,
                                                                    ctx=ast.Load(),
                                                                )
                                                            ],
                                                            keywords=[],
                                                        )
                                                    )
                                                    for name in match_names
                                                ],
                                                ast.Return(
                                                    value=ast.Constant(value=True)
                                                ),
                                            ],
                                        ),
                                    ],
                                )
                                if subpattern is not None
                                else ast.Return(
                                    value=ast.Compare(
                                        left=ast.Name(id="other", ctx=ast.Load()),
                                        ops=[ast.Eq()],
                                        comparators=[
                                            ast.Call(
                                                func=ast.Name(
                                                    id="transformer", ctx=ast.Load()
                                                ),
                                                args=[
                                                    ast.Name(id="other", ctx=ast.Load())
                                                ],
                                                keywords=[],
                                            )
                                        ],
                                    )
                                ),
                            ],
                            handlers=[
                                ast.ExceptHandler(
                                    type=ast.Name(id="Exception", ctx=ast.Load()),
                                    body=[
                                        ast.Pass(),
                                    ],
                                )
                            ],
                            orelse=[],
                            finalbody=[],
                        ),
                        ast.Return(value=ast.Constant(value=False)),
                    ],
                    decorator_list=[],
                ),
            ],
            decorator_list=[],
        )

        ast.fix_missing_locations(class_def)

        return class_def

    # Predicate pattern
    def p_predicate_pattern(self, p):
        """
        predicate_pattern : QUESTION test
        """

        match list(p):

            case [_, "?", ast.UnaryOp(op=ast.Not(), operand=predicate)]:
                func = "build_not_predicate_match_transformer"
            case [_, "?", predicate]:
                func = "build_predicate_match_transformer"
            case _:
                assert False

        # Predicate patterns are implemented via safe transformer patterns

        match_object = ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="__xonsh__", ctx=ast.Load()),
                attr=func,
                ctx=ast.Load(),
            ),
            args=[predicate],
            keywords=[],
        )

        p[0] = ast.MatchValue(
            value=None,
            __xonsh_match_object__=match_object,
            __xonsh_match_pattern__=None,
            **self.get_line_cols(p, 1),
        )
