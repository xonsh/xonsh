# -*- coding: utf-8 -*-
"""Key bindings for prompt_toolkit xonsh shell."""
import builtins

from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import (
    Condition,
    IsMultiline,
    HasSelection,
    EmacsInsertMode,
    ViInsertMode,
)
from prompt_toolkit.keys import Keys

from xonsh.aliases import xonsh_exit
from xonsh.tools import check_for_partial_string, get_line_continuation
from xonsh.shell import transform_command

env = builtins.__xonsh__.env
DEDENT_TOKENS = frozenset(["raise", "return", "pass", "break", "continue"])


def carriage_return(b, cli, *, autoindent=True):
    """Preliminary parser to determine if 'Enter' key should send command to the
    xonsh parser for execution or should insert a newline for continued input.

    Current 'triggers' for inserting a newline are:
    - Not on first line of buffer and line is non-empty
    - Previous character is a colon (covers if, for, etc...)
    - User is in an open paren-block
    - Line ends with backslash
    - Any text exists below cursor position (relevant when editing previous
    multiline blocks)
    """
    doc = b.document
    at_end_of_line = _is_blank(doc.current_line_after_cursor)
    current_line_blank = _is_blank(doc.current_line)

    indent = env.get("INDENT") if autoindent else ""

    partial_string_info = check_for_partial_string(doc.text)
    in_partial_string = (
        partial_string_info[0] is not None and partial_string_info[1] is None
    )

    # indent after a colon
    if doc.current_line_before_cursor.strip().endswith(":") and at_end_of_line:
        b.newline(copy_margin=autoindent)
        b.insert_text(indent, fire_event=False)
    # if current line isn't blank, check dedent tokens
    elif (
        not current_line_blank
        and doc.current_line.split(maxsplit=1)[0] in DEDENT_TOKENS
        and doc.line_count > 1
    ):
        b.newline(copy_margin=autoindent)
        b.delete_before_cursor(count=len(indent))
    elif not doc.on_first_line and not current_line_blank:
        b.newline(copy_margin=autoindent)
    elif doc.current_line.endswith(get_line_continuation()):
        b.newline(copy_margin=autoindent)
    elif doc.find_next_word_beginning() is not None and (
        any(not _is_blank(i) for i in doc.lines_from_current[1:])
    ):
        b.newline(copy_margin=autoindent)
    elif not current_line_blank and not can_compile(doc.text):
        b.newline(copy_margin=autoindent)
    elif current_line_blank and in_partial_string:
        b.newline(copy_margin=autoindent)
    else:
        b.accept_action.validate_and_handle(cli, b)


def _is_blank(l):
    return len(l.strip()) == 0


def can_compile(src):
    """Returns whether the code can be compiled, i.e. it is valid xonsh."""
    src = src if src.endswith("\n") else src + "\n"
    src = transform_command(src, show_diff=False)
    src = src.lstrip()
    try:
        builtins.__xonsh__.execer.compile(
            src, mode="single", glbs=None, locs=builtins.__xonsh__.ctx
        )
        rtn = True
    except SyntaxError:
        rtn = False
    except Exception:
        rtn = True
    return rtn


@Condition
def tab_insert_indent(cli):
    """Check if <Tab> should insert indent instead of starting autocompletion.
    Checks if there are only whitespaces before the cursor - if so indent
    should be inserted, otherwise autocompletion.

    """
    before_cursor = cli.current_buffer.document.current_line_before_cursor

    return bool(before_cursor.isspace())


@Condition
def beginning_of_line(cli):
    """Check if cursor is at beginning of a line other than the first line in a
    multiline document
    """
    before_cursor = cli.current_buffer.document.current_line_before_cursor

    return bool(
        len(before_cursor) == 0 and not cli.current_buffer.document.on_first_line
    )


@Condition
def end_of_line(cli):
    """Check if cursor is at the end of a line other than the last line in a
    multiline document
    """
    d = cli.current_buffer.document
    at_end = d.is_cursor_at_the_end_of_line
    last_line = d.is_cursor_at_the_end

    return bool(at_end and not last_line)


