# -*- coding: utf-8 -*-
"""The prompt_toolkit based xonsh shell."""
import sys
import builtins

from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import print_tokens
from prompt_toolkit.styles import PygmentsStyle, style_from_dict

from xonsh.base_shell import BaseShell
from xonsh.tools import print_exception, carriage_return, ansicolors_to_ptk1_names
from xonsh.ptk.completer import PromptToolkitCompleter
from xonsh.ptk.history import PromptToolkitHistory
from xonsh.ptk.key_bindings import load_xonsh_bindings
from xonsh.ptk.shortcuts import Prompter
from xonsh.events import events
from xonsh.shell import transform_command
from xonsh.platform import HAS_PYGMENTS, ON_WINDOWS
from xonsh.style_tools import (
    partial_color_tokenize,
    _TokenType,
    DEFAULT_STYLE_DICT as _DEFAULT_STYLE_DICT,
)
from xonsh.lazyimps import pygments, pyghooks, winutils
from xonsh.pygments_cache import get_all_styles
from xonsh.lazyasd import LazyObject


Token = _TokenType()

events.transmogrify("on_ptk_create", "LoadEvent")
events.doc(
    "on_ptk_create",
    """
on_ptk_create(prompter: Prompter, history: PromptToolkitHistory, completer: PromptToolkitCompleter, bindings: KeyBindingManager) ->

Fired after prompt toolkit has been initialized
""",
)

# Convert new ansicolor names to names
# understood by PTK1
DEFAULT_STYLE_DICT = LazyObject(
    lambda: ansicolors_to_ptk1_names(_DEFAULT_STYLE_DICT),
    globals(),
    "DEFAULT_STYLE_DICT",
)


