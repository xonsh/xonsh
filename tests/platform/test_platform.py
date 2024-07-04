from pytest_mock import MockerFixture

import xonsh.platform as xp


def test_githash_value_error(mocker: MockerFixture):
    mocker.patch.object(xp, "open", mocker.mock_open(read_data="abc123"))
    sha, date_ = xp.githash()
    assert date_ is None
    assert sha is None


def test_pathsplit_empty_path():
    assert xp.pathsplit("") == ("", "")
