"""Tests xonsh contexts."""

from textwrap import dedent

from xonsh.contexts import Block, Functor

#
# helpers
#

X1_WITH = "x = 1\nwith! Block() as b:\n"
SIMPLE_WITH = "with! Block() as b:\n"
FUNC_WITH = (
    "x = 1\n"
    "def func():\n"
    "    y = 1\n"
    "    with! Block() as b:\n"
    "{body}"
    "    y += 1\n"
    "    return b\n"
    "x += 1\n"
    "rtn = func()\n"
    "x += 1\n"
)

FUNC_OBSG = {"x": 3}
FUNC_OBSL = {"y": 1}


def norm_body(body):
    if not isinstance(body, str):
        body = "\n".join(body)
    body = dedent(body)
    body = body.splitlines()
    return body


def block_checks_glb(name, glbs, body, obs=None):
    block = glbs[name]
    obs = obs or {}
    for k, v in obs.items():
        assert v == glbs[k]
    body = norm_body(body)
    assert body == block.lines
    assert glbs is block.glbs
    assert block.locs is None


def block_checks_func(name, glbs, body, obsg=None, obsl=None):
    block = glbs[name]
    obsg = obsg or {}
    for k, v in obsg.items():
        assert v == glbs[k]
    body = norm_body(body)
    assert body == block.lines
    assert glbs is block.glbs
    # local context tests
    locs = block.locs
    assert locs is not None
    obsl = obsl or {}
    for k, v in obsl.items():
        assert v == locs[k]


#
# Block tests
#


def test_block_noexec(xonsh_execer_exec):
    s = "x = 1\nwith! Block():\n    x += 42\n"
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    assert 1 == glbs["x"]


def test_block_oneline(xonsh_execer_exec):
    body = "    x += 42\n"
    s = X1_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_manylines(xonsh_execer_exec):
    body = "    ![echo wow mom]\n# bad place for a comment\n    x += 42"
    s = X1_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_leading_comment(xonsh_execer_exec):
    # leading comments show up in block lines
    body = "    # I am a leading comment\n    x += 42\n"
    s = X1_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_trailing_comment(xonsh_execer_exec):
    # trailing comments show up in block lines
    body = "    x += 42\n    # I am a trailing comment\n"
    s = X1_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_no_trailing_content(xonsh_execer_exec):
    # content after the with! block must not be captured
    body = "    x += 42\n"
    after = "# comment after\n\nif True:\n    pass\n"
    s = X1_WITH + body + "\n" + after
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_leading_comments_and_trailing_code(xonsh_execer_exec):
    """Reproducer from bug report: leading comments must be captured,
    trailing comments and code after the block must not."""
    s = dedent("""\
        x = 1
        with! Block() as b:
            # first
            # first
            x += 42

        # comment 1
        # comment 2

        if True:
            pass
    """)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    expected = "# first\n# first\nx += 42\n"
    assert "\n".join(glbs["b"].lines) + "\n" == expected
    assert glbs["x"] == 1  # block body was not executed


def test_block_comments_surround_code(xonsh_execer_exec):
    """Leading and trailing indented comments are all part of the block."""
    body = "    # comment 1\n    # comment 2\n    x += 42\n    # comment 3\n    # comment 4\n"
    s = X1_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_multiple_leading_and_trailing_comments(xonsh_execer_exec):
    """Leading comments included, trailing indented comments included,
    trailing unindented comments excluded."""
    body = "    # leading\n    x += 42\n    # trailing inside\n"
    after = "\n# outside comment\n"
    s = X1_WITH + body + after
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_trailing_line_continuation(xonsh_execer_exec):
    body = "    x += \\\n         42\n"
    s = X1_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_trailing_close_paren(xonsh_execer_exec):
    body = '    x += int("42"\n             )\n'
    s = X1_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body, {"x": 1})


def test_block_trailing_close_many(xonsh_execer_exec):
    body = (
        '    x = {None: [int("42"\n'
        "                    )\n"
        "                ]\n"
        "         }\n"
    )
    s = SIMPLE_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body)


