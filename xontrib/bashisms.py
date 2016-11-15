"""Bash-like interface extensions for xonsh."""

@events.on_precommand
def bash_preproc(cmd):
    print("OMG!")
    return cmd.replace('!!', __xonsh_history__.inps[-1].strip())
