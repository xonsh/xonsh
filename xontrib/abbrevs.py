"""Command abbreviations."""

import builtins
from prompt_toolkit.filters import IsMultiline
from prompt_toolkit.keys import Keys
from xonsh.platform import ptk_shell_type

__all__ = ()

builtins.__xonsh__.ctx["abbrevs"] = dict()


def expand_abbrev(buffer):
    word = buffer.document.get_word_before_cursor()
    if "abbrevs" not in builtins.__xonsh__.ctx.keys():
        return
    abbrevs = builtins.__xonsh__.ctx["abbrevs"]
    if word in abbrevs.keys():
        buffer.delete_before_cursor(count=len(word))
        buffer.insert_text(abbrevs[word])


@events.on_ptk_create
def custom_keybindings(bindings, **kw):

    if ptk_shell_type() == "prompt_toolkit2":
        from xonsh.ptk2.key_bindings import carriage_return
        from prompt_toolkit.filters import EmacsInsertMode, ViInsertMode

        handler = bindings.add
        insert_mode = ViInsertMode() | EmacsInsertMode()
    else:
        from xonsh.ptk.key_bindings import carriage_return

        handler = bindings.registry.add_binding
        insert_mode = True

    @handler(" ", filter=IsMultiline() & insert_mode)
    def handle_space(event):
        buffer = event.app.current_buffer
        expand_abbrev(buffer)
        buffer.insert_text(" ")

    @handler(Keys.ControlJ, filter=IsMultiline() & insert_mode)
    @handler(Keys.ControlM, filter=IsMultiline() & insert_mode)
    def multiline_carriage_return(event):
        buffer = event.app.current_buffer
        current_char = buffer.document.current_char
        if not current_char or current_char.isspace():
            expand_abbrev(buffer)
        carriage_return(buffer, event.cli)
