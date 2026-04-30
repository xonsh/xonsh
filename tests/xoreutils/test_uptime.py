import datetime

import pytest


@pytest.fixture
def uptime(xession, load_xontrib):
    load_xontrib("coreutils")
    return xession.aliases["uptime"]


def test_uptime(uptime):
    out = uptime([])
    delta = datetime.timedelta(seconds=float(out))
    # make sure that it returns a positive time lapse
    assert delta > datetime.timedelta(microseconds=1)
