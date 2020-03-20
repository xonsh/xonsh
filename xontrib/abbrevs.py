"""Command abbreviations."""

import builtins
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
        handler = bindings.add
    else:
        handler = bindings.registry.add_binding

    @handler(" ")
    def space(event):
        buffer = event.app.current_buffer
        expand_abbrev(buffer)
        buffer.insert_text(" ")