@Condition
def should_confirm_completion(cli):
    """Check if completion needs confirmation"""
    return (
        builtins.__xonsh__.env.get("COMPLETIONS_CONFIRM")
        and cli.current_buffer.complete_state
    )


# Copied from prompt-toolkit's key_binding/bindings/basic.py
@Condition
def ctrl_d_condition(cli):
    """Ctrl-D binding is only active when the default buffer is selected and
    empty.
    """
    if builtins.__xonsh__.env.get("IGNOREEOF"):
        raise EOFError
    else:
        return cli.current_buffer_name == DEFAULT_BUFFER and not cli.current_buffer.text


@Condition
def autopair_condition(cli):
    """Check if XONSH_AUTOPAIR is set"""
    return builtins.__xonsh__.env.get("XONSH_AUTOPAIR", False)


@Condition
def whitespace_or_bracket_before(cli):
    """Check if there is whitespace or an opening
       bracket to the left of the cursor"""
    d = cli.current_buffer.document
    return bool(
        d.cursor_position == 0
        or d.char_before_cursor.isspace()
        or d.char_before_cursor in "([{"
    )


@Condition
def whitespace_or_bracket_after(cli):
    """Check if there is whitespace or a closing
       bracket to the right of the cursor"""
    d = cli.current_buffer.document
    return bool(
        d.is_cursor_at_the_end_of_line
        or d.current_char.isspace()
        or d.current_char in ")]}"
    )


