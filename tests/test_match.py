"""Tests the xonsh match statement."""

import ast
from tools import skip_if_pre_3_10
from test_parser import check_xonsh_ast, xsh, parser


@skip_if_pre_3_10
def test_expression_pattern(check_xonsh_ast):
    src = """
$x = 1
$y = 4

result = []
for x in [1, 2, "3\\n", 4, {5 : "e"}]:
    match x:
        case $x:
            result.append("a")
        case @(1+1):
            result.append("b")
        case $(echo 3):
            result.append("c")
        case ${"y"}:
            result.append("d")
        case {@(4+1) : _}:
            result.append("e")
        case _:
            raise f"no match for {x}"
"""

    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))

    assert ctx["result"] == ["a", "b", "c", "d", "e"]


@skip_if_pre_3_10
def test_regex_pattern_simple(check_xonsh_ast):
    src = """

def f(x):
    match x:
        case `.irst` as x:
            return x
        case [s, cond] -> `(s)e(cond)` as x:
            return s, cond, x
        case x -> `(thi)r(d)` as y:
            return x, y
        case _:
            return f"no match for {x}"

result = [f(x) for x in ['first', 'second', 'third']]
"""

    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))

    assert ctx["result"] == ["first", ("s", "cond", "second"), (["thi", "d"], "third")]
    assert all(undefined not in ctx for undefined in ["x", "y", "s", "cond", "_"])


@skip_if_pre_3_10
def test_regex_pattern_recursive(check_xonsh_ast):
    src = """

def reverse(x):
    match x:
        case [head, tail] -> `(.)(.*)`:
            return reverse(tail) + head
        case ``:
            return ""

result = [reverse(x) for x in ['part', 'trap', '']]
"""

    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))

    assert ctx["result"] == ["part"[::-1], "trap"[::-1], ""]
    assert all(undefined not in ctx for undefined in ["head", "tail"])


@skip_if_pre_3_10
def test_regex_pattern_nested(check_xonsh_ast):
    src = """

x = "abcd"
match x:
    case @("abcd") as x:
        match x:
            case `abcd` as y:
                match y:
                    case [result, _] -> `(a)(bcd)` if result == 'a':
                        pass

"""

    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))

    assert ctx["result"] == "a"


@skip_if_pre_3_10
def test_regex_pattern_searchfunc(check_xonsh_ast):
    src = """

import xml.etree.ElementTree as ET
import re

html = \"\"\"
<html>
    <head>
        <title>Just some html...</title>
    </head>
    <body>
        <p>Click <a href="http://example.org/">here</a>
        or <a href="https://example.com/">here</a>.</p>
    </body>
</html>
\"\"\"

def find_urls(pattern, subpattern_used):

    def transformer(xml_str):
        root = ET.fromstring(xml_str)

        results = []
        for a in root.iter("a"):
            if (href := a.attrib["href"]) and (m := re.fullmatch(pattern, href)):
                results.append(href)

        if subpattern_used:
            return results
        else:
            if results:
                # return the passed in data so the equality check works
                return xml_str
            else:
                raise ValueError

    return transformer

match html:
    case @find_urls`.*`:
        contains_urls = True

match html:
    case @find_urls`ftp.*`:
        contains_ftp = True
    case _:
        contains_ftp = False

match html:   
    case list(http_urls) -> @find_urls`http:.*`:
        pass

match html:   
    case list(https_urls) -> @find_urls`https:.*`:
        pass
"""

    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))

    assert ctx["contains_urls"]
    assert not ctx["contains_ftp"]
    assert ctx["http_urls"] == ["http://example.org/"]
    assert ctx["https_urls"] == ["https://example.com/"]


@skip_if_pre_3_10
def test_safe_transformer_pattern_nested(check_xonsh_ast):
    src = """

import json

data_str = ' {"pi":"3.141"} '

match data_str:
    case {"pi": pi -> float} -> json.loads:
        pass
    case _:
        raise Exception

match range(10):
    case (total -> sum as sorted_list) -> lambda l : sorted(l, reverse = True) -> list as orig_range if total == 45:
        pass
    case _:
        raise Exception

"""

    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))

    assert ctx["pi"] == 3.141
    assert ctx["total"] == 45
    assert ctx["sorted_list"] == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    assert ctx["orig_range"] == range(10)


@skip_if_pre_3_10
def test_predicate_pattern(check_xonsh_ast):
    src = """

def classify(*l):
    match l:
        case [ (?str.isupper) | (?len) |  (? not (lambda x: x - 42)), *tail]:
            return [True] + classify(*tail)
        case [ head, *tail ]:
            return [False] + classify(*tail)
        case []:
            return []

classification = classify("ABC", [1], [], 42, 41)

def lengthy(l):
    match l:
        case ?len:
            return True
        case ? not len:
            return False
        case _:
            return "tertium non datur does not hold"

lengthiness = [lengthy("lengthy"), lengthy(""), lengthy(0)]

"""

    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))

    assert ctx["classification"] == [True, True, False, True, False]
    assert ctx["lengthiness"] == [True, False, "tertium non datur does not hold"]


@skip_if_pre_3_10
def test_setter_closure_nonlocal_generation(check_xonsh_ast):
    src = """

# nonlocal statement that has nothing to do with match code generation

def independent_of_matching():
    should_stay_nonlocal = 1
    def f():
        nonlocal should_stay_nonlocal

# matching in global namespace
# (i.e. first a nonlocal statement will be generated, which will be converted to a global statement once the context if known)

match None:
    case should_be_global -> str:
        pass

# nonlocal occurrence in non-global namespace that should stay nonlocal
 
class ExpectNonlocal():
    def __init__(self, should_be_generated_as_nonlocal):
        match should_be_generated_as_nonlocal:
            case should_be_generated_as_nonlocal -> str:
                self.should_be_generated_as_nonlocal = should_be_generated_as_nonlocal

assert ExpectNonlocal(None).should_be_generated_as_nonlocal == "None"
"""

    tree = check_xonsh_ast(
        {}, src, run=True, return_obs=True, mode="exec", globals=(ctx := dict())
    )

    generated_source = ast.unparse(tree)

    assert "nonlocal should_stay_nonlocal" in generated_source
    assert "global should_be_global" in generated_source
    assert "nonlocal should_be_generated_as_nonlocal" in generated_source


@skip_if_pre_3_10
def test_exception_during_match(check_xonsh_ast):
    src = """

def raise_(exception):
    raise exception

try:
    match None:
        case @(raise_(ValueError("raise_"))):
            pass
except ValueError as e:
    # exception should be propagated and no other exceptions should occur
    assert str(e) == "raise_"


# this should not produce an exception
match None:
    case ? (lambda: raise_(Exception)):
        pass

# this should produce an exception
match None:
    case ? (lambda: raise_(BaseException)):
        pass

# Errors before the actual sub-pattern match should produce an exception
try:
    match None:
        case ?undefined:
            pass
except NameError as e:
    pass
else:
    assert False, "NameError not thrown"

"""
    check_xonsh_ast({}, src, run=True, mode="exec", globals=(ctx := dict()))
