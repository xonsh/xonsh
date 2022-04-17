import os.path

from xonsh.aliases import source_alias


def test_source_path(mockopen, mocked_execx_checker, patch_locate_binary, xession):
    patch_locate_binary(xession.commands_cache)

    source_alias(["foo", "bar"])
    path_foo = os.path.join("bin", "foo")
    path_bar = os.path.join("bin", "bar")
    assert mocked_execx_checker[0].endswith(path_foo)
    assert mocked_execx_checker[1].endswith(path_bar)
