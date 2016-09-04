# -*- coding: utf-8 -*-

import os
import socket

import xonsh.lazyasd as xl
import xonsh.tools as xt
import xonsh.platform as xp


from xonsh.prompt.cwd import (
    _collapsed_pwd, _replace_home_cwd, _dynamically_collapsed_pwd
)
from xonsh.prompt.job import _current_job
from xonsh.prompt.env import (env_name, vte_new_tab_cwd)
from xonsh.prompt.vc_branch import (
    current_branch, branch_color, branch_bg_color
)
from xonsh.prompt.gitstatus import _gitstatus_prompt


FORMATTER_DICT = xl.LazyObject(lambda: dict(
    user=os.environ.get('USERNAME' if xp.ON_WINDOWS else 'USER', '<user>'),
    prompt_end='#' if xt.is_superuser() else '$',
    hostname=socket.gethostname().split('.', 1)[0],
    cwd=_dynamically_collapsed_pwd,
    cwd_dir=lambda: os.path.dirname(_replace_home_cwd()),
    cwd_base=lambda: os.path.basename(_replace_home_cwd()),
    short_cwd=_collapsed_pwd,
    curr_branch=current_branch,
    branch_color=branch_color,
    branch_bg_color=branch_bg_color,
    current_job=_current_job,
    env_name=env_name,
    vte_new_tab_cwd=vte_new_tab_cwd,
    gitstatus=_gitstatus_prompt,
), globals(), 'FORMATTER_DICT')
