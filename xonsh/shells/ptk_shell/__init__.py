"""The prompt_toolkit based xonsh shell."""

import os
import re
import sys
from functools import wraps
from types import MethodType

from prompt_toolkit import ANSI
from prompt_toolkit.application.current import get_app
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.clipboard import InMemoryClipboard
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.formatted_text import PygmentsTokens, to_formatted_text
from prompt_toolkit.history import ThreadedHistory
from prompt_toolkit.key_binding.bindings.emacs import (
    load_emacs_shift_selection_bindings,
)
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.key_binding.key_bindings import merge_key_bindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.shortcuts import print_formatted_text as ptk_print
from prompt_toolkit.shortcuts.prompt import PromptSession
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.styles.pygments import pygments_token_to_classname

from xonsh.built_ins import XSH
from xonsh.events import events
from xonsh.lib.lazyimps import pyghooks, pygments, winutils
from xonsh.platform import HAS_PYGMENTS, ON_POSIX, ON_WINDOWS
from xonsh.pygments_cache import get_all_styles
from xonsh.shell import transform_command
from xonsh.shells.base_shell import BaseShell
from xonsh.shells.ptk_shell.completer import PromptToolkitCompleter
from xonsh.shells.ptk_shell.formatter import PTKPromptFormatter
from xonsh.shells.ptk_shell.history import PromptToolkitHistory, _cust_history_matches
from xonsh.shells.ptk_shell.key_bindings import load_xonsh_bindings
from xonsh.style_tools import DEFAULT_STYLE_DICT, _TokenType, partial_color_tokenize
from xonsh.tools import carriage_return, print_exception, print_warning

try:
    from prompt_toolkit.clipboard import DummyClipboard
    from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard

    HAVE_SYS_CLIPBOARD = True
except ImportError:
    HAVE_SYS_CLIPBOARD = False

try:
    from prompt_toolkit.cursor_shapes import ModalCursorShapeConfig

    HAVE_CURSOR_SHAPE = True
except ImportError:
    HAVE_CURSOR_SHAPE = False

CAPITAL_PATTERN = re.compile(r"([a-z])([A-Z])")
Token = _TokenType()

events.transmogrify("on_ptk_create", "LoadEvent")
events.doc(
    "on_ptk_create",
    """
on_ptk_create(prompter: PromptSession, history: PromptToolkitHistory, completer: PromptToolkitCompleter, bindings: KeyBindings) ->

Fired after prompt toolkit has been initialized
""",
)


def tokenize_ansi(tokens):
    """Checks a list of (token, str) tuples for ANSI escape sequences and
    extends the token list with the new formatted entries.
    During processing tokens are converted to ``prompt_toolkit.FormattedText``.
    Returns a list of similar (token, str) tuples.
    """
    formatted_tokens = to_formatted_text(tokens)
    ansi_tokens = []
    for style, text in formatted_tokens:
        if "\x1b" in text:
            formatted_ansi = to_formatted_text(ANSI(text))
            ansi_text = ""
            prev_style = ""
            for ansi_style, ansi_text_part in formatted_ansi:
                if prev_style == ansi_style:
                    ansi_text += ansi_text_part
                else:
                    ansi_tokens.append((prev_style or style, ansi_text))
                    prev_style = ansi_style
                    ansi_text = ansi_text_part
            ansi_tokens.append((prev_style or style, ansi_text))
        else:
            ansi_tokens.append((style, text))
    return ansi_tokens


def _pygments_token_to_classname(token):
    """Converts pygments Tokens, token names (strings) to PTK style names."""
    if token and isinstance(token, str):
        # if starts with non capital letter => leave it as it is
        if token[0].islower():
            return token
        # if starts with capital letter => pygments token name
        if token.startswith("Token."):
            token = token[6:]
        # short colors - all caps
        if token == token.upper():
            token = "color." + token
        return "pygments." + token.lower()

    return pygments_token_to_classname(token)


