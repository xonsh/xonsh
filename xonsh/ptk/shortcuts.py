"""A prompt-toolkit inspired shortcut collection."""

import pygments.lexer
from pygments.token import Token

from prompt_toolkit.buffer import Buffer, AcceptAction
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER
from prompt_toolkit.filters import IsDone, HasFocus, RendererHeightIsKnown, to_simple_filter, to_cli_filter, Condition
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.interface import CommandLineInterface, Application, AbortAction
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.layout import Window, HSplit, VSplit, FloatContainer, Float
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.layout.controls import BufferControl, TokenListControl
from prompt_toolkit.layout.dimension import LayoutDimension
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.layout.menus import CompletionsMenu, MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import PasswordProcessor, ConditionalProcessor, AppendAutoSuggestion
from prompt_toolkit.layout.prompt import DefaultPrompt
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.styles import PygmentsStyle
from prompt_toolkit.layout.toolbars import ValidationToolbar, SystemToolbar, ArgToolbar, SearchToolbar
from prompt_toolkit.layout.utils import explode_tokens
from prompt_toolkit.utils import is_conemu_ansi, is_windows, DummyContext
from prompt_toolkit.shortcuts import (create_prompt_application, 
    create_eventloop, create_asyncio_eventloop, create_output, 
    _split_multiline_prompt)

try:
    from prompt_toolkit.styles import DEFAULT_STYLE
except ImportError:
    DEFAULT_STYLE = None

try:
    from prompt_toolkit.layout.highlighters import (SearchHighlighter, 
        SelectionHighlighter, ConditionalHighlighter)
