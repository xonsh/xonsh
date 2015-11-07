"""The readline based xonsh shell"""
import os
import sys
import time
import select
import builtins
from cmd import Cmd
from warnings import warn
from threading import Thread, Lock
from collections import deque

from xonsh import lazyjson
from xonsh.base_shell import BaseShell
from xonsh.tools import ON_WINDOWS

RL_COMPLETION_SUPPRESS_APPEND = RL_LIB = None
RL_CAN_RESIZE = False
RL_DONE = None


def setup_readline():
    """Sets up the readline module and completion supression, if available."""
    global RL_COMPLETION_SUPPRESS_APPEND, RL_LIB, RL_CAN_RESIZE
    if RL_COMPLETION_SUPPRESS_APPEND is not None:
        return
    try:
        import readline
    except ImportError:
        return
    import ctypes
    import ctypes.util
    readline.set_completer_delims(' \t\n')
    if not readline.__file__.endswith('.py'):
        RL_LIB = lib = ctypes.cdll.LoadLibrary(readline.__file__)
        try:
            RL_COMPLETION_SUPPRESS_APPEND = ctypes.c_int.in_dll(
                lib, 'rl_completion_suppress_append')
        except ValueError:
            # not all versions of readline have this symbol, ie Macs sometimes
            RL_COMPLETION_SUPPRESS_APPEND = None
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
    if readline.__doc__ and 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")


def teardown_readline():
    """Tears down up the readline module, if available."""
    try:
        import readline
    except (ImportError, TypeError):
        return


def rl_completion_suppress_append(val=1):
    """Sets the rl_completion_suppress_append varaiable, if possible.
    A value of 1 (default) means to suppress, a value of 0 means to enable.
    """
    if RL_COMPLETION_SUPPRESS_APPEND is None:
        return
    RL_COMPLETION_SUPPRESS_APPEND.value = val


def _insert_text_func(s, readline):
    """Creates a function to insert text via readline."""
    def inserter():
        readline.insert_text(s)
        readline.redisplay()
    return inserter


DEDENT_TOKENS = frozenset(['raise', 'return', 'pass', 'break', 'continue'])


class ReadlineShell(BaseShell, Cmd):
    """The readline based xonsh shell."""

    def __init__(self, completekey='tab', stdin=None, stdout=None, **kwargs):
        super().__init__(completekey=completekey,
                         stdin=stdin,
                         stdout=stdout,
                         **kwargs)
        setup_readline()
        self._current_indent = ''
        self.cmdqueue = deque()

    def __del__(self):
        teardown_readline()

    def parseline(self, line):
        """Overridden to no-op."""
        return '', line, line

    def completedefault(self, text, line, begidx, endidx):
        """Implements tab-completion for text."""
        rl_completion_suppress_append()  # this needs to be called each time
        return self.completer.complete(text, line,
                                       begidx, endidx,
                                       ctx=self.ctx)

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
                self.stdout.write(str(self.intro)+"\n")
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
                        line = input(self.prompt)
                    except EOFError:
                        line = 'EOF'
                    if inserter is not None:
                        readline.set_pre_input_hook(None)
                else:
                    self.stdout.write(self.prompt.replace('\001', '')
                                                 .replace('\002', ''))
                    self.stdout.flush()
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
        return super().prompt


class ReadlineHistoryAdder(Thread):

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
        files = hist.gc.unlocked_files()
        i = 1
        for _, _, f in files:
            try:
                lj = lazyjson.LazyJSON(f, reopen=False)
                for cmd in lj['cmds']:
                    inp = cmd['inp'].splitlines()
                    for line in inp:
                        if line == 'EOF':
                            continue
                        readline.add_history(line)
                        if RL_LIB is not None:
                            RL_LIB.history_set_pos(i)
                        i += 1
                lj.close()
            except (IOError, OSError):
                continue