def test_block_trailing_triple_string(xonsh_execer_exec):
    body = '    x = """This\nis\n"probably"\n\'not\' what I meant.\n"""\n'
    s = SIMPLE_WITH + body
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("b", glbs, body)


def test_block_func_oneline(xonsh_execer_exec):
    body = "        x += 42\n"
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_manylines(xonsh_execer_exec):
    body = "        ![echo wow mom]\n# bad place for a comment\n        x += 42\n"
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_leading_comment(xonsh_execer_exec):
    # leading comments show up in block lines
    body = "        # I am a leading comment\n        x += 42\n"
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_comment(xonsh_execer_exec):
    # trailing comments show up in block lines
    body = "        x += 42\n        # I am a trailing comment\n"
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_blockfunc__trailing_line_continuation(xonsh_execer_exec):
    body = "        x += \\\n             42\n"
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_close_paren(xonsh_execer_exec):
    body = '        x += int("42"\n                 )\n'
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_close_many(xonsh_execer_exec):
    body = (
        '        x = {None: [int("42"\n'
        "                        )\n"
        "                    ]\n"
        "             }\n"
    )
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_triple_string(xonsh_execer_exec):
    body = '        x = """This\nis\n"probably"\n\'not\' what I meant.\n"""\n'
    s = FUNC_WITH.format(body=body)
    glbs = {"Block": Block}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_func("rtn", glbs, body, FUNC_OBSG, FUNC_OBSL)


#
# Functor tests
#

X2_WITH = "{var} = 1\nwith! Functor() as f:\n{body}{var} += 1\n{calls}\n"


def test_functor_oneline_onecall_class(xonsh_execer_exec):
    body = "    global y\n    y += 42\n"
    calls = "f()"
    s = X2_WITH.format(body=body, calls=calls, var="y")
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"y": 44})


def test_functor_oneline_onecall_func(xonsh_execer_exec):
    body = "    global z\n    z += 42\n"
    calls = "f.func()"
    s = X2_WITH.format(body=body, calls=calls, var="z")
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"z": 44})


def test_functor_oneline_onecall_both(xonsh_execer_exec):
    body = "    global x\n    x += 42\n"
    calls = "f()\nf.func()"
    s = X2_WITH.format(body=body, calls=calls, var="x")
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"x": 86})


XA_WITH = "x = [1]\nwith! Functor() as f:\n{body}x.append(2)\n{calls}\n"


def test_functor_oneline_append(xonsh_execer_exec):
    body = "    x.append(3)\n"
    calls = "f()\n"
    s = XA_WITH.format(body=body, calls=calls)
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"x": [1, 2, 3]})


def test_functor_return(xonsh_execer_exec):
    body = "    x = 42"
    t = 'res = 0\nwith! Functor(rtn="x") as f:\n{body}\nres = f()\n'
    s = t.format(body=body)
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"res": 42})


def test_functor_args(xonsh_execer_exec):
    body = "    x = 42 + a"
    t = 'res = 0\nwith! Functor(args=("a",), rtn="x") as f:\n{body}\nres = f(2)\n'
    s = t.format(body=body)
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"res": 44})


def test_functor_kwargs(xonsh_execer_exec):
    body = "    x = 42 + a + b"
    t = (
        "res = 0\n"
        'with! Functor(kwargs={{"a": 1, "b": 12}}, rtn="x") as f:\n'
        "{body}\n"
        "res = f(b=6)\n"
    )
    s = t.format(body=body)
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"res": 49})


def test_functor_fullsig(xonsh_execer_exec):
    body = "    x = 42 + a + b + c"
    t = (
        "res = 0\n"
        'with! Functor(args=("c",), kwargs={{"a": 1, "b": 12}}, rtn="x") as f:\n'
        "{body}\n"
        "res = f(55)\n"
    )
    s = t.format(body=body)
    glbs = {"Functor": Functor}
    xonsh_execer_exec(s, glbs=glbs, locs=None)
    block_checks_glb("f", glbs, body, {"res": 110})