except ImportError:
    SearchHighlighter = SelectionHighlighter = ConditionalHighlighter = None


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

        kwargs['reserve_space_for_menu'] = 0
        # Create CommandLineInterface.
        if self.cli is None:
            cli = CommandLineInterface(
                application=self.create_prompt_application(message, **kwargs),
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
            exec_(textwrap.dedent('''
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

    def create_prompt_layout(self, message='', lexer=None, is_password=False,
        reserve_space_for_menu=8, get_prompt_tokens=None, 
        get_bottom_toolbar_tokens=None, display_completions_in_columns=False,
        extra_input_processors=None, multiline=False, wrap_lines=True):
        """
        Create a :class:`.Container` instance for a prompt.
        :param message: Text to be used as prompt.
        :param lexer: :class:`~prompt_toolkit.layout.lexers.Lexer` to be used for
            the highlighting.
        :param is_password: `bool` or :class:`~prompt_toolkit.filters.CLIFilter`.
            When True, display input as '*'.
        :param reserve_space_for_menu: Space to be reserved for the menu. When >0,
            make sure that a minimal height is allocated in the terminal, in order
            to display the completion menu.
        :param get_prompt_tokens: An optional callable that returns the tokens to be
            shown in the menu. (To be used instead of a `message`.)
        :param get_bottom_toolbar_tokens: An optional callable that returns the
            tokens for a toolbar at the bottom.
        :param display_completions_in_columns: `bool` or
            :class:`~prompt_toolkit.filters.CLIFilter`. Display the completions in
            multiple columns.
        :param multiline: `bool` or :class:`~prompt_toolkit.filters.CLIFilter`.
            When True, prefer a layout that is more adapted for multiline input.
            Text after newlines is automatically indented, and search/arg input is
            shown below the input, instead of replacing the prompt.
        :param wrap_lines: `bool` or :class:`~prompt_toolkit.filters.CLIFilter`.
            When True (the default), automatically wrap long lines instead of
            scrolling horizontally.
        """
        assert isinstance(message, str)
        assert get_bottom_toolbar_tokens is None or callable(get_bottom_toolbar_tokens)
        assert get_prompt_tokens is None or callable(get_prompt_tokens)
        assert not (message and get_prompt_tokens)

        display_completions_in_columns = to_cli_filter(display_completions_in_columns)
        multiline = to_cli_filter(multiline)

        if get_prompt_tokens is None:
            get_prompt_tokens = lambda _: [(Token.Prompt, message)]

        get_prompt_tokens_1, get_prompt_tokens_2 = _split_multiline_prompt(get_prompt_tokens)

        # `lexer` is supposed to be a `Lexer` instance. But if a Pygments lexer
        # class is given, turn it into a PygmentsLexer. (Important for
        # backwards-compatibility.)
        try:
            if issubclass(lexer, pygments.lexer.Lexer):
                lexer = PygmentsLexer(lexer)
        except TypeError: # Happens when lexer is `None` or an instance of something else.
            pass

        # Create highlighters and processors list.
        if ConditionalHighlighter is None:
            highlighters = None
            highlighters_kwargs = {}
        else:
            highlighters = [
                ConditionalHighlighter(
                    # By default, only highlight search when the search
                    # input has the focus. (Note that this doesn't mean
                    # there is no search: the Vi 'n' binding for instance
                    # still allows to jump to the next match in
                    # navigation mode.)
                    SearchHighlighter(preview_search=True),
                HasFocus(SEARCH_BUFFER)),
                SelectionHighlighter()]
            highlighters_kwargs = {'highlighters': highlighters}

        input_processors = [
            ConditionalProcessor(AppendAutoSuggestion(), HasFocus(DEFAULT_BUFFER) & ~IsDone()),
            ConditionalProcessor(PasswordProcessor(), is_password)]

        if extra_input_processors:
            input_processors.extend(extra_input_processors)

        # Show the prompt before the input (using the DefaultPrompt processor.
        # This also replaces it with reverse-i-search and 'arg' when required.
        # (Only for single line mode.)
        # (DefaultPrompt should always be at the end of the processors.)
        input_processors.append(ConditionalProcessor(
            DefaultPrompt(get_prompt_tokens), ~multiline))

        # Create bottom toolbar.
        if get_bottom_toolbar_tokens:
            toolbars = [ConditionalContainer(
                Window(TokenListControl(get_bottom_toolbar_tokens,
                                        default_char=Char(' ', Token.Toolbar)),
                                        height=LayoutDimension.exact(1)),
                filter=~IsDone() & RendererHeightIsKnown())]
        else:
            toolbars = []

        def get_height(cli):
            # If there is an autocompletion menu to be shown, make sure that our
            # layout has at least a minimal height in order to display it.
            if reserve_space_for_menu and not cli.is_done:
                return LayoutDimension(min=reserve_space_for_menu)
            else:
                return LayoutDimension()

        # Create and return Container instance.
        return HSplit([
            ConditionalContainer(
                Window(
                    TokenListControl(get_prompt_tokens_1),
                    dont_extend_height=True),
                filter=multiline,
            ),
            VSplit([
                # In multiline mode, the prompt is displayed in a left pane.
                ConditionalContainer(
                    Window(
                        TokenListControl(get_prompt_tokens_2),
                        dont_extend_width=True,
                    ),
                    filter=multiline,
                ),
                # The main input, with completion menus floating on top of it.
                FloatContainer(
                    Window(
                        BufferControl(
                            input_processors=input_processors,
                            lexer=lexer,
                            wrap_lines=wrap_lines,
                            # Enable preview_search, we want to have immediate feedback
                            # in reverse-i-search mode.
                            preview_search=True, 
                            **highlighters_kwargs),
                        get_height=get_height,
                    ),
                    [
                        Float(xcursor=True,
                              ycursor=True,
                              content=CompletionsMenu(
                                  max_height=16,
                                  scroll_offset=1,
                                  extra_filter=HasFocus(DEFAULT_BUFFER) &
                                               ~display_completions_in_columns)),
                        Float(xcursor=True,
                              ycursor=True,
                              content=MultiColumnCompletionsMenu(
                                  extra_filter=HasFocus(DEFAULT_BUFFER) &
                                               display_completions_in_columns,
                                  show_meta=True))
                    ]
                ),
            ]),
            ValidationToolbar(),
            SystemToolbar(),

            # In multiline mode, we use two toolbars for 'arg' and 'search'.
            ConditionalContainer(ArgToolbar(), multiline),
            ConditionalContainer(SearchToolbar(), multiline),
        ] + toolbars)


    def create_prompt_application(self,
        message='',
        multiline=False,
        wrap_lines=True,
        is_password=False,
        vi_mode=False,
        complete_while_typing=True,
        enable_history_search=False,
        lexer=None,
        enable_system_bindings=False,
        enable_open_in_editor=False,
        validator=None,
        completer=None,
        reserve_space_for_menu=8,
        auto_suggest=None,
        style=None,
        history=None,
        clipboard=None,
        get_prompt_tokens=None,
        get_bottom_toolbar_tokens=None,
        display_completions_in_columns=False,
        get_title=None,
        mouse_support=False,
        extra_input_processors=None,
        key_bindings_registry=None,
        on_abort=AbortAction.RAISE_EXCEPTION,
        on_exit=AbortAction.RAISE_EXCEPTION,
        accept_action=AcceptAction.RETURN_DOCUMENT,
        default=''):
        """
        Create an :class:`~Application` instance for a prompt.
        (It is meant to cover 90% of the prompt use cases, where no extreme
        customization is required. For more complex input, it is required to create
        a custom :class:`~Application` instance.)
        :param message: Text to be shown before the prompt.
        :param mulitiline: Allow multiline input. Pressing enter will insert a
                           newline. (This requires Meta+Enter to accept the input.)
        :param wrap_lines: `bool` or :class:`~prompt_toolkit.filters.CLIFilter`.
            When True (the default), automatically wrap long lines instead of
            scrolling horizontally.
        :param is_password: Show asterisks instead of the actual typed characters.
        :param vi_mode: `bool` or :class:`~prompt_toolkit.filters.CLIFilter`. If
            True, use Vi key bindings.
        :param complete_while_typing: `bool` or
            :class:`~prompt_toolkit.filters.CLIFilter`. Enable autocompletion while
            typing.
        :param enable_history_search: `bool` or
            :class:`~prompt_toolkit.filters.CLIFilter`. Enable up-arrow parting
            string matching.
        :param lexer: :class:`~prompt_toolkit.layout.lexers.Lexer` to be used for
            the syntax highlighting.
        :param validator: :class:`~prompt_toolkit.validation.Validator` instance
            for input validation.
        :param completer: :class:`~prompt_toolkit.completion.Completer` instance
            for input completion.
        :param reserve_space_for_menu: Space to be reserved for displaying the menu.
            (0 means that no space needs to be reserved.)
        :param auto_suggest: :class:`~prompt_toolkit.auto_suggest.AutoSuggest`
            instance for input suggestions.
        :param style: Pygments style class for the color scheme.
        :param enable_system_bindings: `bool` or
            :class:`~prompt_toolkit.filters.CLIFilter`. Pressing Meta+'!' will show
            a system prompt.
        :param enable_open_in_editor: `bool` or
            :class:`~prompt_toolkit.filters.CLIFilter`. Pressing 'v' in Vi mode or
            C-X C-E in emacs mode will open an external editor.
        :param history: :class:`~prompt_toolkit.history.History` instance.
        :param clipboard: :class:`~prompt_toolkit.clipboard.base.Clipboard` instance.
            (e.g. :class:`~prompt_toolkit.clipboard.in_memory.InMemoryClipboard`)
        :param get_bottom_toolbar_tokens: Optional callable which takes a
            :class:`~prompt_toolkit.interface.CommandLineInterface` and returns a
            list of tokens for the bottom toolbar.
        :param display_completions_in_columns: `bool` or
            :class:`~prompt_toolkit.filters.CLIFilter`. Display the completions in
            multiple columns.
        :param get_title: Callable that returns the title to be displayed in the
            terminal.
        :param mouse_support: `bool` or :class:`~prompt_toolkit.filters.CLIFilter`
            to enable mouse support.
        :param default: The default text to be shown in the input buffer. (This can
            be edited by the user.)
        """
        if key_bindings_registry is None:
            key_bindings_registry = KeyBindingManager.for_prompt(
                enable_vi_mode=vi_mode,
                enable_system_bindings=enable_system_bindings,
                enable_open_in_editor=enable_open_in_editor).registry

        # Make sure that complete_while_typing is disabled when enable_history_search
        # is enabled. (First convert to SimpleFilter, to avoid doing bitwise operations
        # on bool objects.)
        complete_while_typing = to_simple_filter(complete_while_typing)
        enable_history_search = to_simple_filter(enable_history_search)
        multiline = to_simple_filter(multiline)

        complete_while_typing = complete_while_typing & ~enable_history_search

        # Accept Pygments styles as well for backwards compatibility.
        try:
            if issubclass(style, pygments.style.Style):
                style = PygmentsStyle(style)
        except TypeError: # Happens when style is `None` or an instance of something else.
            pass

        # Create application
        return Application(
            layout=self.create_prompt_layout(
                message=message,
                lexer=lexer,
                is_password=is_password,
                reserve_space_for_menu=(reserve_space_for_menu if completer is not None else 0),
                multiline=Condition(lambda cli: multiline()),
                get_prompt_tokens=get_prompt_tokens,
                get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                display_completions_in_columns=display_completions_in_columns,
                extra_input_processors=extra_input_processors,
                wrap_lines=wrap_lines),
            buffer=Buffer(
                enable_history_search=enable_history_search,
                complete_while_typing=complete_while_typing,
                is_multiline=multiline,
                history=(history or InMemoryHistory()),
                validator=validator,
                completer=completer,
                auto_suggest=auto_suggest,
                accept_action=accept_action,
                initial_document=Document(default),
            ),
            style=style or DEFAULT_STYLE,
            clipboard=clipboard,
            key_bindings_registry=key_bindings_registry,
            get_title=get_title,
            mouse_support=mouse_support,
            on_abort=on_abort,
            on_exit=on_exit)