class PromptToolkitShell(BaseShell):
    """The xonsh shell."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if ON_WINDOWS:
            winutils.enable_virtual_terminal_processing()
        self._first_prompt = True
        self.prompter = Prompter()
        self.history = PromptToolkitHistory()
        self.pt_completer = PromptToolkitCompleter(self.completer, self.ctx, self)
        key_bindings_manager_args = {
            "enable_auto_suggest_bindings": True,
            "enable_search": True,
            "enable_abort_and_exit_bindings": True,
        }
        self.key_bindings_manager = KeyBindingManager(**key_bindings_manager_args)
        load_xonsh_bindings(self.key_bindings_manager)
        # This assumes that PromptToolkitShell is a singleton
        events.on_ptk_create.fire(
            prompter=self.prompter,
            history=self.history,
            completer=self.pt_completer,
            bindings=self.key_bindings_manager,
        )

    def singleline(
        self,
        store_in_history=True,
        auto_suggest=None,
        enable_history_search=True,
        multiline=True,
        **kwargs
    ):
        """Reads a single line of input from the shell. The store_in_history
        kwarg flags whether the input should be stored in PTK's in-memory
        history.
        """
        events.on_pre_prompt.fire()
        env = builtins.__xonsh__.env
        mouse_support = env.get("MOUSE_SUPPORT")
        if store_in_history:
            history = self.history
        else:
            history = None
            enable_history_search = False
        auto_suggest = auto_suggest if env.get("AUTO_SUGGEST") else None
        completions_display = env.get("COMPLETIONS_DISPLAY")
        multicolumn = completions_display == "multi"
        complete_while_typing = env.get("UPDATE_COMPLETIONS_ON_KEYPRESS")
        if complete_while_typing:
            # PTK requires history search to be none when completing while typing
            enable_history_search = False
        if HAS_PYGMENTS:
            self.styler.style_name = env.get("XONSH_COLOR_STYLE")
        completer = None if completions_display == "none" else self.pt_completer
        if not env.get("UPDATE_PROMPT_ON_KEYPRESS"):
            prompt_tokens_cached = self.prompt_tokens(None)
            get_prompt_tokens = lambda cli: prompt_tokens_cached
            rprompt_tokens_cached = self.rprompt_tokens(None)
            get_rprompt_tokens = lambda cli: rprompt_tokens_cached
            bottom_toolbar_tokens_cached = self.bottom_toolbar_tokens(None)
            get_bottom_toolbar_tokens = lambda cli: bottom_toolbar_tokens_cached
        else:
            get_prompt_tokens = self.prompt_tokens
            get_rprompt_tokens = self.rprompt_tokens
            get_bottom_toolbar_tokens = self.bottom_toolbar_tokens

        with self.prompter:
            prompt_args = {
                "mouse_support": mouse_support,
                "auto_suggest": auto_suggest,
                "get_prompt_tokens": get_prompt_tokens,
                "get_rprompt_tokens": get_rprompt_tokens,
                "get_bottom_toolbar_tokens": get_bottom_toolbar_tokens,
                "completer": completer,
                "multiline": multiline,
                "get_continuation_tokens": self.continuation_tokens,
                "history": history,
                "enable_history_search": enable_history_search,
                "reserve_space_for_menu": 0,
                "key_bindings_registry": self.key_bindings_manager.registry,
                "display_completions_in_columns": multicolumn,
                "complete_while_typing": complete_while_typing,
            }
            if builtins.__xonsh__.env.get("COLOR_INPUT"):
                if HAS_PYGMENTS:
                    prompt_args["lexer"] = PygmentsLexer(pyghooks.XonshLexer)
                    prompt_args["style"] = PygmentsStyle(
                        pyghooks.xonsh_style_proxy(self.styler)
                    )
                else:
                    prompt_args["style"] = style_from_dict(DEFAULT_STYLE_DICT)
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
            code = self.execer.compile(src, mode="single", glbs=self.ctx, locs=None)
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
        self.push = self._push
        while not builtins.__xonsh__.exit:
            try:
                line = self.singleline(auto_suggest=auto_suggest)
                if not line:
                    self.emptyline()
                else:
                    line = self.precmd(line)
                    self.default(line)
            except (KeyboardInterrupt, SystemExit):
                self.reset_buffer()
            except EOFError:
                if builtins.__xonsh__.env.get("IGNOREEOF"):
                    print('Use "exit" to leave the shell.', file=sys.stderr)
                else:
                    break

    def prompt_tokens(self, cli):
        """Returns a list of (token, str) tuples for the current prompt."""
        p = builtins.__xonsh__.env.get("PROMPT")
        try:
            p = self.prompt_formatter(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        toks = partial_color_tokenize(p)
        if self._first_prompt:
            carriage_return()
            self._first_prompt = False
        self.settitle()
        return toks

    def rprompt_tokens(self, cli):
        """Returns a list of (token, str) tuples for the current right
        prompt.
        """
        p = builtins.__xonsh__.env.get("RIGHT_PROMPT")
        # self.prompt_formatter does handle empty strings properly,
        # but this avoids descending into it in the common case of
        # $RIGHT_PROMPT == ''.
        if isinstance(p, str) and len(p) == 0:
            return []
        try:
            p = self.prompt_formatter(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        toks = partial_color_tokenize(p)
        return toks

    def bottom_toolbar_tokens(self, cli):
        """Returns a list of (token, str) tuples for the current bottom
        toolbar.
        """
        p = builtins.__xonsh__.env.get("BOTTOM_TOOLBAR")
        # self.prompt_formatter does handle empty strings properly,
        # but this avoids descending into it in the common case of
        # $TOOLBAR == ''.
        if isinstance(p, str) and len(p) == 0:
            return []
        try:
            p = self.prompt_formatter(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        toks = partial_color_tokenize(p)
        return toks

    def continuation_tokens(self, cli, width):
        """Displays dots in multiline prompt"""
        width = width - 1
        dots = builtins.__xonsh__.env.get("MULTILINE_PROMPT")
        dots = dots() if callable(dots) else dots
        if dots is None:
            return [(Token, " " * (width + 1))]
        basetoks = self.format_color(dots)
        baselen = sum(len(t[1]) for t in basetoks)
        if baselen == 0:
            return [(Token, " " * (width + 1))]
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
        return toks

    def format_color(self, string, hide=False, force_string=False, **kwargs):
        """Formats a color string using Pygments. This, therefore, returns
        a list of (Token, str) tuples. If force_string is set to true, though,
        this will return a color formatted string.
        """
        tokens = partial_color_tokenize(string)
        if force_string and HAS_PYGMENTS:
            env = builtins.__xonsh__.env
            self.styler.style_name = env.get("XONSH_COLOR_STYLE")
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
            tokens = partial_color_tokenize(string + end)
        else:
            # assume this is a list of (Token, str) tuples and just print
            tokens = string
        if HAS_PYGMENTS:
            env = builtins.__xonsh__.env
            self.styler.style_name = env.get("XONSH_COLOR_STYLE")
            proxy_style = PygmentsStyle(pyghooks.xonsh_style_proxy(self.styler))
        else:
            proxy_style = style_from_dict(DEFAULT_STYLE_DICT)
        print_tokens(tokens, style=proxy_style)

    def color_style_names(self):
        """Returns an iterable of all available style names."""
        if not HAS_PYGMENTS:
            return ["For other xonsh styles, please install pygments"]
        return get_all_styles()

    def color_style(self):
        """Returns the current color map."""
        if not HAS_PYGMENTS:
            return DEFAULT_STYLE_DICT
        env = builtins.__xonsh__.env
        self.styler.style_name = env.get("XONSH_COLOR_STYLE")
        return self.styler.styles

    def restore_tty_sanity(self):
        """An interface for resetting the TTY stdin mode. This is highly
        dependent on the shell backend. Also it is mostly optional since
        it only affects ^Z backgrounding behaviour.
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
