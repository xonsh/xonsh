"""date & time related prompt formatter"""

import time

from xonsh.built_ins import XS


def _localtime():
    pf = XS.env.get("PROMPT_FIELDS", {})
    tf = pf.get("time_format", "%H:%M:%S")
    return time.strftime(tf, time.localtime())
