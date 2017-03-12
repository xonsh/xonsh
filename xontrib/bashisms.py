"""Bash-like interface extensions for xonsh."""
from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import Condition, EmacsInsertMode, ViInsertMode


@events.on_transform_command
def bash_preproc(cmd, **kw):
    if not __xonsh_history__.inps:
        if cmd.strip() == '!!':
            return ''
        return cmd
    return cmd.replace('!!', __xonsh_history__.inps[-1].strip())


@events.on_ptk_create
def custom_keybindings(bindings, **kw):
    handler = bindings.registry.add_binding
    insert_mode = ViInsertMode() | EmacsInsertMode()

    @Condition
    def last_command_exists(cli):
        return len(__xonsh_history__) > 0

    @handler(Keys.Escape, '.', filter=last_command_exists &
             insert_mode)
    def recall_last_arg(event):
        arg = __xonsh_history__[-1].cmd.split()[-1]
        event.current_buffer.insert_text(arg)
