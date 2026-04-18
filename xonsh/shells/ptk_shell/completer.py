"""Completer implementation to use with prompt_toolkit."""

import ast
import os

from prompt_toolkit.application.current import get_app
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText

from xonsh.built_ins import XSH
from xonsh.completers.tools import RichCompletion
from xonsh.lib.string import commonprefix
from xonsh.tools import print_exception


def unquote(completion):
    s: str = str(completion)
    quote: str
    if s.startswith("r'") or s.startswith("'"):
        quote = "'"
    elif s.startswith('r"') or s.startswith('"'):
        quote = '"'
    else:
        # No quote
        return s
    if not s.endswith(quote):
        return s
    if s[0] == "r" or "\\" not in s:
        # Simple path for raw strings and strings without escaping backslash
        if s[0] == "r":
            s = s[1:]
        if s.startswith(quote * 3) and s.endswith(quote * 3):
            return s[3:-3]
        else:
            return s[1:-1]
    else:
        # Theoretically this should happen only when both " and '
        # appears in the original completion,
        # and ' is escaped as \' while " is retained as " in a '...' quoted string
        # There may also be \\ in such quoted strings
        try:
            # Use literal eval for this rare case for simplicity
            # https://docs.python.org/3/library/ast.html#ast.literal_eval
            return ast.literal_eval(s)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            # Give up if something unexpected happen
            if XSH.env.get("XONSH_DEBUG"):
                print_exception(f"Unable to unquote completion {s}")
            return s


def _underline_span(text, start, end):
    """Build a FormattedText that underlines ``text[start:end]``."""
    parts = [("", text[:start]), ("underline", text[start:end])]
    if end < len(text):
        parts.append(("", text[end:]))
    return FormattedText(parts)


def _highlight_match(display_text, full_text, prefix, pre):
    """Create FormattedText with underline on the matched substring.

    Parameters
    ----------
    display_text : str
        The text shown in the completion menu (already trimmed by ``pre``).
    full_text : str
        The full unquoted completion text (before ``pre`` trimming).
    prefix : str
        The user-typed text to highlight.
    pre : int
        Number of characters stripped from the front of ``full_text``.

    Returns
    -------
    str or FormattedText
        Plain string if no highlight needed, FormattedText with underline
        on the matched portion otherwise.
    """
    if not prefix or not display_text:
        return display_text

    # Try to find the full prefix in the full text
    match_start = full_text.lower().find(prefix.lower())

    if match_start >= 0:
        disp_start = match_start - pre
        disp_end = disp_start + len(prefix)

        if disp_start > 0:
            # Substring match visible in display — underline it
            disp_end = min(len(display_text), disp_end)
            if disp_start < disp_end:
                return _underline_span(display_text, disp_start, disp_end)
        elif disp_start == 0:
            # Prefix match at display start — no underline needed
            return display_text

    # Full prefix not usable (not found, or falls before display start).
    # For dotted completions like "json.de" → "JSONDecoder", match the
    # visible portion of the prefix against the display text.
    if pre > 0:
        visible_prefix = prefix[pre:]
        if visible_prefix:
            vis_start = display_text.lower().find(visible_prefix.lower())
            if vis_start > 0:
                vis_end = min(len(display_text), vis_start + len(visible_prefix))
                if vis_start < vis_end:
                    return _underline_span(display_text, vis_start, vis_end)

    return display_text


