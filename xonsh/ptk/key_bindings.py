# -*- coding: utf-8 -*-
"""Key bindings for prompt_toolkit xonsh shell."""
import builtins

from prompt_toolkit.filters import Filter, IsMultiline
from prompt_toolkit.keys import Keys
from xonsh.tools import ON_WINDOWS

env = builtins.__xonsh_env__
indent_ = env.get('INDENT')
DEDENT_TOKENS = frozenset(['raise', 'return', 'pass', 'break', 'continue'])


def carriage_return(b, cli):
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

    at_end_of_line = _is_blank(b.document.current_line_after_cursor)
    current_line_blank = _is_blank(b.document.current_line)

    # indent after a colon
    if (b.document.current_line_before_cursor.strip().endswith(':') and
            at_end_of_line):
        b.newline()
        b.insert_text(indent_, fire_event=False)
    # if current line isn't blank, check dedent tokens
    elif (not current_line_blank and
            b.document.current_line.split(maxsplit=1)[0] in DEDENT_TOKENS and
            b.document.line_count > 1):
        b.newline(copy_margin=True)
        _ = b.delete_before_cursor(count=len(indent_))
    elif (not b.document.on_first_line and
            not current_line_blank):
        b.newline(copy_margin=True)
    elif (b.document.char_before_cursor == '\\' and 
            not (not builtins.__xonsh_env__.get('FORCE_POSIX_PATHS') 
                and ON_WINDOWS)):
        b.newline()
    elif (b.document.find_next_word_beginning() is not None and
            (any(not _is_blank(i)
                 for i
                 in b.document.lines_from_current[1:]))):
        b.newline(copy_margin=True)
    elif not current_line_blank and not can_compile(b.document.text):
        b.newline()
    else:
        b.accept_action.validate_and_handle(cli, b)


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

class BeginningOfLine(Filter):
    """
    Check if cursor is at beginning of a line other than the first line
    in a multiline document
    """
    def __call__(self, cli):
        before_cursor = cli.current_buffer.document.current_line_before_cursor

        return bool(len(before_cursor) == 0
                    and not cli.current_buffer.document.on_first_line)

class EndOfLine(Filter):
    """
    Check if cursor is at the end of a line other than the last line
    in a multiline document
    """
    def __call__(self, cli):
        d = cli.current_buffer.document
        at_end = d.is_cursor_at_the_end_of_line
        last_line = d.is_cursor_at_the_end

        return bool(at_end and not last_line)

def can_compile(src):
    """Returns whether the code can be compiled, i.e. it is valid xonsh."""
    src = src if src.endswith('\n') else src + '\n'
    src = src.lstrip()
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

    @handle(Keys.Tab, filter=TabShouldInsertIndentFilter())
    def _(event):
        """
        If there are only whitespaces before current cursor position insert
        indent instead of autocompleting.
        """
        event.cli.current_buffer.insert_text(env.get('INDENT'))

    @handle(Keys.BackTab)
    def insert_literal_tab(event):
        """ Insert literal tab on Shift+Tab instead of autocompleting """
        event.cli.current_buffer.insert_text(env.get('INDENT'))

    @handle(Keys.ControlJ, filter=IsMultiline())
    def multiline_carriage_return(event):
        """ Wrapper around carriage_return multiline parser """
        b = event.cli.current_buffer
        carriage_return(b, event.cli)

    @handle(Keys.Left, filter=BeginningOfLine())
    def wrap_cursor_back(event):
        """Move cursor to end of previous line unless at beginning of document"""
        b = event.cli.current_buffer
        b.cursor_up(count=1)
        relative_end_index = b.document.get_end_of_line_position()
        b.cursor_right(count=relative_end_index)

    @handle(Keys.Right, filter=EndOfLine())
    def wrap_cursor_forward(event):
        """Move cursor to beginning of next line unless at end of document"""
        b = event.cli.current_buffer
        relative_begin_index = b.document.get_start_of_line_position()
        b.cursor_left(count=abs(relative_begin_index))
        b.cursor_down(count=1)

def _is_blank(l):
    return len(l.strip()) == 0
