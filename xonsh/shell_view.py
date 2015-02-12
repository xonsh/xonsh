"""The main shell for xonsh."""
import os
import sys
import time
import copy
import errno
import select
import struct
import signal
import atexit
import traceback

try:
    import pty
    import fcntl
    import termios
except ImportError:
    pass  # windows  

from urwid import Widget
from urwid.vterm import TermModes, TermCanvas
from urwid.display_common import AttrSpec, RealTerminal

class ShellView(Widget):
    _selectable = True
    _sizing = frozenset(['box'])
    signals = ['closed', 'beep', 'leds', 'title']

    def __init__(self, env=None, main_loop=None, escape_sequence=None):
        """
        A terminal emulator within a widget.
        'command' is the command to execute inside the terminal, provided as a
        list of the command followed by its arguments.  If 'command' is None,
        the command is the current user's shell. You can also provide a callable
        instead of a command, which will be executed in the subprocess.
        'env' can be used to pass custom environment variables. If omitted,
        os.environ is used.
        'main_loop' should be provided, because the canvas state machine needs
        to act on input from the PTY master device. This object must have
        watch_file and remove_watch_file methods.
        'escape_sequence' is the urwid key symbol which should be used to break
        out of the terminal widget. If it's not specified, "ctrl a" is used.
        """
        self.__super.__init__()

        if escape_sequence is None:
            self.escape_sequence = "ctrl a"
        else:
            self.escape_sequence = escape_sequence

        if env is None:
            self.env = dict(os.environ)
        else:
            self.env = dict(env)

        self.keygrab = False
        self.last_key = None

        self.response_buffer = []

        self.term_modes = TermModes()

        self.main_loop = main_loop

        self.master = None
        self.pid = None

        self.width = None
        self.height = None
        self.term = None
        self.has_focus = False
        self.terminated = False

    def spawn(self):
        env = self.env
        env['TERM'] = 'linux'

        self.pid, self.master = pty.fork()

        if self.pid == 0:
            if callable(self.command):
                try:
                    try:
                        self.command()
                    except:
                        sys.stderr.write(traceback.format_exc())
                        sys.stderr.flush()
                finally:
                    os._exit(0)
            else:
                os.execvpe(self.command[0], self.command, env)

        if self.main_loop is None:
            fcntl.fcntl(self.master, fcntl.F_SETFL, os.O_NONBLOCK)

        atexit.register(self.terminate)

    def terminate(self):
        if self.terminated:
            return

        self.terminated = True
        self.remove_watch()
        self.change_focus(False)

        if self.pid > 0:
            self.set_termsize(0, 0)
            for sig in (signal.SIGHUP, signal.SIGCONT, signal.SIGINT,
                        signal.SIGTERM, signal.SIGKILL):
                try:
                    os.kill(self.pid, sig)
                    pid, status = os.waitpid(self.pid, os.WNOHANG)
                except OSError:
                    break

                if pid == 0:
                    break
                time.sleep(0.1)
            try:
                os.waitpid(self.pid, 0)
            except OSError:
                pass

            os.close(self.master)

    def beep(self):
        self._emit('beep')

    def leds(self, which):
        self._emit('leds', which)

    def respond(self, string):
        """
        Respond to the underlying application with 'string'.
        """
        self.response_buffer.append(string)

    def flush_responses(self):
        for string in self.response_buffer:
            os.write(self.master, string.encode('ascii'))
        self.response_buffer = []

    def set_termsize(self, width, height):
        winsize = struct.pack("HHHH", height, width, 0, 0)
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, winsize)

    def touch_term(self, width, height):
        process_opened = False

        if self.pid is None:
            self.spawn()
            process_opened = True

        if self.width == width and self.height == height:
            return

        self.set_termsize(width, height)

        if not self.term:
            self.term = TermCanvas(width, height, self)
        else:
            self.term.resize(width, height)

        self.width = width
        self.height = height

        if process_opened:
            self.add_watch()

    def set_title(self, title):
        self._emit('title', title)

    def change_focus(self, has_focus):
        """
        Ignore SIGINT if this widget has focus.
        """
        if self.terminated or self.has_focus == has_focus:
            return

        self.has_focus = has_focus

        if has_focus:
            self.old_tios = RealTerminal().tty_signal_keys()
            RealTerminal().tty_signal_keys(*(['undefined'] * 5))
        else:
            RealTerminal().tty_signal_keys(*self.old_tios)

    def render(self, size, focus=False):
        if not self.terminated:
            self.change_focus(focus)

            width, height = size
            self.touch_term(width, height)

            if self.main_loop is None:
                self.feed()

        return self.term

    def add_watch(self):
        if self.main_loop is None:
            return

        self.main_loop.watch_file(self.master, self.feed)

    def remove_watch(self):
        if self.main_loop is None:
            return

        self.main_loop.remove_watch_file(self.master)

    def selectable(self):
        return True

    def wait_and_feed(self, timeout=1.0):
        while True:
            try:
                select.select([self.master], [], [], timeout)
                break
            except select.error as e:
                if e.args[0] != 4:
                    raise
        self.feed()

    def feed(self):
        data = ''

        try:
            data = os.read(self.master, 4096)
        except OSError as e:
            if e.errno == 5: # End Of File
                data = ''
            elif e.errno == errno.EWOULDBLOCK: # empty buffer
                return
            else:
                raise

        if data == '': # EOF on BSD
            self.terminate()
            self._emit('closed')
            return

        self.term.addstr(data)

        self.flush_responses()

    def keypress(self, size, key):
        if self.terminated:
            return key

        if key == "window resize":
            width, height = size
            self.touch_term(width, height)
            return

        if (self.last_key == self.escape_sequence
            and key == self.escape_sequence):
            # escape sequence pressed twice...
            self.last_key = key
            self.keygrab = True
            # ... so pass it to the terminal
        elif self.keygrab:
            if self.escape_sequence == key:
                # stop grabbing the terminal
                self.keygrab = False
                self.last_key = key
                return
        else:
            if key == 'page up':
                self.term.scroll_buffer()
                self.last_key = key
                self._invalidate()
                return
            elif key == 'page down':
                self.term.scroll_buffer(up=False)
                self.last_key = key
                self._invalidate()
                return
            elif (self.last_key == self.escape_sequence
                  and key != self.escape_sequence):
                # hand down keypress directly after ungrab.
                self.last_key = key
                return key
            elif self.escape_sequence == key:
                # start grabbing the terminal
                self.keygrab = True
                self.last_key = key
                return
            elif self._command_map[key] is None or key == 'enter':
                # printable character or escape sequence means:
                # lock in terminal...
                self.keygrab = True
                # ... and do key processing
            else:
                # hand down keypress
                self.last_key = key
                return key

        self.last_key = key

        self.term.scroll_buffer(reset=True)

        if key.startswith("ctrl "):
            if key[-1].islower():
                key = chr(ord(key[-1]) - ord('a') + 1)
            else:
                key = chr(ord(key[-1]) - ord('A') + 1)
        else:
            if self.term_modes.keys_decckm and key in KEY_TRANSLATIONS_DECCKM:
                key = KEY_TRANSLATIONS_DECCKM.get(key)
            else:
                key = KEY_TRANSLATIONS.get(key, key)

        # ENTER transmits both a carriage return and linefeed in LF/NL mode.
        if self.term_modes.lfnl and key == "\x0d":
            key += "\x0a"

        if PYTHON3:
            key = key.encode('ascii')

        os.write(self.master, key)

