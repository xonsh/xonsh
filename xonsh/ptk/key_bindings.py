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


def load_xonsh_bindings(key_bindings_manager):
    """
    Load custom key bindings.
    """
    handle = key_bindings_manager.registry.add_binding
    env = builtins.__xonsh_env__

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

    @handle(Keys.F10, filter=IsMultiline())
    def multiline_carriage_return(event):
        b = event.cli.current_buffer
        indent_length = len(env.get('INDENT'))
        #check if last character is a colon
        if b.document.char_before_cursor == ':':
            b.newline()
            b.insert_text(env.get('INDENT'), fire_event=False)
        #then check if there's an open paren block
        elif b.document.text.count('(') > b.document.text.count(')'):
            b.newline()
        #then check if the line ends in a backslash
        elif b.document.char_before_cursor == '\\':
            b.newline()

        #if previous line is empty, and we're on the last line of the buffer
        #then execute on second carriage return (otherwise you can't hit
        #enter when editing in the middle of an old block)
        elif (b.document.empty_line_count_at_the_end() > 0
              and b.document.on_last_line):
            b.accept_action.validate_and_handle(event.cli, b)

        #if not first line 
            #and nonblank char before cursor then newline at same indent
        elif (not b.document.on_first_line and
            not b.document.current_line_before_cursor.isspace()):
            b.newline(copy_margin=True)
            b.cursor_down()
        #and only empty space before cursor, then unindent
        elif not b.document.on_first_line:
            b.newline(copy_margin=False)
            b.cursor_down()

        else:
            b.accept_action.validate_and_handle(event.cli, b)
