"""date & time related prompt formatter"""

import time

from xonsh.built_ins import XSH


def _localtime():
    pf = XSH.env.get("PROMPT_FIELDS", {})
    tf = pf.get("time_format", "%H:%M:%S")
    return time.strftime(tf, time.localtime())
