import xonsh.completers.path as xcp

def test_pattern_need_quotes():
    # just make sure the regex compiles
    xcp.PATTERN_NEED_QUOTES.match('')
