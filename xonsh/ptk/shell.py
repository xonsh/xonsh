# -*- coding: utf-8 -*-
"""The prompt_toolkit based xonsh shell."""
import builtins
from warnings import warn

from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.filters import Condition
from prompt_toolkit.styles import PygmentsStyle
from pygments.style import Style
from pygments.styles.default import DefaultStyle
from pygments.token import (Keyword, Name, Comment, String, Error, Number,
                            Operator, Generic, Whitespace, Token)

from xonsh.base_shell import BaseShell
from xonsh.tools import print_exception, format_color
from xonsh.environ import partial_format_prompt
from xonsh.pyghooks import XonshLexer, XonshStyle, partial_color_tokenize
from xonsh.ptk.completer import PromptToolkitCompleter
from xonsh.ptk.history import PromptToolkitHistory
from xonsh.ptk.key_bindings import load_xonsh_bindings
from xonsh.ptk.shortcuts import Prompter, print_tokens


class PromptToolkitShell(BaseShell):
    """The xonsh shell."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.styler = XonshStyle(builtins.__xonsh_env__.get('XONSH_COLOR_STYLE'))
        self.prompter = Prompter()
        self.history = PromptToolkitHistory()
        self.pt_completer = PromptToolkitCompleter(self.completer, self.ctx)
        self.key_bindings_manager = KeyBindingManager(
            enable_auto_suggest_bindings=True,
            enable_search=True,
            enable_abort_and_exit_bindings=True,
            enable_vi_mode=Condition(lambda cli: builtins.__xonsh_env__.get('VI_MODE')),
            enable_open_in_editor=True)
        load_xonsh_bindings(self.key_bindings_manager)

    def singleline(self, store_in_history=True, auto_suggest=None,
                   enable_history_search=True, multiline=True, **kwargs):
        """Reads a single line of input from the shell. The store_in_history
        kwarg flags whether the input should be stored in PTK's in-memory
        history.
        """
        #token_func, style_cls = self._get_prompt_tokens_and_style()
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
        with self.prompter:
            line = self.prompter.prompt(
                    mouse_support=mouse_support,
                    auto_suggest=auto_suggest,
                    get_prompt_tokens=self.prompt_tokens,
                    style=self.styler,
                    completer=completer,
                    lexer=PygmentsLexer(XonshLexer),
                    multiline=multiline,
                    history=history,
                    enable_history_search=enable_history_search,
                    reserve_space_for_menu=0,
                    key_bindings_registry=self.key_bindings_manager.registry,
                    display_completions_in_columns=multicolumn)
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
                                       glbs=None,
                                       locs=self.ctx)
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

    #def _get_prompt_tokens_and_style(self):
    #    """Returns function to pass as prompt to prompt_toolkit."""
    #    token_names, cstyles, strings = format_prompt_for_prompt_toolkit(self.prompt)
    #    tokens = [getattr(Token, n) for n in token_names]
    #    def get_tokens(cli):
    #        return list(zip(tokens, strings))
    #    custom_style = _xonsh_style(tokens, cstyles)
    #    return get_tokens, custom_style

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

    def print_color(self, string,end='\n', **kwargs):
        """Prints a color string using prompt-toolkit color management."""
        s = format_color(string + end, remove_escapes=False)
        token_names, cstyles, strings = format_prompt_for_prompt_toolkit(s)
        toks = [getattr(Token, n) for n in token_names]
        custom_style = PygmentsStyle(_xonsh_style(toks, cstyles))
        tokens = list(zip(toks, strings))
        print_tokens(tokens, style=custom_style)


