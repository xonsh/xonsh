# -*- coding: utf-8 -*-
"""date & time related prompt formatter"""
import time
import builtins

import xonsh.tools as xt
import xonsh.platform as xp


def _localtime():
    pf = builtins.__xonsh__.env.get("PROMPT_FIELDS", {})
    tf = pf.get("time_format", "%H:%M:%S")
    return time.strftime(tf, time.localtime())
