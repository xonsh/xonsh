# -*- coding: utf-8 -*-
"""The readline based xonsh shell.

Portions of this code related to initializing the readline library
are included from the IPython project.  The IPython project is:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (c) 2001-2007, Fernando Perez <fernando.perez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>

"""
import os
import sys
import cmd
import time
import select
import builtins
import importlib
import threading
import collections

from xonsh.lazyjson import LazyJSON
from xonsh.lazyasd import LazyObject
from xonsh.base_shell import BaseShell
from xonsh.ansi_colors import ansi_partial_color_format, ansi_color_style_names, ansi_color_style
from xonsh.prompt.base import partial_format_prompt, multiline_prompt
from xonsh.tools import print_exception, check_for_partial_string
from xonsh.platform import ON_WINDOWS, ON_CYGWIN, ON_DARWIN
from xonsh.lazyimps import pygments, pyghooks

terminal256 = LazyObject(
    lambda: importlib.import_module('pygments.formatters.terminal256'),
    globals(), 'terminal')

readline = None
RL_COMPLETION_SUPPRESS_APPEND = RL_LIB = RL_STATE = None
RL_CAN_RESIZE = False
RL_DONE = None
RL_VARIABLE_VALUE = None
_RL_STATE_DONE = 0x1000000
_RL_STATE_ISEARCH = 0x0000080

_RL_PREV_CASE_SENSITIVE_COMPLETIONS = 'to-be-set'


def setup_readline():
    """Sets up the readline module and completion suppression, if available."""
    global RL_COMPLETION_SUPPRESS_APPEND, RL_LIB, RL_CAN_RESIZE, RL_STATE, readline
    if RL_COMPLETION_SUPPRESS_APPEND is not None:
        return
    for _rlmod_name in ('gnureadline', 'readline'):
        try:
            readline = importlib.import_module(_rlmod_name)
            sys.modules['readline'] = readline
        except ImportError:
            pass
        else:
            break

    if readline is None:
        print("""Skipping setup. Because no `readline` implementation available.
            Please install a backend (`readline`, `prompt-toolkit`, etc) to use
            `xonsh` interactively.
            See https://github.com/xonsh/xonsh/issues/1170""")
        return

    import ctypes
    import ctypes.util
    uses_libedit = readline.__doc__ and 'libedit' in readline.__doc__
    readline.set_completer_delims(' \t\n')
    # Cygwin seems to hang indefinitely when querying the readline lib
    if (not ON_CYGWIN) and (not readline.__file__.endswith('.py')):
        RL_LIB = lib = ctypes.cdll.LoadLibrary(readline.__file__)
        try:
            RL_COMPLETION_SUPPRESS_APPEND = ctypes.c_int.in_dll(
                lib, 'rl_completion_suppress_append')
        except ValueError:
            # not all versions of readline have this symbol, ie Macs sometimes
            RL_COMPLETION_SUPPRESS_APPEND = None
        try:
            RL_STATE = ctypes.c_int.in_dll(lib, 'rl_readline_state')
        except Exception:
            pass
        RL_CAN_RESIZE = hasattr(lib, 'rl_reset_screen_size')
    env = builtins.__xonsh_env__
    # reads in history
    readline.set_history_length(-1)
    ReadlineHistoryAdder()
    # sets up IPython-like history matching with up and down
    readline.parse_and_bind('"\e[B": history-search-forward')
    readline.parse_and_bind('"\e[A": history-search-backward')
    # Setup Shift-Tab to indent
    readline.parse_and_bind('"\e[Z": "{0}"'.format(env.get('INDENT')))

    # handle tab completion differences found in libedit readline compatibility
    # as discussed at http://stackoverflow.com/a/7116997
    if uses_libedit and ON_DARWIN:
        readline.parse_and_bind("bind ^I rl_complete")
        print('\n'.join(['', "*" * 78,
                         "libedit detected - readline will not be well behaved, including but not limited to:",
                         "   * crashes on tab completion",
                         "   * incorrect history navigation",
                         "   * corrupting long-lines",
                         "   * failure to wrap or indent lines properly",
                         "",
                         "It is highly recommended that you install gnureadline, which is installable with:",
                         "     pip install gnureadline",
                         "*" * 78]), file=sys.stderr)
    else:
        readline.parse_and_bind("tab: complete")
    # try to load custom user settings
    inputrc_name = os.environ.get('INPUTRC')
    if inputrc_name is None:
        if uses_libedit:
            inputrc_name = '.editrc'
        else:
            inputrc_name = '.inputrc'
        inputrc_name = os.path.join(os.path.expanduser('~'), inputrc_name)
    if (not ON_WINDOWS) and (not os.path.isfile(inputrc_name)):
        inputrc_name = '/etc/inputrc'
    if os.path.isfile(inputrc_name):
        try:
            readline.read_init_file(inputrc_name)
        except Exception:
            # this seems to fail with libedit
            print_exception('xonsh: could not load readline default init file.')


