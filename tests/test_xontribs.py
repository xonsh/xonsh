"""xontrib tests, such as they are"""
from xonsh.xontribs import xontrib_metadata

def test_load_xontrib_metadata():
    # Simply tests that the xontribs JSON files isn't malformed.
    xontrib_metadata()