"""Key bindings for prompt_toolkit xonsh shell."""

from prompt_toolkit import search
from prompt_toolkit.application.current import get_app
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import (
    Condition,
    EmacsInsertMode,
    HasSelection,
    IsMultiline,
    IsSearching,
    ViInsertMode,
)
from prompt_toolkit.input import ansi_escape_sequences
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.key_binding.key_bindings import KeyBindings, KeyBindingsBase
from prompt_toolkit.keys import Keys

from xonsh.aliases import xonsh_exit
from xonsh.built_ins import XSH
from xonsh.platform import ON_WINDOWS
from xonsh.shell import transform_command
from xonsh.tools import (
    check_for_partial_string,
    ends_with_colon_token,
    get_line_continuation,
)

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

    env = XSH.env
    indent = env.get("INDENT") if autoindent else ""

    partial_string_info = check_for_partial_string(doc.text)
    in_partial_string = (
        partial_string_info[0] is not None and partial_string_info[1] is None
    )

    # indent after a colon
    if ends_with_colon_token(doc.current_line_before_cursor) and at_end_of_line:
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
        b.validate_and_handle()


def _is_blank(line):
    return len(line.strip()) == 0


def can_compile(src):
    """Returns whether the code can be compiled, i.e. it is valid xonsh."""
    src = src if src.endswith("\n") else src + "\n"
    src = transform_command(src, show_diff=False)
    src = src.lstrip()
    try:
        XSH.execer.compile(src, mode="single", glbs=None, locs=XSH.ctx)
        rtn = True
    except SyntaxError:
        rtn = False
    except Exception:
        rtn = True
    return rtn


@Condition
def tab_insert_indent():
    """Check if <Tab> should insert indent instead of starting autocompletion.
    Checks if there are only whitespaces before the cursor - if so indent
    should be inserted, otherwise autocompletion.

    """
    before_cursor = get_app().current_buffer.document.current_line_before_cursor

    return bool(before_cursor.isspace())


@Condition
def tab_menu_complete():
    """Checks whether completion mode is `menu-complete`"""
    return XSH.env.get("COMPLETION_MODE") == "menu-complete"


@Condition
def beginning_of_line():
    """Check if cursor is at beginning of a line other than the first line in a
    multiline document
    """
    app = get_app()
    before_cursor = app.current_buffer.document.current_line_before_cursor

    return bool(
        len(before_cursor) == 0 and not app.current_buffer.document.on_first_line
    )


@Condition
def end_of_line():
    """Check if cursor is at the end of a line other than the last line in a
    multiline document
    """
    d = get_app().current_buffer.document
    at_end = d.is_cursor_at_the_end_of_line
    last_line = d.is_cursor_at_the_end

    return bool(at_end and not last_line)


@Condition
def should_confirm_completion():
    """Check if completion needs confirmation"""
    return (
        XSH.env.get("COMPLETIONS_CONFIRM") and get_app().current_buffer.complete_state
    )


# Copied from prompt-toolkit's key_binding/bindings/basic.py
@Condition
def ctrl_d_condition():
    """Ctrl-D binding is only active when the default buffer is selected and
    empty.
    """
    if XSH.env.get("IGNOREEOF"):
        return False
    else:
        app = get_app()
        buffer_name = app.current_buffer.name

        return buffer_name == DEFAULT_BUFFER and not app.current_buffer.text


@Condition
def autopair_condition():
    """Check if XONSH_AUTOPAIR is set"""
    return XSH.env.get("XONSH_AUTOPAIR", False)


@Condition
def whitespace_or_bracket_before():
    """Check if there is whitespace or an opening
    bracket to the left of the cursor"""
    d = get_app().current_buffer.document
    return bool(
        d.cursor_position == 0
        or d.char_before_cursor.isspace()
        or d.char_before_cursor in "([{"
    )


@Condition
def whitespace_or_bracket_after():
    """Check if there is whitespace or a closing
    bracket to the right of the cursor"""
    d = get_app().current_buffer.document
    return bool(
        d.is_cursor_at_the_end_of_line
        or d.current_char.isspace()
        or d.current_char in ")]}"
    )


def wrap_selection(buffer, left, right=None):
    selection_state = buffer.selection_state

    for start, end in buffer.document.selection_ranges():
        buffer.transform_region(start, end, lambda s: f"{left}{s}{right}")

    # keep the selection of the inner expression
    # e.g. `echo |Hello World|` -> `echo "|Hello World|"`
    buffer.cursor_position += 1
    selection_state.original_cursor_position += 1
    buffer.selection_state = selection_state


