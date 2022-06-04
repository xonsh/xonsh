"""Jump/delete across whole (non-whitespace) words with Ctrl+Left/Right/Delete/Backspace.

Control+left/right: Jump to previous/next whole word
Control+backspace: Delete to beginning of whole word
Control+delete: Delete to end of whole word
Shift+delete: Delete whole word

Alt+Left/Right/Delete/Backspace remain unmodified:

Alt+left/right: Jump to previous/next token
Alt+backspace: Delete to beginning of token
Alt+delete: Delete to end of token

Some terminals cannot differentiate between Backspace and Control+Backspace.
In this case, users can set `$XONSH_WHOLE_WORD_CTRL_BKSP = False` to skip
configuration of the Control+Backspace key binding.
"""

import prompt_toolkit.input.ansi_escape_sequences as ansiseq
import prompt_toolkit.input.win32 as ptk_win32
from prompt_toolkit.filters import EmacsInsertMode, ViInsertMode
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.keys import Keys

from xonsh.built_ins import XSH, XonshSession
from xonsh.platform import ON_WINDOWS


def custom_keybindings(bindings, **kw):
    insert_mode = ViInsertMode() | EmacsInsertMode()

    # Key bindings for jumping over whole words (everything that's not
    # white space) using Ctrl+Left and Ctrl+Right;
    # Alt+Left and Alt+Right still jump over smaller word segments.
    # See https://github.com/xonsh/xonsh/issues/2403

    @bindings.add(Keys.ControlLeft)
    def ctrl_left(event):
        buff = event.current_buffer
        pos = buff.document.find_previous_word_beginning(count=event.arg, WORD=True)
        if pos:
            buff.cursor_position += pos

    @bindings.add(Keys.ControlRight)
    def ctrl_right(event):
        buff = event.current_buffer
        pos = buff.document.find_next_word_ending(count=event.arg, WORD=True)
        if pos:
            buff.cursor_position += pos

    @bindings.add(Keys.ShiftDelete, filter=insert_mode)
    def delete_surrounding_big_word(event):
        buff = event.current_buffer
        startpos, endpos = buff.document.find_boundaries_of_current_word(WORD=True)
        startpos = buff.cursor_position + startpos - 1
        startpos = 0 if startpos < 0 else startpos
        endpos = buff.cursor_position + endpos
        endpos = endpos + 1 if startpos == 0 else endpos
        buff.text = buff.text[:startpos] + buff.text[endpos:]
        buff.cursor_position = startpos

    @bindings.add(Keys.ControlDelete, filter=insert_mode)
    def delete_big_word(event):
        buff = event.current_buffer
        pos = buff.document.find_next_word_ending(count=event.arg, WORD=True)
        if pos:
            buff.delete(count=pos)

    @bindings.add(Keys.Escape, Keys.Delete, filter=insert_mode)
    def delete_small_word(event):
        get_by_name("kill-word").call(event)

    # PTK sets both "\x7f" (^?) and "\x08" (^H) to the same behavior. Refs:
    # https://github.com/prompt-toolkit/python-prompt-toolkit/blob/65c3d0607c69c19d80abb052a18569a2546280e5/src/prompt_toolkit/input/ansi_escape_sequences.py#L65
    # https://github.com/prompt-toolkit/python-prompt-toolkit/issues/257#issuecomment-190328366
    # We patch the ANSI sequences used by PTK.  This requires a terminal
    # that sends different codes for <backspace> and <control-h>.
    # PTK sets Keys.Backspace = Keys.ControlH, so we hardcode the code.
    # Windows has the codes reversed, see https://github.com/xonsh/xonsh/commit/406d20f78f18af39d9bbaf9580b0a763df78a0db
    if XSH.env.get("XONSH_WHOLE_WORD_CTRL_BKSP", True):
        CONTROL_BKSP = "\x08"
        if ON_WINDOWS:
            # On windows BKSP is "\x08" and CTRL-BKSP is "\x7f"
            CONTROL_BKSP = "\x7f"
            ptk_win32.ConsoleInputReader.mappings[b"\x7f"] = CONTROL_BKSP
        ansiseq.ANSI_SEQUENCES[CONTROL_BKSP] = CONTROL_BKSP
        ansiseq.REVERSE_ANSI_SEQUENCES[CONTROL_BKSP] = CONTROL_BKSP

        @bindings.add(CONTROL_BKSP, filter=insert_mode)
        def backward_delete_big_word(event):
            get_by_name("unix-word-rubout").call(event)

    # backward_delete_small_word works on Alt+Backspace by default


def _load_xontrib_(xsh: XonshSession, **_):
    xsh.builtins.events.on_ptk_create(custom_keybindings)
