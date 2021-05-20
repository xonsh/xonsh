"""
Command abbreviations.

This expands input words from `abbrevs` disctionary as you type.
Adds ``abbrevs`` dictionary to hold user-defined "command abbreviations.
The dictionary is searched as you type the matching words are replaced
at the command line by the corresponding dictionary contents once you hit
'Space' or 'Return' key.

For instance a frequently used command such as ``git status`` can be abbreviated to ``gst`` as follows::

    $ xontrib load abbrevs
    $ abbrevs['gst'] = 'git status'
    $ gst # Once you hit <space> or <return> 'gst' gets expanded to 'git status'.

one can set a callback function that receives current buffer and word to customize the expanded word based on context

.. code-block:: python

    $ abbrevs['ps'] = lambda buffer, word: "procs" if buffer.text.startswith(word) else word


It is also possible to set the cursor position after expansion with,

    $ abbrevs['gp'] = "git push <edit> --force"
"""

import builtins
import typing as tp

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import completion_is_selected, IsMultiline
from prompt_toolkit.keys import Keys
from xonsh.built_ins import DynamicAccessProxy, XSH
from xonsh.events import events
from xonsh.tools import check_for_partial_string

__all__ = ()

# todo: do not assign .abbrevs and directly use abbrevs as mutable const.
XSH.abbrevs = abbrevs = dict()
proxy = DynamicAccessProxy("abbrevs", "__xonsh__.abbrevs")
builtins.abbrevs = proxy


class _LastExpanded(tp.NamedTuple):
    word: str
    expanded: str


class Abbreviation:
    """A container class to handle state related to abbreviating keywords"""

    last_expanded: tp.Optional[_LastExpanded] = None

    def expand(self, buffer: Buffer) -> bool:
        """expand the given abbr text. Return true if cursor position changed."""
        if not abbrevs:
            return False
        document = buffer.document
        word = document.get_word_before_cursor(WORD=True)
        if word in abbrevs.keys():
            partial = document.text[: document.cursor_position]
            startix, endix, quote = check_for_partial_string(partial)
            if startix is not None and endix is None:
                return False
            text = get_abbreviated(word, buffer)

            buffer.delete_before_cursor(count=len(word))
            buffer.insert_text(text)

            self.last_expanded = _LastExpanded(word, text)
            if EDIT_SYMBOL in text:
                set_cursor_position(buffer, text)
                return True
        return False

    def revert(self, buffer) -> bool:
        if self.last_expanded is None:
            return False
        document = buffer.document
        expansion = self.last_expanded.expanded + " "
        if not document.text_before_cursor.endswith(expansion):
            return False
        buffer.delete_before_cursor(count=len(expansion))
        buffer.insert_text(self.last_expanded.word)
        self.last_expanded = None
        return True


EDIT_SYMBOL = "<edit>"


def get_abbreviated(key: str, buffer) -> str:
    abbr = abbrevs[key]
    if callable(abbr):
        text = abbr(buffer=buffer, word=key)
    else:
        text = abbr
    return text


def set_cursor_position(buffer, expanded: str) -> None:
    pos = expanded.rfind(EDIT_SYMBOL)
    if pos == -1:
        return
    buffer.cursor_position = buffer.cursor_position - (len(expanded) - pos)
    buffer.delete(len(EDIT_SYMBOL))


@events.on_ptk_create
def custom_keybindings(bindings, **kw):

    from xonsh.ptk_shell.key_bindings import carriage_return
    from prompt_toolkit.filters import EmacsInsertMode, ViInsertMode

    handler = bindings.add
    insert_mode = ViInsertMode() | EmacsInsertMode()
    abbrev = Abbreviation()

    @handler(" ", filter=IsMultiline() & insert_mode)
    def handle_space(event):
        buffer = event.app.current_buffer

        add_space = True
        if not abbrev.revert(buffer):
            position_changed = abbrev.expand(buffer)
            if position_changed:
                add_space = False
        if add_space:
            buffer.insert_text(" ")

    @handler(
        Keys.ControlJ, filter=IsMultiline() & insert_mode & ~completion_is_selected
    )
    @handler(
        Keys.ControlM, filter=IsMultiline() & insert_mode & ~completion_is_selected
    )
    def multiline_carriage_return(event):
        buffer = event.app.current_buffer
        current_char = buffer.document.current_char
        if not current_char or current_char.isspace():
            abbrev.expand(buffer)
        carriage_return(buffer, event.cli)
