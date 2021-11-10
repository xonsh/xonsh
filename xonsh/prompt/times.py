# -*- coding: utf-8 -*-
"""date & time related prompt formatter"""
import time

import xonsh.session as xsh


def _localtime():
    pf = xsh.XSH.env.get("PROMPT_FIELDS", {})
    tf = pf.get("time_format", "%H:%M:%S")
    return time.strftime(tf, time.localtime())
