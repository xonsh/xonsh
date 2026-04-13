"""Prompt formatter for jobs fields e.g. current_job."""

import contextlib
import threading

from xonsh.prompt.base import PromptField


class CurrentJobField(PromptField):
    """Prompt field for the currently running foreground job.

    Uses thread-local storage so that background threads running
    subprocesses don't leak their command names into the prompt.
    See xonsh/xonsh#3175.
    """

    _tlocal = threading.local()

    def update(self, ctx):
        cmds = getattr(self._tlocal, "current_cmds", None)
        if cmds is not None:
            cmd = cmds[-1]
            s = cmd[0]
            if s == "sudo" and len(cmd) > 1:
                s = cmd[1]
            self.value = s
        else:
            self.value = None

    @contextlib.contextmanager
    def update_current_cmds(self, cmds):
        """Context manager that updates the information used to update the job name"""
        old_cmds = getattr(self._tlocal, "current_cmds", None)
        try:
            self._tlocal.current_cmds = cmds
            yield
        finally:
            self._tlocal.current_cmds = old_cmds
