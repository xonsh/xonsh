# -*- coding: utf-8 -*-
"""Prompt formatter for current jobs"""

import xonsh.jobs as xj


def _current_job():
    j = xj.get_next_task()
    if j is not None:
        if not j["bg"]:
            cmd = j["cmds"][-1]
            s = cmd[0]
            if s == "sudo" and len(cmd) > 1:
                s = cmd[1]
            return s
