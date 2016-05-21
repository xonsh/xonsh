"""A prompt-toolkit inspired shortcut collection."""
import builtins
import textwrap

from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.utils import DummyContext
from prompt_toolkit.shortcuts import (create_prompt_application,
    create_eventloop, create_asyncio_eventloop, create_output)

from xonsh.platform import ptk_version_info


class Prompter(object):

    def __init__(self, cli=None, *args, **kwargs):
        """Implements a prompt that statefully holds a command-line
        interface.  When used as a context manager, it will return itself
        on entry and reset itself on exit.

        Parameters
        ----------
        cli : CommandLineInterface or None, optional
            If this is not a CommandLineInterface object, such an object
            will be created when the prompt() method is called.
        """
        self.cli = cli
        self.major_minor = ptk_version_info()[:2]

    def __enter__(self):
        self.reset()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        #self.reset()
        pass

    def prompt(self, message='', **kwargs):
        """Get input from the user and return it.

        This is a wrapper around a lot of prompt_toolkit functionality and
        can be a replacement for raw_input. (or GNU readline.) If you want
        to keep your history across several calls, create one
        `~prompt_toolkit.history.History instance and pass it every
        time. This function accepts many keyword arguments. Except for the
        following. they are a proxy to the arguments of
        create_prompt_application().

        Parameters
        ----------
        patch_stdout : file-like, optional
            Replace ``sys.stdout`` by a proxy that ensures that print
            statements from other threads won't destroy the prompt. (They
            will be printed above the prompt instead.)
        return_asyncio_coroutine : bool, optional
            When True, return a asyncio coroutine. (Python >3.3)

        Notes
        -----
        This method was forked from the mainline prompt-toolkit repo.
        Copyright (c) 2014, Jonathan Slenders, All rights reserved.
        """
        patch_stdout = kwargs.pop('patch_stdout', False)
        return_asyncio_coroutine = kwargs.pop('return_asyncio_coroutine', False)
        if return_asyncio_coroutine:
            eventloop = create_asyncio_eventloop()
        else:
            eventloop = kwargs.pop('eventloop', None) or create_eventloop()

        # Create CommandLineInterface.
        if self.cli is None:
            if self.major_minor < (0, 57):
                kwargs.pop('reserve_space_for_menu', None)
            if self.major_minor <= (0, 57):
                kwargs.pop('get_rprompt_tokens', None)
                kwargs.pop('get_continuation_tokens', None)
            # VI_Mode handling changed in prompt_toolkit v1.0
            if self.major_minor >= (1, 0):
                from prompt_toolkit.enums import EditingMode
                if builtins.__xonsh_env__.get('VI_MODE'):
                    editing_mode = EditingMode.VI
                else:
                    editing_mode = EditingMode.EMACS
                kwargs['editing_mode'] = editing_mode
                kwargs['vi_mode'] = builtins.__xonsh_env__.get('VI_MODE')
            cli = CommandLineInterface(
                application=create_prompt_application(message, **kwargs),
                eventloop=eventloop,
                output=create_output())
            self.cli = cli
        else:
            cli = self.cli

        # Replace stdout.
        patch_context = cli.patch_stdout_context() if patch_stdout else DummyContext()

        # Read input and return it.
        if return_asyncio_coroutine:
            # Create an asyncio coroutine and call it.
            exec_context = {'patch_context': patch_context, 'cli': cli}
            exec(textwrap.dedent('''
            import asyncio
            @asyncio.coroutine
            def prompt_coro():
                with patch_context:
                    document = yield from cli.run_async(reset_current_buffer=False)
                    if document:
                        return document.text
            '''), exec_context)
            return exec_context['prompt_coro']()
        else:
            # Note: We pass `reset_current_buffer=False`, because that way
            # it's easy to give DEFAULT_BUFFER a default value, without it
            # getting erased. We don't have to reset anyway, because this is
            # the first and only time that this CommandLineInterface will run.
            try:
                with patch_context:
                    document = cli.run(reset_current_buffer=False)

                    if document:
                        return document.text
            finally:
                eventloop.close()

    def reset(self):
        """Resets the prompt and cli to a pristine state on this object."""
        self.cli = None


try:
    from prompt_toolkit.shortcuts import print_tokens
except ImportError:
    import os
    import sys
    from prompt_toolkit.renderer import print_tokens as renderer_print_tokens
    from prompt_toolkit.filters import to_simple_filter
    from prompt_toolkit.utils import is_conemu_ansi, is_windows
    if is_windows():
        from prompt_toolkit.terminal.win32_output import Win32Output
        from prompt_toolkit.terminal.conemu_output import ConEmuOutput
    else:
        from prompt_toolkit.terminal.vt100_output import Vt100_Output
    from pygments.style import Style
    from prompt_toolkit.styles import Style
    from six import PY2

    def create_output(stdout=None, true_color=False):
        """
        Return an :class:`~prompt_toolkit.output.Output` instance for the command
        line.
        :param true_color: When True, use 24bit colors instead of 256 colors.
            (`bool` or :class:`~prompt_toolkit.filters.SimpleFilter`.)

        Notes
        -----
        This method was forked from the mainline prompt-toolkit repo.
        Copyright (c) 2014, Jonathan Slenders, All rights reserved.
        This is deprecated and slated for removal after a prompt-toolkit
        v0.57+ release.
        """
        stdout = stdout or sys.__stdout__
        true_color = to_simple_filter(true_color)

        if is_windows():
            if is_conemu_ansi():
                return ConEmuOutput(stdout)
            else:
                return Win32Output(stdout)
        else:
            term = os.environ.get('TERM', '')
            if PY2:
                term = term.decode('utf-8')

            return Vt100_Output.from_pty(stdout, true_color=true_color)#, term=term)

    def print_tokens(tokens, style=None, true_color=False):
        """
        Print a list of (Token, text) tuples in the given style to the output.
        E.g.::
            style = PygmentsStyle.from_defaults(style_dict={
                Token.Hello: '#ff0066',
                Token.World: '#884444 italic',
            })
            tokens = [
                (Token.Hello, 'Hello'),
                (Token.World, 'World'),
            ]
            print_tokens(tokens, style=style)
        :param tokens: List of ``(Token, text)`` tuples.
        :param style: :class:`.Style` instance for the color scheme.
        :param true_color: When True, use 24bit colors instead of 256 colors.

        Notes
        -----
        This method was forked from the mainline prompt-toolkit repo.
        Copyright (c) 2014, Jonathan Slenders, All rights reserved.
        This is deprecated and slated for removal after a prompt-toolkit
        v0.57+ release.
        """
        assert isinstance(style, Style)
        output = create_output(true_color=true_color)
        renderer_print_tokens(output, tokens, style)
