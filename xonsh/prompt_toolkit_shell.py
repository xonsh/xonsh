# -*- coding: utf-8 -*-
"""The prompt_toolkit based xonsh shell."""
import builtins
from warnings import warn

from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.filters import Condition
from pygments.style import Style
from pygments.styles.default import DefaultStyle
from pygments.token import (Keyword, Name, Comment, String, Error, Number,
                            Operator, Generic, Whitespace, Token)

from xonsh.base_shell import BaseShell
from xonsh.tools import format_prompt_for_prompt_toolkit, _make_style
from xonsh.prompt_toolkit_completer import PromptToolkitCompleter
from xonsh.prompt_toolkit_history import PromptToolkitHistory
from xonsh.prompt_toolkit_key_bindings import load_xonsh_bindings
from xonsh.pyghooks import XonshLexer



class PromptToolkitShell(BaseShell):
    """The xonsh shell."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = PromptToolkitHistory()
        self.pt_completer = PromptToolkitCompleter(self.completer, self.ctx)
        self.key_bindings_manager = KeyBindingManager(
            enable_auto_suggest_bindings=True,
            enable_search=True,
            enable_abort_and_exit_bindings=True,
            enable_vi_mode=Condition(lambda cli: builtins.__xonsh_env__.get('VI_MODE')),
            enable_open_in_editor=True)
        load_xonsh_bindings(self.key_bindings_manager)

    def cmdloop(self, intro=None):
        """Enters a loop that reads and execute input from user."""
        if intro:
            print(intro)
        _auto_suggest = AutoSuggestFromHistory()
        while not builtins.__xonsh_exit__:
            try:
                token_func, style_cls = self._get_prompt_tokens_and_style()
                mouse_support = builtins.__xonsh_env__.get('MOUSE_SUPPORT')
                if builtins.__xonsh_env__.get('AUTO_SUGGEST'):
                    auto_suggest = _auto_suggest
                else:
                    auto_suggest = None
                completions_display = builtins.__xonsh_env__.get('COMPLETIONS_DISPLAY')
                multicolumn = (completions_display == 'multi')
                completer = None if completions_display == 'none' else self.pt_completer
                line = prompt(
                    mouse_support=mouse_support,
                    auto_suggest=auto_suggest,
                    get_prompt_tokens=token_func,
                    style=style_cls,
                    completer=completer,
                    lexer=PygmentsLexer(XonshLexer),
                    history=self.history,
                    enable_history_search=True,
                    key_bindings_registry=self.key_bindings_manager.registry,
                    display_completions_in_columns=multicolumn)
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

    def _get_prompt_tokens_and_style(self):
        """Returns function to pass as prompt to prompt_toolkit."""
        token_names, cstyles, strings = format_prompt_for_prompt_toolkit(self.prompt)
        tokens = [getattr(Token, n) for n in token_names]

        def get_tokens(cli):
            return list(zip(tokens, strings))

        custom_style = _xonsh_style(tokens, cstyles)

        return get_tokens, custom_style


def _xonsh_style(tokens=tuple(), cstyles=tuple()):
    class XonshStyle(Style):
        styles = {
            Whitespace: "GRAY",
            Comment: "UNDERLINE INTENSE GRAY",
            Comment.Preproc: "UNDERLINE INTENSE GRAY",
            Keyword: "BOLD GREEN",
            Keyword.Pseudo: "GREEN",
            Keyword.Type: "MAGENTA",
            Operator: "GRAY",
            Operator.Word: "BOLD",
            Name.Builtin: "INTENSE GREEN",
            Name.Function: "BLUE",
            Name.Class: "BOLD BLUE",
            Name.Namespace: "BOLD BLUE",
            Name.Exception: "BOLD INTENSE RED",
            Name.Variable: "CYAN",
            Name.Constant: "RED",
            Name.Label: "YELLOW",
            Name.Entity: "BOLD WHITE",
            Name.Attribute: "CYAN",
            Name.Tag: "BOLD GREEN",
            Name.Decorator: "CYAN",
            String: "MAGENTA",
            String.Doc: "UNDERLINE MAGENTA",
            String.Interpol: "BOLD MAGENTA",
            String.Escape: "BOLD RED",
            String.Regex: "MAGENTA",
            String.Symbol: "BOLD GREEN",
            String.Other: "GREEN",
            Number: "RED",
            Generic.Heading: "BOLD BLUE",
            Generic.Subheading: "BOLD MAGENTA",
            Generic.Deleted: "RED",
            Generic.Inserted: "GREEN",
            Generic.Error: "BOLD RED",
            Generic.Emph: "UNDERLINE",
            Generic.Prompt: "BOLD BLUE",
            Generic.Output: "GRAY",
            Generic.Traceback: "RED",
            Error: "RED",
        }
        styles = {k: _make_style(v) for k, v in styles.items()}
        styles.update({
            Token.Menu.Completions.Completion.Current: 'bg:#00aaaa #000000',
            Token.Menu.Completions.Completion: 'bg:#008888 #ffffff',
            Token.Menu.Completions.ProgressButton: 'bg:#003333',
            Token.Menu.Completions.ProgressBar: 'bg:#00aaaa',
            Token.AutoSuggestion: '#666666',
            Token.Aborted: '#888888',
        })
        # update with the prompt styles
        styles.update({t: s for (t, s) in zip(tokens, cstyles)})
        # Update with with any user styles
        userstyle = builtins.__xonsh_env__.get('PROMPT_TOOLKIT_STYLES')
        if userstyle is not None:
            styles.update(userstyle)
    return XonshStyle
