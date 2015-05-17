"""The prompt_toolkit based xonsh shell"""
import os
import builtins
from warnings import warn

from prompt_toolkit.shortcuts import create_cli, create_eventloop
from pygments.token import Token

from xonsh.base_shell import BaseShell
from xonsh.history import LimitedFileHistory
from xonsh.pyghooks import XonshLexer
from xonsh.tools import format_prompt_for_prompt_toolkit
from xonsh.prompt_toolkit_completer import PromptToolkitCompleter


def setup_history():
    """Creates history object."""
    env = builtins.__xonsh_env__
    hfile = env.get('XONSH_HISTORY_FILE',
                    os.path.expanduser('~/.xonsh_history'))
    history = LimitedFileHistory()
    try:
        history.read_history_file(hfile)
    except PermissionError:
        warn('do not have read permissions for ' + hfile, RuntimeWarning)
    return history


def teardown_history(history):
    """Tears down the history object."""
    env = builtins.__xonsh_env__
    hsize = env.get('XONSH_HISTORY_SIZE', 8128)
    hfile = env.get('XONSH_HISTORY_FILE',
                    os.path.expanduser('~/.xonsh_history'))
    try:
        history.save_history_to_file(hfile, hsize)
    except PermissionError:
        warn('do not have write permissions for ' + hfile, RuntimeWarning)

def get_user_input(get_prompt_tokens,
                   history=None,
                   lexer=None,
                   completer=None):
    """Customized function that mostly mimics promp_toolkit's get_input.

    Main difference between this and prompt_toolkit's get_input() is that it
    allows to pass get_tokens() function instead of text prompt.
    """
    eventloop = create_eventloop()

    cli = create_cli(
        eventloop,
        lexer=lexer,
        completer=completer,
        history=history,
        get_prompt_tokens=get_prompt_tokens)

    try:
        document = cli.read_input()

        if document:
            return document.text
    finally:
        eventloop.close()


class PromptToolkitShell(BaseShell):
    """The xonsh shell."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = setup_history()
        self.pt_completer = PromptToolkitCompleter(self.completer, self.ctx)

    def __del__(self):
        if self.history is not None:
            teardown_history(self.history)

    def cmdloop(self, intro=None):
        """Enters a loop that reads and execute input from user."""
        if intro:
            print(intro)
        while not builtins.__xonsh_exit__:
            try:
                line = get_user_input(
                    get_prompt_tokens=self._get_prompt_tokens(),
                    completer=self.pt_completer,
                    history=self.history,
                    lexer=self.lexer)
                if not line:
                    self.emptyline()
                else:
                    line = self.precmd(line)
                    self.default(line)
            except KeyboardInterrupt:
                self.reset_buffer()
            except EOFError:
                break

    def _get_prompt_tokens(self):
        """Returns function to pass as prompt to prompt_toolkit."""
        def get_tokens(cli):
            return [(Token.Prompt,
                     format_prompt_for_prompt_toolkit(self.prompt))]
        return get_tokens

    @property
    def lexer(self):
        """Obtains the current lexer."""
        env = builtins.__xonsh_env__
        return env['HIGHLIGHTING_LEXER']