def _style_from_pygments_dict(pygments_dict):
    """Custom implementation of ``style_from_pygments_dict`` that supports PTK specific
    (``Token.PTK``) styles.
    """
    pygments_style = []

    for token, style in pygments_dict.items():
        # if ``Token.PTK`` then add it as "native" PTK style too
        if str(token).startswith("Token.PTK"):
            key = CAPITAL_PATTERN.sub(r"\1-\2", str(token)[10:]).lower()
            pygments_style.append((key, style))
        pygments_style.append((_pygments_token_to_classname(token), style))

    return Style(pygments_style)


def _style_from_pygments_cls(pygments_cls):
    """Custom implementation of ``style_from_pygments_cls`` that supports PTK specific
    (``Token.PTK``) styles.
    """
    return _style_from_pygments_dict(pygments_cls.styles)


def disable_copy_on_deletion():
    dummy_clipboard = DummyClipboard()
    ignored_actions = [
        "kill-line",
        "kill-word",
        "unix-word-rubout",
        "unix-line-discard",
        "backward-kill-word",
    ]

    def handle_binding(name):
        try:
            binding = get_by_name(name)
        except KeyError:
            print_warning(f"Failed to disable clipboard for ptk action {name!r}")
            return

        if getattr(binding, "xonsh_disabled_clipboard", False):
            # binding's clipboard has already been disabled
            return

        binding.xonsh_disabled_clipboard = True
        original_handler = binding.handler

        # this needs to be defined inside a function so that ``binding`` will be the correct one
        @wraps(original_handler)
        def wrapped_handler(event):
            app = event.app
            prev = app.clipboard
            app.clipboard = dummy_clipboard
            try:
                return original_handler(event)
            finally:
                app.clipboard = prev

        binding.handler = wrapped_handler

    for _name in ignored_actions:
        handle_binding(_name)


