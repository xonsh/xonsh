# -*- coding: utf-8 -*-
"""Key bindings for prompt_toolkit xonsh shell."""
import builtins

from prompt_toolkit.filters import Filter, IsMultiline
from prompt_toolkit.keys import Keys


class TabShouldInsertIndentFilter(Filter):
    """
    Filter that is intended to check if <Tab> should insert indent instead of
    starting autocompletion.
    It basically just checks if there are only whitespaces before the cursor -
    if so indent should be inserted, otherwise autocompletion.
    """
    def __call__(self, cli):
        before_cursor = cli.current_buffer.document.current_line_before_cursor

        return bool(before_cursor.isspace())


def can_compile(src):
    """Returns whether the code can be compiled, i.e. it is valid xonsh."""
    if not src.endswith('\n') and not src.endswith('\''):
        src = src + '\n'
    try:
        builtins.__xonsh_execer__.compile(src, mode='single', glbs=None,
                                          locs=builtins.__xonsh_ctx__)
        rtn = True
    except SyntaxError:
        rtn = False
    return rtn


def load_xonsh_bindings(key_bindings_manager):
    """
    Load custom key bindings.
    """
    handle = key_bindings_manager.registry.add_binding
    env = builtins.__xonsh_env__
    indent_ = env.get('INDENT')

    DEDENT_TOKENS = frozenset(['raise', 'return', 'pass', 'break', 'continue'])

    @handle(Keys.Tab, filter=TabShouldInsertIndentFilter())
    def _(event):
        """
        If there are only whitespaces before current cursor position insert
        indent instead of autocompleting.
        """
        event.cli.current_buffer.insert_text(env.get('INDENT'))

    @handle(Keys.BackTab)
    def insert_literal_tab(event):
        """
        Insert literal tab on Shift+Tab instead of autocompleting
        """
        event.cli.current_buffer.insert_text(env.get('INDENT'))

    @handle(Keys.ControlJ, filter=IsMultiline())
    def multiline_carriage_return(event):
        """
        Preliminary parser to determine if 'Enter' key should send command to
        the xonsh parser for execution or should insert a newline for continued
        input.

        Current 'triggers' for inserting a newline are:
        - Not on first line of buffer and line is non-empty
        - Previous character is a colon (covers if, for, etc...)
        - User is in an open paren-block
        - Line ends with backslash
        - Any text exists below cursor position (relevant when editing previous
        multiline blocks)
        """

        b = event.cli.current_buffer

        # indent after a colon
        if b.document.char_before_cursor == ':':
            b.newline()
            b.insert_text(indent_, fire_event=False)
        # if current line isn't blank, check dedent tokens
        elif (not (len(b.document.current_line) == 0 or
                   b.document.current_line.isspace()) and
              b.document.current_line.split(maxsplit=1)[0] in DEDENT_TOKENS):
            b.newline(copy_margin=True)
            _ = b.delete_before_cursor(count=len(indent_))
        elif (not b.document.on_first_line and
              not (len(b.document.current_line) == 0 or
                   b.document.current_line.isspace())):
            b.newline(copy_margin=True)
        elif b.document.char_before_cursor == '\\':
            b.newline()
        elif not can_compile(b.document.text):
            b.newline()
        else:
            b.accept_action.validate_and_handle(event.cli, b)
