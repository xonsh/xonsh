"""Bash-like interface extensions for xonsh."""


@events.on_transform_command
def bash_preproc(cmd, **kw):
    if not __xonsh_history__.inps:
        if cmd.strip() == '!!':
            return ''
        return cmd
    return cmd.replace('!!', __xonsh_history__.inps[-1].strip())