class PromptToolkitShell(BaseShell):
    """The xonsh shell for prompt_toolkit v2 and later."""

    completion_displays_to_styles = {
        "multi": CompleteStyle.MULTI_COLUMN,
        "single": CompleteStyle.COLUMN,
        "readline": CompleteStyle.READLINE_LIKE,
        "none": None,
    }

    def __init__(self, **kwargs):
        if not XSH.env.get("XONSH_DEBUG", False):
            __import__("warnings").filterwarnings(
                "ignore",
                "There is no current event loop",
                DeprecationWarning,
                module="prompt_toolkit.application.application",
            )

        ptk_args = kwargs.pop("ptk_args", {})
        super().__init__(**kwargs)
        if ON_WINDOWS:
            winutils.enable_virtual_terminal_processing()
        self._first_prompt = True
        self.history = ThreadedHistory(PromptToolkitHistory())
        self.push = self._push

        ptk_args.setdefault("history", self.history)
        if not XSH.env.get("XONSH_COPY_ON_DELETE", False):
            disable_copy_on_deletion()
        if HAVE_SYS_CLIPBOARD and (XSH.env.get("XONSH_USE_SYSTEM_CLIPBOARD", True)):
            default_clipboard = PyperclipClipboard()
        else:
            default_clipboard = InMemoryClipboard()
        ptk_args.setdefault("clipboard", default_clipboard)
        self.prompter: PromptSession = PromptSession(**ptk_args)

        self.prompt_formatter = PTKPromptFormatter(self)
        self.pt_completer = PromptToolkitCompleter(self.completer, self.ctx, self)
        ptk_bindings = self.prompter.app.key_bindings
        self.key_bindings = load_xonsh_bindings(ptk_bindings)
        self._overrides_deprecation_warning_shown = False

        # Store original `_history_matches` in case we need to restore it
        self._history_matches_orig = self.prompter.default_buffer._history_matches
        # This assumes that PromptToolkitShell is a singleton
        events.on_ptk_create.fire(
            prompter=self.prompter,
            history=self.history,
            completer=self.pt_completer,
            bindings=self.key_bindings,
        )
        # Goes at the end, since _MergedKeyBindings objects do not have
        # an add() function, which is necessary for on_ptk_create events
        self.key_bindings = merge_key_bindings(
            [self.key_bindings, load_emacs_shift_selection_bindings()]
        )

    def get_lazy_ptk_kwargs(self):
        """These are non-essential attributes for the PTK shell to start.
        Lazy loading these later would save some startup time.
        """
        if not XSH.env.get("COLOR_INPUT"):
            return

        if HAS_PYGMENTS:
            # these imports slowdown a little
            from prompt_toolkit.lexers import PygmentsLexer

            yield "lexer", PygmentsLexer(pyghooks.XonshLexer)

        events.on_timingprobe.fire(name="on_pre_prompt_style")
        yield "style", self.get_prompt_style()
        events.on_timingprobe.fire(name="on_post_prompt_style")

    def get_prompt_style(self):
        env = XSH.env

        style_overrides_env = env.get("PTK_STYLE_OVERRIDES", {}).copy()
        if (
            len(style_overrides_env) > 0
            and not self._overrides_deprecation_warning_shown
        ):
            print_warning(
                "$PTK_STYLE_OVERRIDES is deprecated, use $XONSH_STYLE_OVERRIDES instead!"
            )
            self._overrides_deprecation_warning_shown = True
        style_overrides_env.update(env.get("XONSH_STYLE_OVERRIDES", {}))

        if HAS_PYGMENTS:
            style = _style_from_pygments_cls(pyghooks.xonsh_style_proxy(self.styler))
            if len(self.styler.non_pygments_rules) > 0:
                try:
                    style = merge_styles(
                        [
                            style,
                            _style_from_pygments_dict(self.styler.non_pygments_rules),
                        ]
                    )
                except (AttributeError, TypeError, ValueError) as style_exception:
                    print_warning(
                        f"Error applying style override!\n{style_exception}\n"
                    )

        else:
            style = _style_from_pygments_dict(DEFAULT_STYLE_DICT)

        if len(style_overrides_env) > 0:
            try:
                style = merge_styles(
                    [style, _style_from_pygments_dict(style_overrides_env)]
                )
            except (AttributeError, TypeError, ValueError) as style_exception:
                print_warning(f"Error applying style override!\n{style_exception}\n")
        return style

    def singleline(
        self, auto_suggest=None, enable_history_search=True, multiline=True, **kwargs
    ):
        """Reads a single line of input from the shell. The store_in_history
        kwarg flags whether the input should be stored in PTK's in-memory
        history.
        """
        events.on_pre_prompt_format.fire()
        env = XSH.env
        mouse_support = env.get("MOUSE_SUPPORT")
        auto_suggest = auto_suggest if env.get("AUTO_SUGGEST") else None
        refresh_interval = env.get("PROMPT_REFRESH_INTERVAL")
        refresh_interval = refresh_interval if refresh_interval > 0 else None
        complete_in_thread = env.get("COMPLETION_IN_THREAD")
        completions_display = env.get("COMPLETIONS_DISPLAY")
        complete_style = self.completion_displays_to_styles[completions_display]

        complete_while_typing = env.get("UPDATE_COMPLETIONS_ON_KEYPRESS")
        if complete_while_typing:
            # PTK requires history search to be none when completing while typing
            enable_history_search = False
        if HAS_PYGMENTS:
            self.styler.style_name = env.get("XONSH_COLOR_STYLE")
        completer = None if completions_display == "none" else self.pt_completer

        events.on_timingprobe.fire(name="on_pre_prompt_tokenize")

        # clear prompt level cache
        env["PROMPT_FIELDS"].reset()

        get_bottom_toolbar_tokens = self.bottom_toolbar_tokens
        if env.get("UPDATE_PROMPT_ON_KEYPRESS"):
            get_prompt_tokens = self.prompt_tokens
            get_rprompt_tokens = self.rprompt_tokens
        else:
            get_prompt_tokens = self.prompt_tokens()
            get_rprompt_tokens = self.rprompt_tokens()
            if get_bottom_toolbar_tokens:
                get_bottom_toolbar_tokens = get_bottom_toolbar_tokens()
        events.on_timingprobe.fire(name="on_post_prompt_tokenize")

        if env.get("VI_MODE"):
            editing_mode = EditingMode.VI
        else:
            editing_mode = EditingMode.EMACS

        if env.get("XONSH_HISTORY_MATCH_ANYWHERE"):
            self.prompter.default_buffer._history_matches = MethodType(
                _cust_history_matches, self.prompter.default_buffer
            )
        elif (
            self.prompter.default_buffer._history_matches
            is not self._history_matches_orig
        ):
            self.prompter.default_buffer._history_matches = self._history_matches_orig

        menu_rows = env.get("COMPLETIONS_MENU_ROWS", None)
        if menu_rows:
            # https://github.com/xonsh/xonsh/pull/4477#pullrequestreview-767982976
            menu_rows += 1

        prompt_args = {
            "mouse_support": mouse_support,
            "auto_suggest": auto_suggest,
            "message": get_prompt_tokens,
            "rprompt": get_rprompt_tokens,
            "bottom_toolbar": get_bottom_toolbar_tokens,
            "completer": completer,
            "multiline": multiline,
            "editing_mode": editing_mode,
            "prompt_continuation": self.continuation_tokens,
            "enable_history_search": enable_history_search,
            "reserve_space_for_menu": menu_rows,
            "key_bindings": self.key_bindings,
            "complete_style": complete_style,
            "complete_while_typing": complete_while_typing,
            "include_default_pygments_style": False,
            "refresh_interval": refresh_interval,
            "complete_in_thread": complete_in_thread,
        }
        if env["ENABLE_ASYNC_PROMPT"]:
            # once the prompt is done, update it in background as each future is completed
            prompt_args["pre_run"] = self.prompt_formatter.start_update
        else:
            for attr, val in self.get_lazy_ptk_kwargs():
                prompt_args[attr] = val

        if editing_mode == EditingMode.VI and HAVE_CURSOR_SHAPE:
            prompt_args["cursor"] = ModalCursorShapeConfig()
        events.on_pre_prompt.fire()
        line = self.prompter.prompt(**prompt_args)
        events.on_post_prompt.fire()
        return line

    def _push(self, line):
        """Pushes a line onto the buffer and compiles the code in a way that
        enables multiline input.
        """
        code = None
        self.buffer.append(line)
        if self.need_more_lines:
            return None, code
        src = "".join(self.buffer)
        src = transform_command(src)
        try:
            code = self.execer.compile(
                src, mode="single", glbs=self.ctx, locs=None, compile_empty_tree=False
            )
            self.reset_buffer()
        except Exception:  # pylint: disable=broad-except
            self.reset_buffer()
            print_exception()
            return src, None
        return src, code

    def cmdloop(self, intro=None):
        """Enters a loop that reads and execute input from user."""
        if intro:
            print(intro)
        auto_suggest = AutoSuggestFromHistory()
        while XSH.exit is None:
            try:
                line = self.singleline(auto_suggest=auto_suggest)
                if not line:
                    self.emptyline()
                else:
                    raw_line = line
                    line = self.precmd(line)
                    self.default(line, raw_line)
            except (KeyboardInterrupt, SystemExit) as e:
                self.reset_buffer()
                if isinstance(e, KeyboardInterrupt):
                    if XSH.env.get("XONSH_HISTORY_SIGINT_FLUSH", True):
                        """
                        Development tools like PyCharm send SIGINT before SIGKILL.
                        This is the last chance to save history in this case.
                        """
                        if XSH.env.get("XONSH_DEBUG", False):
                            print("Flushing history after SIGINT.", file=sys.stderr)
                        XSH.history.flush()
                if isinstance(e, SystemExit):
                    get_app().reset()  # Reset TTY mouse and keys handlers.
                    self.restore_tty_sanity()  # Reset TTY SIGINT handlers.
                    raise
            except EOFError:
                if XSH.env.get("IGNOREEOF"):
                    print('Use "exit" to leave the shell.', file=sys.stderr)
                else:
                    break

    def _get_prompt_tokens(self, env_name: str, prompt_name: str, **kwargs):
        env = XSH.env  # type:ignore
        p = env.get(env_name)

        if not p and "default" in kwargs:
            return kwargs.pop("default")

        try:
            p = self.prompt_formatter(
                template=p, threaded=env["ENABLE_ASYNC_PROMPT"], prompt_name=prompt_name
            )
        except Exception:  # pylint: disable=broad-except
            print_exception()

        toks = partial_color_tokenize(p)

        return tokenize_ansi(PygmentsTokens(toks))

    def prompt_tokens(self):
        """Returns a list of (token, str) tuples for the current prompt."""
        if self._first_prompt:
            carriage_return()
            self._first_prompt = False

        tokens = self._get_prompt_tokens("PROMPT", "message")
        self.settitle()
        return tokens

    def rprompt_tokens(self):
        """Returns a list of (token, str) tuples for the current right
        prompt.
        """
        return self._get_prompt_tokens("RIGHT_PROMPT", "rprompt", default=[])

    def _bottom_toolbar_tokens(self):
        """Returns a list of (token, str) tuples for the current bottom
        toolbar.
        """
        return self._get_prompt_tokens("BOTTOM_TOOLBAR", "bottom_toolbar", default=None)

    @property
    def bottom_toolbar_tokens(self):
        """Returns self._bottom_toolbar_tokens if it would yield a result"""
        if XSH.env.get("BOTTOM_TOOLBAR"):
            return self._bottom_toolbar_tokens

    def continuation_tokens(self, width, line_number, is_soft_wrap=False):
        """Displays dots in multiline prompt"""
        if is_soft_wrap:
            return ""
        width -= 1
        dots = XSH.env.get("MULTILINE_PROMPT")
        dots = dots() if callable(dots) else dots
        if not dots:
            return ""
        prefix = XSH.env.get(
            "MULTILINE_PROMPT_PRE", ""
        )  # e.g.: '\x01\x1b]133;P;k=c\x07\x02'
        suffix = XSH.env.get(
            "MULTILINE_PROMPT_POS", ""
        )  # e.g.: '\x01\x1b]133;B\x07\x02'
        is_affix = any(x for x in [prefix, suffix])
        if is_affix:
            prefixtoks = tokenize_ansi(PygmentsTokens(self.format_color(prefix)))
            suffixtoks = tokenize_ansi(PygmentsTokens(self.format_color(suffix)))
            # [('class:pygments.color.reset',''), ('[ZeroWidthEscape]','\x1b]133;P;k=c\x07')]
            # [('class:pygments.color.reset',''), ('[ZeroWidthEscape]','\x1b]133;B\x07')]

        basetoks = self.format_color(dots)
        baselen = sum(len(t[1]) for t in basetoks)
        if baselen == 0:
            toks = [(Token, " " * (width + 1))]
            if is_affix:  # to convert ↓ classes to str to allow +
                return prefixtoks + to_formatted_text(PygmentsTokens(toks)) + suffixtoks
            else:
                return PygmentsTokens(toks)
        toks = basetoks * (width // baselen)
        n = width % baselen
        count = 0
        for tok in basetoks:
            slen = len(tok[1])
            newcount = slen + count
            if slen == 0:
                continue
            elif newcount <= n:
                toks.append(tok)
            else:
                toks.append((tok[0], tok[1][: n - count]))
            count = newcount
            if n <= count:
                break
        toks.append((Token, " "))  # final space
        if is_affix:
            return prefixtoks + to_formatted_text(PygmentsTokens(toks)) + suffixtoks
        else:
            return PygmentsTokens(toks)

    def format_color(self, string, hide=False, force_string=False, **kwargs):
        """Formats a color string using Pygments. This, therefore, returns
        a list of (Token, str) tuples. If force_string is set to true, though,
        this will return a color formatted string.
        """
        tokens = partial_color_tokenize(string)
        if force_string and HAS_PYGMENTS:
            env = XSH.env
            style_overrides_env = env.get("XONSH_STYLE_OVERRIDES", {})
            self.styler.style_name = env.get("XONSH_COLOR_STYLE")
            self.styler.override(style_overrides_env)
            proxy_style = pyghooks.xonsh_style_proxy(self.styler)
            formatter = pyghooks.XonshTerminal256Formatter(style=proxy_style)
            s = pygments.format(tokens, formatter)
            return s
        elif force_string:
            print("To force colorization of string, install Pygments")
            return tokens
        else:
            return tokens

    def print_color(self, string, end="\n", **kwargs):
        """Prints a color string using prompt-toolkit color management."""
        if isinstance(string, str):
            tokens = partial_color_tokenize(string)
        else:
            # assume this is a list of (Token, str) tuples and just print
            tokens = string
        tokens = PygmentsTokens(tokens)
        env = XSH.env
        style_overrides_env = env.get("XONSH_STYLE_OVERRIDES", {})
        if HAS_PYGMENTS:
            self.styler.style_name = env.get("XONSH_COLOR_STYLE")
            self.styler.override(style_overrides_env)
            proxy_style = _style_from_pygments_cls(
                pyghooks.xonsh_style_proxy(self.styler)
            )
        else:
            proxy_style = merge_styles(
                [
                    _style_from_pygments_dict(DEFAULT_STYLE_DICT),
                    _style_from_pygments_dict(style_overrides_env),
                ]
            )
        ptk_print(
            tokens,
            style=proxy_style,
            end=end,
            include_default_pygments_style=False,
            **kwargs,
        )

    def color_style_names(self):
        """Returns an iterable of all available style names."""
        if not HAS_PYGMENTS:
            return ["For other xonsh styles, please install pygments"]
        return get_all_styles()

    def color_style(self):
        """Returns the current color map."""
        if not HAS_PYGMENTS:
            return DEFAULT_STYLE_DICT
        env = XSH.env
        self.styler.style_name = env.get("XONSH_COLOR_STYLE")
        return self.styler.styles

    def restore_tty_sanity(self):
        """An interface for resetting the TTY stdin mode. This is highly
        dependent on the shell backend.
        For prompt-toolkit it allows to fix case when terminal lost
        SIGINT catching and Ctrl+C is not working after abnormal exiting.
        """
        # PTK does not seem to need any specialization here. However,
        # if it does for some reason in the future...
        # The following writes an ANSI escape sequence that sends the cursor
        # to the end of the line. This has the effect of restoring ECHO mode.
        # See http://unix.stackexchange.com/a/108014/129048 for more details.
        # This line can also be replaced by os.system("stty sane"), as per
        # http://stackoverflow.com/questions/19777129/interactive-python-interpreter-run-in-background#comment29421919_19778355
        # However, it is important to note that not termios-based solution
        # seems to work. My guess is that this is because termios restoration
        # needs to be performed by the subprocess itself. This fix is important
        # when subprocesses don't properly restore the terminal attributes,
        # like Python in interactive mode. Also note that the sequences "\033M"
        # and "\033E" seem to work too, but these are technically VT100 codes.
        # I used the more primitive ANSI sequence to maximize compatibility.
        # -scopatz 2017-01-28
        #   if not ON_POSIX:
        #       return
        #   sys.stdout.write('\033[9999999C\n')
        if not ON_POSIX:
            return
        stty, _ = XSH.commands_cache.lazyget("stty", (None, None))
        if stty is None:
            return
        os.system(stty + " sane")
