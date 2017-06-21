"""Jumping across whole words (non-whitespace) with Ctrl+Left/Right.

Alt+Left/Right remains unmodified to jump over smaller word segments.
"""
from prompt_toolkit.keys import Keys

__all__ = ()


@events.on_ptk_create
def custom_keybindings(bindings, **kw):

    # Key bindings for jumping over whole words (everything that's not
    # white space) using Ctrl+Left and Ctrl+Right;
    # Alt+Left and Alt+Right still jump over smaller word segments.
    # See https://github.com/xonsh/xonsh/issues/2403

    handler = bindings.registry.add_binding

    @handler(Keys.ControlLeft)
    def ctrl_left(event):
        buff = event.current_buffer
        pos = buff.document.find_previous_word_beginning(count=event.arg, WORD=True)
        if pos:
            buff.cursor_position += pos

    @handler(Keys.ControlRight)
    def ctrl_right(event):
        buff = event.current_buffer
        pos = buff.document.find_next_word_ending(count=event.arg, WORD=True)
        if pos:
            buff.cursor_position += pos