def load_xonsh_bindings(key_bindings_manager):
    """
    Load custom key bindings.
    """
    handle = key_bindings_manager.registry.add_binding
    has_selection = HasSelection()
    insert_mode = ViInsertMode() | EmacsInsertMode()

    @handle(Keys.Tab, filter=tab_insert_indent)
    def insert_indent(event):
        """
        If there are only whitespaces before current cursor position insert
        indent instead of autocompleting.
        """
        event.cli.current_buffer.insert_text(env.get("INDENT"))

    @handle(Keys.ControlX, Keys.ControlE, filter=~has_selection)
    def open_editor(event):
        """ Open current buffer in editor """
        event.current_buffer.open_in_editor(event.cli)

    @handle(Keys.BackTab, filter=insert_mode)
    def insert_literal_tab(event):
        """ Insert literal tab on Shift+Tab instead of autocompleting """
        b = event.current_buffer
        if b.complete_state:
            b.complete_previous()
        else:
            event.cli.current_buffer.insert_text(env.get("INDENT"))

    @handle("(", filter=autopair_condition & whitespace_or_bracket_after)
    def insert_right_parens(event):
        event.cli.current_buffer.insert_text("(")
        event.cli.current_buffer.insert_text(")", move_cursor=False)

    @handle(")", filter=autopair_condition)
    def overwrite_right_parens(event):
        buffer = event.cli.current_buffer
        if buffer.document.current_char == ")":
            buffer.cursor_position += 1
        else:
            buffer.insert_text(")")

    @handle("[", filter=autopair_condition & whitespace_or_bracket_after)
    def insert_right_bracket(event):
        event.cli.current_buffer.insert_text("[")
        event.cli.current_buffer.insert_text("]", move_cursor=False)

    @handle("]", filter=autopair_condition)
    def overwrite_right_bracket(event):
        buffer = event.cli.current_buffer

        if buffer.document.current_char == "]":
            buffer.cursor_position += 1
        else:
            buffer.insert_text("]")

    @handle("{", filter=autopair_condition & whitespace_or_bracket_after)
    def insert_right_brace(event):
        event.cli.current_buffer.insert_text("{")
        event.cli.current_buffer.insert_text("}", move_cursor=False)

    @handle("}", filter=autopair_condition)
    def overwrite_right_brace(event):
        buffer = event.cli.current_buffer

        if buffer.document.current_char == "}":
            buffer.cursor_position += 1
        else:
            buffer.insert_text("}")

    @handle("'", filter=autopair_condition)
    def insert_right_quote(event):
        buffer = event.cli.current_buffer

        if buffer.document.current_char == "'":
            buffer.cursor_position += 1
        elif whitespace_or_bracket_before(event.cli) and whitespace_or_bracket_after(
            event.cli
        ):
            buffer.insert_text("'")
            buffer.insert_text("'", move_cursor=False)
        else:
            buffer.insert_text("'")

    @handle('"', filter=autopair_condition)
    def insert_right_double_quote(event):
        buffer = event.cli.current_buffer

        if buffer.document.current_char == '"':
            buffer.cursor_position += 1
        elif whitespace_or_bracket_before(event.cli) and whitespace_or_bracket_after(
            event.cli
        ):
            buffer.insert_text('"')
            buffer.insert_text('"', move_cursor=False)
        else:
            buffer.insert_text('"')

    @handle(Keys.Backspace, filter=autopair_condition)
    def delete_brackets_or_quotes(event):
        """Delete empty pair of brackets or quotes"""
        buffer = event.cli.current_buffer
        before = buffer.document.char_before_cursor
        after = buffer.document.current_char

        if any(
            [before == b and after == a for (b, a) in ["()", "[]", "{}", "''", '""']]
        ):
            buffer.delete(1)

        buffer.delete_before_cursor(1)

    @handle(Keys.ControlD, filter=ctrl_d_condition)
    def call_exit_alias(event):
        """Use xonsh exit function"""
        b = event.cli.current_buffer
        b.accept_action.validate_and_handle(event.cli, b)
        xonsh_exit([])

    @handle(Keys.ControlJ, filter=IsMultiline())
    def multiline_carriage_return(event):
        """ Wrapper around carriage_return multiline parser """
        b = event.cli.current_buffer
        carriage_return(b, event.cli)

    @handle(Keys.ControlJ, filter=should_confirm_completion)
    def enter_confirm_completion(event):
        """Ignore <enter> (confirm completion)"""
        event.current_buffer.complete_state = None

    @handle(Keys.Escape, filter=should_confirm_completion)
    def esc_cancel_completion(event):
        """Use <ESC> to cancel completion"""
        event.cli.current_buffer.cancel_completion()

    @handle(Keys.Escape, Keys.ControlJ)
    def execute_block_now(event):
        """Execute a block of text irrespective of cursor position"""
        b = event.cli.current_buffer
        b.accept_action.validate_and_handle(event.cli, b)

    @handle(Keys.Left, filter=beginning_of_line)
    def wrap_cursor_back(event):
        """Move cursor to end of previous line unless at beginning of
        document
        """
        b = event.cli.current_buffer
        b.cursor_up(count=1)
        relative_end_index = b.document.get_end_of_line_position()
        b.cursor_right(count=relative_end_index)

    @handle(Keys.Right, filter=end_of_line)
    def wrap_cursor_forward(event):
        """Move cursor to beginning of next line unless at end of document"""
        b = event.cli.current_buffer
        relative_begin_index = b.document.get_start_of_line_position()
        b.cursor_left(count=abs(relative_begin_index))
        b.cursor_down(count=1)

    @handle(Keys.ControlI, filter=insert_mode)
    def generate_completions(event):
        """
        Tab-completion: where the first tab completes the common suffix and the
        second tab lists all the completions.

        Notes
        -----
        This method was forked from the mainline prompt-toolkit repo.
        Copyright (c) 2014, Jonathan Slenders, All rights reserved.
        """
        b = event.current_buffer

        def second_tab():
            if b.complete_state:
                b.complete_next()
            else:
                event.cli.start_completion(select_first=False)

        # On the second tab-press, or when already navigating through
        # completions.
        if event.is_repeat or b.complete_state:
            second_tab()
        else:
            event.cli.start_completion(insert_common_part=True, select_first=False)