def teardown_readline():
    """Tears down up the readline module, if available."""
    try:
        import readline
    except (ImportError, TypeError):
        return


def _rebind_case_sensitive_completions():
    # handle case sensitive, see Github issue #1342 for details
    global _RL_PREV_CASE_SENSITIVE_COMPLETIONS
    env = builtins.__xonsh_env__
    case_sensitive = env.get('CASE_SENSITIVE_COMPLETIONS')
    if case_sensitive is _RL_PREV_CASE_SENSITIVE_COMPLETIONS:
        return
    if case_sensitive:
        readline.parse_and_bind("set completion-ignore-case off")
    else:
        readline.parse_and_bind("set completion-ignore-case on")
    _RL_PREV_CASE_SENSITIVE_COMPLETIONS = case_sensitive


def fix_readline_state_after_ctrl_c():
    """
    Fix to allow Ctrl-C to exit reverse-i-search.

    Based on code from:
        http://bugs.python.org/file39467/raw_input__workaround_demo.py
    """
    if ON_WINDOWS:
        # hack to make pyreadline mimic the desired behavior
        try:
            _q = readline.rl.mode.process_keyevent_queue
            if len(_q) > 1:
                _q.pop()
        except Exception:
            pass
    if RL_STATE is None:
        return
    if RL_STATE.value & _RL_STATE_ISEARCH:
        RL_STATE.value &= ~_RL_STATE_ISEARCH
    if not RL_STATE.value & _RL_STATE_DONE:
        RL_STATE.value |= _RL_STATE_DONE


def rl_completion_suppress_append(val=1):
    """Sets the rl_completion_suppress_append varaiable, if possible.
    A value of 1 (default) means to suppress, a value of 0 means to enable.
    """
    if RL_COMPLETION_SUPPRESS_APPEND is None:
        return
    RL_COMPLETION_SUPPRESS_APPEND.value = val


def rl_variable_dumper(readable=True):
    """Dumps the currently set readline variables. If readable is True, then this
    output may be used in an inputrc file.
    """
    RL_LIB.rl_variable_dumper(int(readable))


def rl_variable_value(variable):
    """Returns the currently set value for a readline configuration variable."""
    global RL_VARIABLE_VALUE
    if RL_VARIABLE_VALUE is None:
        import ctypes
        RL_VARIABLE_VALUE = RL_LIB.rl_variable_value
        RL_VARIABLE_VALUE.restype = ctypes.c_char_p
    env = builtins.__xonsh_env__
    enc, errors = env.get('XONSH_ENCODING'), env.get('XONSH_ENCODING_ERRORS')
    if isinstance(variable, str):
        variable = variable.encode(encoding=enc, errors=errors)
    rtn = RL_VARIABLE_VALUE(variable)
    return rtn.decode(encoding=enc, errors=errors)


def _insert_text_func(s, readline):
    """Creates a function to insert text via readline."""

    def inserter():
        readline.insert_text(s)
        readline.redisplay()

    return inserter


DEDENT_TOKENS = LazyObject(lambda: frozenset(['raise', 'return', 'pass',
                                              'break', 'continue']),
                           globals(), 'DEDENT_TOKENS')