def load_xonsh_bindings(ptk_bindings: KeyBindingsBase) -> KeyBindingsBase:
    """
    Load custom key bindings.

    Parameters
    ----------
    ptk_bindings :
        The default prompt toolkit bindings. We need these to add aliases to them.
    """
    key_bindings = KeyBindings()
    handle = key_bindings.add
    has_selection = HasSelection()
    insert_mode = ViInsertMode() | EmacsInsertMode()

    if XSH.env["XONSH_CTRL_BKSP_DELETION"]:
        # Not all terminal emulators emit the same keys for backspace, therefore
        # ptk always maps backspace ("\x7f") to ^H ("\x08"), and all the backspace bindings are registered for ^H.
        # This means we can't re-map backspace and instead we register a new "real-ctrl-bksp" key.
        # See https://github.com/xonsh/xonsh/issues/4407

        if ON_WINDOWS:
            # On windows BKSP is "\x08" and CTRL-BKSP is "\x7f"
            REAL_CTRL_BKSP = "\x7f"

            # PTK uses a second mapping
            from prompt_toolkit.input import win32 as ptk_win32

            ptk_win32.ConsoleInputReader.mappings[b"\x7f"] = REAL_CTRL_BKSP  # type: ignore
        else:
            REAL_CTRL_BKSP = "\x08"

        # Prompt-toolkit allows using single-character keys that aren't in the `Keys` enum.
        ansi_escape_sequences.ANSI_SEQUENCES[REAL_CTRL_BKSP] = REAL_CTRL_BKSP  # type: ignore
        ansi_escape_sequences.REVERSE_ANSI_SEQUENCES[REAL_CTRL_BKSP] = REAL_CTRL_BKSP  # type: ignore

        @handle(REAL_CTRL_BKSP, filter=insert_mode)
        def delete_word(event):
            """Delete a single word (like ALT-backspace)"""
            get_by_name("backward-kill-word").call(event)

    @handle(Keys.Tab, filter=tab_insert_indent)
    def insert_indent(event):
        """
        If there are only whitespaces before current cursor position insert
        indent instead of autocompleting.
        """
        env = XSH.env
        event.cli.current_buffer.insert_text(env.get("INDENT"))

    @handle(Keys.Tab, filter=~tab_insert_indent & tab_menu_complete)
    def menu_complete_select(event):
        """Start completion in menu-complete mode, or tab to next completion"""
        b = event.current_buffer
        if b.complete_state:
            b.complete_next()
        else:
            b.start_completion(select_first=True)

    @handle(Keys.ControlX, Keys.ControlE, filter=~has_selection)
    def open_editor(event):
        """Open current buffer in editor"""
        event.current_buffer.open_in_editor(event.cli)

    @handle(Keys.BackTab, filter=insert_mode)
    def insert_literal_tab(event):
        """Insert literal tab on Shift+Tab instead of autocompleting"""
        b = event.current_buffer
        if b.complete_state:
            b.complete_previous()
        else:
            env = XSH.env
            event.cli.current_buffer.insert_text(env.get("INDENT"))

    def generate_parens_handlers(left, right):
        @handle(left, filter=autopair_condition)
        def insert_left_paren(event):
            buffer = event.cli.current_buffer

            if has_selection():
                wrap_selection(buffer, left, right)
            elif whitespace_or_bracket_after():
                buffer.insert_text(left)
                buffer.insert_text(right, move_cursor=False)
            else:
                buffer.insert_text(left)

        @handle(right, filter=autopair_condition)
        def overwrite_right_paren(event):
            buffer = event.cli.current_buffer

            if buffer.document.current_char == right:
                buffer.cursor_position += 1
            else:
                buffer.insert_text(right)

    generate_parens_handlers("(", ")")
    generate_parens_handlers("[", "]")
    generate_parens_handlers("{", "}")

    def generate_quote_handler(quote):
        @handle(quote, filter=autopair_condition)
        def insert_quote(event):
            buffer = event.cli.current_buffer

            if has_selection():
                wrap_selection(buffer, quote, quote)
            elif buffer.document.current_char == quote:
                buffer.cursor_position += 1
            elif whitespace_or_bracket_before() and whitespace_or_bracket_after():
                buffer.insert_text(quote)
                buffer.insert_text(quote, move_cursor=False)
            else:
                buffer.insert_text(quote)

    generate_quote_handler("'")
    generate_quote_handler('"')

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
        b.validate_and_handle()
        xonsh_exit([])

    @handle(Keys.ControlJ, filter=IsMultiline() & insert_mode)
    @handle(Keys.ControlM, filter=IsMultiline() & insert_mode)
    def multiline_carriage_return(event):
        """Wrapper around carriage_return multiline parser"""
        b = event.cli.current_buffer
        carriage_return(b, event.cli)

    @handle(Keys.ControlJ, filter=should_confirm_completion)
    @handle(Keys.ControlM, filter=should_confirm_completion)
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
        b.validate_and_handle()

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

    @handle(Keys.ControlM, filter=IsSearching())
    @handle(Keys.ControlJ, filter=IsSearching())
    def accept_search(event):
        search.accept_search()

    @handle(Keys.ControlZ)
    def skip_control_z(event):
        """Prevents the writing of ^Z to the prompt, if Ctrl+Z was pressed
        during the previous command.
        """
        pass

    @handle(Keys.ControlX, Keys.ControlX, filter=has_selection)
    def _cut(event):
        """Cut selected text."""
        data = event.current_buffer.cut_selection()
        event.app.clipboard.set_data(data)

    @handle(Keys.ControlX, Keys.ControlC, filter=has_selection)
    def _copy(event):
        """Copy selected text."""
        data = event.current_buffer.copy_selection()
        event.app.clipboard.set_data(data)

    @handle(Keys.ControlV, filter=insert_mode | has_selection)
    def _yank(event):
        """Paste selected text."""
        buff = event.current_buffer
        if buff.selection_state:
            buff.cut_selection()
        get_by_name("yank").call(event)

    def create_alias(new_keys, original_keys):
        bindings = ptk_bindings.get_bindings_for_keys(tuple(original_keys))
        for original_binding in bindings:
            handle(*new_keys, filter=original_binding.filter)(original_binding.handler)

    # Complete a single auto-suggestion word
    create_alias([Keys.ControlRight], ["escape", "f"])

    # since macOS uses Control as reserved, then we use the alt/option key instead
    # which is mapped as the "escape" key
    create_alias(["escape", "right"], ["escape", "f"])

    return key_bindings