class PromptToolkitCompleter(Completer):
    """Simple prompt_toolkit Completer object.

    It just redirects requests to normal Xonsh completer.
    """

    def __init__(self, completer, ctx, shell):
        """Takes instance of xonsh.completer.Completer, the xonsh execution
        context, and the shell instance itself.
        """
        self.completer = completer
        self.ctx = ctx
        self.shell = shell
        self.hist_suggester = AutoSuggestFromHistory()

    def get_completions(self, document, complete_event):
        """Returns a generator for list of completions."""
        env = XSH.env
        should_complete = complete_event.completion_requested or env.get(
            "UPDATE_COMPLETIONS_ON_KEYPRESS"
        )
        #  Only generate completions when the user hits tab.
        if not should_complete or self.completer is None:
            return
        # generate actual completions
        line = document.current_line

        endidx = document.cursor_position_col
        try:
            line_ex = XSH.aliases.expand_alias(line, endidx)
        except Exception as e:
            from xonsh.tools import print_above_prompt

            print_above_prompt(f"completer: {e}")
            return

        begidx = line[:endidx].rfind(" ") + 1 if line[:endidx].rfind(" ") >= 0 else 0
        prefix = line[begidx:endidx]
        expand_offset = len(line_ex) - len(line)

        multiline_text = document.text
        cursor_index = document.cursor_position
        if line != line_ex:
            line_start = cursor_index - len(document.current_line_before_cursor)
            multiline_text = (
                multiline_text[:line_start]
                + line_ex
                + multiline_text[line_start + len(line) :]
            )
            cursor_index += expand_offset

        # get normal completions
        completions, plen = self.completer.complete(
            prefix,
            line_ex,
            begidx + expand_offset,
            endidx + expand_offset,
            self.ctx,
            multiline_text=multiline_text,
            cursor_index=cursor_index,
        )

        # completions from auto suggest
        sug_comp = None
        if env.get("XONSH_PROMPT_AUTO_SUGGEST") and env.get(
            "AUTO_SUGGEST_IN_COMPLETIONS"
        ):
            sug_comp = self.suggestion_completion(document, line)
            if sug_comp is None:
                pass
            elif len(completions) == 0:
                plen = len(prefix)
                completions = (sug_comp,)
            else:
                # Preserve the sort order from complete_from_context
                # (tier-based: prefix > substring > no match) while
                # moving the auto-suggest entry to the front.
                completions = (sug_comp,) + tuple(
                    c for c in completions if c != sug_comp
                )
        # reserve space, if needed.
        if len(completions) <= 1:
            pass
        elif len(commonprefix(completions)) <= len(prefix):
            self.reserve_space()
        # Find common prefix (strip quoting)
        c_prefix = commonprefix([unquote(a) for a in completions])
        # Find last split symbol, do not trim the last part
        while c_prefix:
            if c_prefix[-1] in r"/\.:@,":
                break
            c_prefix = c_prefix[:-1]
        # yield completions
        if sug_comp is None:
            pre = min(document.cursor_position_col - begidx, len(c_prefix))
        else:
            pre = len(c_prefix)
        for comp in completions:
            # do not display quote
            if isinstance(comp, RichCompletion):
                # ptk doesn't render newlines. This can be removed once it is supported.
                desc = (
                    comp.description.replace(os.linesep, " ")
                    if comp.description
                    else None
                )
                if comp.display:
                    display = comp.display
                else:
                    full_text = unquote(comp)
                    disp = full_text[pre:]
                    display = _highlight_match(disp, full_text, prefix, pre)
                yield Completion(
                    comp,
                    -comp.prefix_len if comp.prefix_len is not None else -plen,
                    display=display,
                    display_meta=desc,
                    style=comp.style or "",
                )
            elif isinstance(comp, Completion):
                yield comp
            else:
                # pre is calculated after unquote,
                # so prefix cutting should also be performed afterwards
                full_text = unquote(comp)
                disp = full_text[pre:]
                yield Completion(
                    comp,
                    -plen,
                    display=_highlight_match(disp, full_text, prefix, pre),
                )

    def suggestion_completion(self, document, line):
        """Provides a completion based on the current auto-suggestion."""
        app = self.shell.prompter.app
        sug = self.hist_suggester.get_suggestion(app.current_buffer, document)
        if sug is None:
            return None
        _, _, prev = line.rpartition(" ")
        full_completion = prev + sug.text
        if len(full_completion) > 60:
            display_text = full_completion[:57] + "..."
            return RichCompletion(
                full_completion, display=display_text, append_space=False
            )
        return full_completion

    def reserve_space(self):
        """Adjust the height for showing autocompletion menu."""
        app = get_app()
        render = app.renderer

        window = None
        try:
            # this raises error sometimes when COMPLETE_WHILE_TYPE is enabled
            window = app.layout.current_window
        except Exception:
            pass

        if window and window.render_info:
            h = window.render_info.content_height
            r = XSH.env.get("COMPLETIONS_MENU_ROWS")
            size = h + r
            last_h = render._last_screen.height if render._last_screen else 0
            last_h = max(render._min_available_height, last_h)
            if last_h < size:
                if render._last_screen:
                    render._last_screen.height = size