class ReadlineShell(BaseShell, cmd.Cmd):
    """The readline based xonsh shell."""

    def __init__(self, completekey='tab', stdin=None, stdout=None, **kwargs):
        super().__init__(completekey=completekey,
                         stdin=stdin,
                         stdout=stdout,
                         **kwargs)
        setup_readline()
        self._current_indent = ''
        self._current_prompt = ''
        self._force_hide = None
        self.cmdqueue = collections.deque()

    def __del__(self):
        teardown_readline()

    def singleline(self, store_in_history=True, **kwargs):
        """Reads a single line of input. The store_in_history kwarg
        flags whether the input should be stored in readline's in-memory
        history.
        """
        if not store_in_history:  # store current position to remove it later
            try:
                import readline
            except ImportError:
                store_in_history = True
            pos = readline.get_current_history_length() - 1
        rtn = input(self.prompt)
        if not store_in_history and pos >= 0:
            readline.remove_history_item(pos)
        return rtn

    def parseline(self, line):
        """Overridden to no-op."""
        return '', line, line

    def completedefault(self, text, line, begidx, endidx):
        """Implements tab-completion for text."""
        rl_completion_suppress_append()  # this needs to be called each time
        offset = 0
        _s, _e, _q = check_for_partial_string(line)
        if _s is not None and _e is None:
            # we are in a partial string; we should complete based
            # on this part now
            offset = begidx - _s
            begidx = _s
        elif _e == endidx:
            offset = begidx - _s
            begidx = _s
            endidx -= 1
        elif (_s is not None and
                _e is not None and
                not any(i == ' ' for i in line[_e:begidx])):
            line = line[:_e] + line[_e+1:]
            offset = begidx - _s
            begidx = _s
        if self.completer is None:
            x = []
        else:
            comps = self.completer.complete(text, line,
                                            begidx, endidx,
                                            ctx=self.ctx)
            x = [(i[offset:] if " " in i[:-1] else i)
                 for i in comps[0]]
        return x

    # tab complete on first index too
    completenames = completedefault

    def _load_remaining_input_into_queue(self):
        buf = b''
        while True:
            r, w, x = select.select([self.stdin], [], [], 1e-6)
            if len(r) == 0:
                break
            buf += os.read(self.stdin.fileno(), 1024)
        if len(buf) > 0:
            buf = buf.decode().replace('\r\n', '\n').replace('\r', '\n')
            self.cmdqueue.extend(buf.splitlines(keepends=True))

    def postcmd(self, stop, line):
        """Called just before execution of line. For readline, this handles the
        automatic indentation of code blocks.
        """
        try:
            import readline
        except ImportError:
            return stop
        if self.need_more_lines:
            if len(line.strip()) == 0:
                readline.set_pre_input_hook(None)
                self._current_indent = ''
            elif line.rstrip()[-1] == ':':
                ind = line[:len(line) - len(line.lstrip())]
                ind += builtins.__xonsh_env__.get('INDENT')
                readline.set_pre_input_hook(_insert_text_func(ind, readline))
                self._current_indent = ind
            elif line.split(maxsplit=1)[0] in DEDENT_TOKENS:
                env = builtins.__xonsh_env__
                ind = self._current_indent[:-len(env.get('INDENT'))]
                readline.set_pre_input_hook(_insert_text_func(ind, readline))
                self._current_indent = ind
            else:
                ind = line[:len(line) - len(line.lstrip())]
                if ind != self._current_indent:
                    insert_func = _insert_text_func(ind, readline)
                    readline.set_pre_input_hook(insert_func)
                    self._current_indent = ind
        else:
            readline.set_pre_input_hook(None)
        return stop

    def _cmdloop(self, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.

        This was forked from Lib/cmd.py from the Python standard library v3.4.3,
        (C) Python Software Foundation, 2015.
        """
        self.preloop()
        if self.use_rawinput and self.completekey:
            try:
                import readline
                self.old_completer = readline.get_completer()
                readline.set_completer(self.complete)
                readline.parse_and_bind(self.completekey + ": complete")
                have_readline = True
            except ImportError:
                have_readline = False
        try:
            if intro is not None:
                self.intro = intro
            if self.intro:
                self.stdout.write(str(self.intro) + "\n")
            stop = None
            while not stop:
                line = None
                exec_now = False
                if len(self.cmdqueue) > 0:
                    line = self.cmdqueue.popleft()
                    exec_now = line.endswith('\n')
                if self.use_rawinput and not exec_now:
                    inserter = None if line is None \
                        else _insert_text_func(line, readline)
                    if inserter is not None:
                        readline.set_pre_input_hook(inserter)
                    try:
                        line = self.singleline()
                    except EOFError:
                        if builtins.__xonsh_env__.get("IGNOREEOF"):
                            self.stdout.write('Use "exit" to leave the shell.'
                                              '\n')
                            line = ''
                        else:
                            line = 'EOF'
                    if inserter is not None:
                        readline.set_pre_input_hook(None)
                else:
                    self.print_color(self.prompt, file=self.stdout)
                    if line is not None:
                        os.write(self.stdin.fileno(), line.encode())
                    if not exec_now:
                        line = self.stdin.readline()
                    if len(line) == 0:
                        line = 'EOF'
                    else:
                        line = line.rstrip('\r\n')
                    if have_readline and line != 'EOF':
                        readline.add_history(line)
                if not ON_WINDOWS:
                    # select() is not fully functional on windows
                    self._load_remaining_input_into_queue()
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            self.postloop()
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    import readline
                    readline.set_completer(self.old_completer)
                except ImportError:
                    pass

    def cmdloop(self, intro=None):
        while not builtins.__xonsh_exit__:
            try:
                self._cmdloop(intro=intro)
            except KeyboardInterrupt:
                print()  # Gives a newline
                fix_readline_state_after_ctrl_c()
                self.reset_buffer()
                intro = None

    @property
    def prompt(self):
        """Obtains the current prompt string."""
        global RL_LIB, RL_CAN_RESIZE
        if RL_CAN_RESIZE:
            # This is needed to support some system where line-wrapping doesn't
            # work. This is a bug in upstream Python, or possibly readline.
            RL_LIB.rl_reset_screen_size()
        if self.need_more_lines:
            if self.mlprompt is None:
                try:
                    self.mlprompt = multiline_prompt(curr=self._current_prompt)
                except Exception:  # pylint: disable=broad-except
                    print_exception()
                    self.mlprompt = '<multiline prompt error> '
            return self.mlprompt
        env = builtins.__xonsh_env__  # pylint: disable=no-member
        p = env.get('PROMPT')
        try:
            p = partial_format_prompt(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        hide = True if self._force_hide is None else self._force_hide
        p = ansi_partial_color_format(p, style=env.get('XONSH_COLOR_STYLE'),
                                      hide=hide)
        self._current_prompt = p
        self.settitle()
        return p

    def format_color(self, string, hide=False, **kwargs):
        """Readline implementation of color formatting. This usesg ANSI color
        codes.
        """
        hide = hide if self._force_hide is None else self._force_hide
        return ansi_partial_color_format(string, hide=hide,
                                         style=builtins.__xonsh_env__.get('XONSH_COLOR_STYLE'))

    def print_color(self, string, hide=False, **kwargs):
        if isinstance(string, str):
            s = self.format_color(string, hide=hide)
        else:
            # assume this is a list of (Token, str) tuples and format it
            env = builtins.__xonsh_env__
            self.styler.style_name = env.get('XONSH_COLOR_STYLE')
            style_proxy = pyghooks.xonsh_style_proxy(self.styler)
            formatter = terminal256.Terminal256Formatter(style=style_proxy)
            s = pygments.format(string, formatter).rstrip()
        print(s, **kwargs)

    def color_style_names(self):
        """Returns an iterable of all available style names."""
        return ansi_color_style_names()

    def color_style(self):
        """Returns the current color map."""
        style = style = builtins.__xonsh_env__.get('XONSH_COLOR_STYLE')
        return ansi_color_style(style=style)


class ReadlineHistoryAdder(threading.Thread):
    def __init__(self, wait_for_gc=True, *args, **kwargs):
        """Thread responsible for adding inputs from history to the current readline
        instance. May wait for the history garbage collector to finish.
        """
        super(ReadlineHistoryAdder, self).__init__(*args, **kwargs)
        self.daemon = True
        self.wait_for_gc = wait_for_gc
        self.start()

    def run(self):
        try:
            import readline
        except ImportError:
            return
        hist = builtins.__xonsh_history__
        while self.wait_for_gc and hist.gc.is_alive():
            time.sleep(0.011)  # gc sleeps for 0.01 secs, sleep a beat longer
        files = hist.gc.files()
        i = 1
        for _, _, f in files:
            try:
                lj = LazyJSON(f, reopen=False)
                for command in lj['cmds']:
                    inp = command['inp'].splitlines()
                    for line in inp:
                        if line == 'EOF':
                            continue
                        readline.add_history(line)
                        if RL_LIB is not None:
                            RL_LIB.history_set_pos(i)
                        i += 1
                lj.close()
            except (IOError, OSError, ValueError):
                continue
