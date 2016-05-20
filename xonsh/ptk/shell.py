# -*- coding: utf-8 -*-
"""The prompt_toolkit based xonsh shell."""
import builtins

from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.filters import Condition
from prompt_toolkit.styles import PygmentsStyle
from pygments.styles import get_all_styles
from pygments.token import Token

from xonsh.base_shell import BaseShell
from xonsh.tools import print_exception
from xonsh.environ import partial_format_prompt
from xonsh.platform import ptk_version, ptk_version_info
from xonsh.pyghooks import (XonshLexer, partial_color_tokenize,
                            xonsh_style_proxy)
from xonsh.ptk.completer import PromptToolkitCompleter
from xonsh.ptk.history import PromptToolkitHistory
from xonsh.ptk.key_bindings import load_xonsh_bindings
from xonsh.ptk.shortcuts import Prompter, print_tokens


class PromptToolkitShell(BaseShell):
    """The xonsh shell."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prompter = Prompter()
        self.history = PromptToolkitHistory()
        self.pt_completer = PromptToolkitCompleter(self.completer, self.ctx)

        key_bindings_manager_args = {
                'enable_auto_suggest_bindings': True,
                'enable_search': True,
                'enable_abort_and_exit_bindings': True,
                'enable_open_in_editor': True,
                }
        major, minor = ptk_version_info()[:2]
        self.new_vi_mode_flag = (major, minor) >= (1, 0) \
                                and ptk_version() != '<0.57'
        if not self.new_vi_mode_flag:
            # enable_vi_mode is deprecated acoording to prompt_toolset 1.0 document.
            key_bindings_manager_args['enable_vi_mode'] = Condition(lambda cli: builtins.__xonsh_env__.get('VI_MODE'))

        self.key_bindings_manager = KeyBindingManager(**key_bindings_manager_args)
        load_xonsh_bindings(self.key_bindings_manager)

    def singleline(self, store_in_history=True, auto_suggest=None,
                   enable_history_search=True, multiline=True, **kwargs):
        """Reads a single line of input from the shell. The store_in_history
        kwarg flags whether the input should be stored in PTK's in-memory
        history.
        """
        env = builtins.__xonsh_env__
        mouse_support = env.get('MOUSE_SUPPORT')
        if store_in_history:
            history = self.history
        else:
            history = None
            enable_history_search = False
        auto_suggest = auto_suggest if env.get('AUTO_SUGGEST') else None
        completions_display = env.get('COMPLETIONS_DISPLAY')
        multicolumn = (completions_display == 'multi')
        self.styler.style_name = env.get('XONSH_COLOR_STYLE')
        completer = None if completions_display == 'none' else self.pt_completer
        prompt_tokens = self.prompt_tokens(None)
        get_prompt_tokens = lambda cli: prompt_tokens
        rprompt_tokens = self.rprompt_tokens(None)
        get_rprompt_tokens = lambda cli: rprompt_tokens
        with self.prompter:
            prompt_args = {
                    'mouse_support': mouse_support,
                    'auto_suggest': auto_suggest,
                    'get_prompt_tokens': get_prompt_tokens,
                    'get_rprompt_tokens': get_rprompt_tokens,
                    'style': PygmentsStyle(xonsh_style_proxy(self.styler)),
                    'completer': completer,
                    'lexer': PygmentsLexer(XonshLexer),
                    'multiline': multiline,
                    'get_continuation_tokens': self.continuation_tokens,
                    'history': history,
                    'enable_history_search': enable_history_search,
                    'reserve_space_for_menu': 0,
                    'key_bindings_registry': self.key_bindings_manager.registry,
                    'display_completions_in_columns': multicolumn
                    }
            if self.new_vi_mode_flag:
                prompt_args['vi_mode'] = env.get('VI_MODE')
            line = self.prompter.prompt(**prompt_args)
        return line

    def push(self, line):
        """Pushes a line onto the buffer and compiles the code in a way that
        enables multiline input.
        """
        code = None
        self.buffer.append(line)
        if self.need_more_lines:
            return None, code
        src = ''.join(self.buffer)
        try:
            code = self.execer.compile(src,
                                       mode='single',
                                       glbs=self.ctx,
                                       locs=None)
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
        while not builtins.__xonsh_exit__:
            try:
                line = self.singleline(auto_suggest=auto_suggest)
                if not line:
                    self.emptyline()
                else:
                    line = self.precmd(line)
                    self.default(line)
            except KeyboardInterrupt:
                self.reset_buffer()
            except EOFError:
                if builtins.__xonsh_env__.get("IGNOREEOF"):
                    print('Use "exit" to leave the shell.')
                else:
                    break

    def prompt_tokens(self, cli):
        """Returns a list of (token, str) tuples for the current prompt."""
        p = builtins.__xonsh_env__.get('PROMPT')
        try:
            p = partial_format_prompt(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        toks = partial_color_tokenize(p)
        self.settitle()
        return toks

    def rprompt_tokens(self, cli):
        """Returns a list of (token, str) tuples for the current right
        prompt.
        """
        p = builtins.__xonsh_env__.get('RIGHT_PROMPT')
        if len(p) == 0:
            return []
        try:
            p = partial_format_prompt(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        toks = partial_color_tokenize(p)
        return toks

    def continuation_tokens(self, cli, width):
        """Displays dots in multiline prompt"""
        dots = builtins.__xonsh_env__.get('MULTILINE_PROMPT')
        _width = width - 1
        dots = _width // len(dots) * dots + dots[:_width % len(dots)]
        return [(Token, dots + ' ')]

    def format_color(self, string, **kwargs):
        """Formats a color string using Pygments. This, therefore, returns
        a list of (Token, str) tuples.
        """
        return partial_color_tokenize(string)

    def print_color(self, string, end='\n', **kwargs):
        """Prints a color string using prompt-toolkit color management."""
        env = builtins.__xonsh_env__
        self.styler.style_name = env.get('XONSH_COLOR_STYLE')
        if isinstance(string, str):
            tokens = partial_color_tokenize(string + end)
        else:
            # assume this is a list of (Token, str) tuples and just print
            tokens = string
        proxy_style = PygmentsStyle(xonsh_style_proxy(self.styler))
        print_tokens(tokens, style=proxy_style)

    def color_style_names(self):
        """Returns an iterable of all available style names."""
        return get_all_styles()

    def color_style(self):
        """Returns the current color map."""
        env = builtins.__xonsh_env__
        self.styler.style_name = env.get('XONSH_COLOR_STYLE')
        return self.styler.styles
