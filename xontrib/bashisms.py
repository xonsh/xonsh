"""Bash-like interface extensions for xonsh."""


@events.on_precommand
def bash_preproc(cmd):
    if len(__xonsh_history__) == 0:
        return cmd
    return cmd.replace('!!', __xonsh_history__.inps[-1].strip())
