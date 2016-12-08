# -*- coding: utf-8 -*-
"""The prompt_toolkit based xonsh shell."""
import sys
import builtins

from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import print_tokens
from prompt_toolkit.styles import PygmentsStyle
import pygments
from pygments.styles import get_all_styles
from pygments.token import Token

from xonsh.base_shell import BaseShell
from xonsh.tools import print_exception
from xonsh.pyghooks import (XonshLexer, partial_color_tokenize,
                            xonsh_style_proxy, XonshTerminal256Formatter)
from xonsh.ptk.completer import PromptToolkitCompleter
from xonsh.ptk.history import PromptToolkitHistory
from xonsh.ptk.key_bindings import load_xonsh_bindings
from xonsh.ptk.shortcuts import Prompter
from xonsh.events import events


events.transmogrify('on_ptk_create', 'LoadEvent')
events.doc('on_ptk_create', """
on_ptk_create(prompter: Prompter, history: PromptToolkitHistory, completer: PromptToolkitCompleter, bindings: KeyBindingManager) ->

Fired after prompt toolkit has been initialized
""")


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
            }
        self.key_bindings_manager = KeyBindingManager(**key_bindings_manager_args)
        load_xonsh_bindings(self.key_bindings_manager)
        # This assumes that PromptToolkitShell is a singleton
        events.on_ptk_create.fire(self.prompter, self.history, self.pt_completer, self.key_bindings_manager)

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
        if not env.get('UPDATE_PROMPT_ON_KEYPRESS'):
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
                    'mouse_support': mouse_support,
                    'auto_suggest': auto_suggest,
                    'get_prompt_tokens': get_prompt_tokens,
                    'get_rprompt_tokens': get_rprompt_tokens,
                    'get_bottom_toolbar_tokens': get_bottom_toolbar_tokens,
                    'style': PygmentsStyle(xonsh_style_proxy(self.styler)),
                    'completer': completer,
                    'multiline': multiline,
                    'get_continuation_tokens': self.continuation_tokens,
                    'history': history,
                    'enable_history_search': enable_history_search,
                    'reserve_space_for_menu': 0,
                    'key_bindings_registry': self.key_bindings_manager.registry,
                    'display_completions_in_columns': multicolumn,
                    }
            if builtins.__xonsh_env__.get('COLOR_INPUT'):
                prompt_args['lexer'] = PygmentsLexer(XonshLexer)
            line = self.prompter.prompt(**prompt_args)
        return line

    def _push(self, line):
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
                    print('Use "exit" to leave the shell.', file=sys.stderr)
                else:
                    break

    def prompt_tokens(self, cli):
        """Returns a list of (token, str) tuples for the current prompt."""
        p = builtins.__xonsh_env__.get('PROMPT')
        try:
            p = self.prompt_formatter(p)
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
        p = builtins.__xonsh_env__.get('BOTTOM_TOOLBAR')
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
        dots = builtins.__xonsh_env__.get('MULTILINE_PROMPT')
        dots = dots() if callable(dots) else dots
        if dots is None:
            return [(Token, ' '*(width + 1))]
        basetoks = self.format_color(dots)
        baselen = sum(len(t[1]) for t in basetoks)
        if baselen == 0:
            return [(Token, ' '*(width + 1))]
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
                toks.append((tok[0], tok[1][:n-count]))
            count = newcount
            if n <= count:
                break
        toks.append((Token, ' '))  # final space
        return toks

    def format_color(self, string, hide=False, force_string=False, **kwargs):
        """Formats a color string using Pygments. This, therefore, returns
        a list of (Token, str) tuples. If force_string is set to true, though,
        this will return a color fomtatted string.
        """
        tokens = partial_color_tokenize(string)
        if force_string:
            env = builtins.__xonsh_env__
            self.styler.style_name = env.get('XONSH_COLOR_STYLE')
            proxy_style = xonsh_style_proxy(self.styler)
            formatter = XonshTerminal256Formatter(style=proxy_style)
            s = pygments.format(tokens, formatter)
            return s
        else:
            return tokens

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
