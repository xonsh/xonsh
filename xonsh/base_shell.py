# -*- coding: utf-8 -*-
"""The base class for xonsh shell"""
import io
import os
import sys
import time
import builtins

from xonsh.tools import (XonshError, print_exception, DefaultNotGiven,
                         check_for_partial_string, format_std_prepost,
                         get_line_continuation)
from xonsh.platform import HAS_PYGMENTS, ON_WINDOWS
from xonsh.codecache import (should_use_cache, code_cache_name,
                             code_cache_check, get_cache_filename,
                             update_cache, run_compiled_code)
from xonsh.completer import Completer
from xonsh.prompt.base import multiline_prompt, PromptFormatter
from xonsh.events import events
from xonsh.shell import transform_command
from xonsh.lazyimps import pygments, pyghooks
from xonsh.ansi_colors import ansi_partial_color_format

if ON_WINDOWS:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleTitleW.argtypes = [ctypes.c_wchar_p]


class _TeeStdBuf(io.RawIOBase):
    """A dispatcher for bytes to two buffers, as std stream buffer and an
    in memory buffer.
    """

    def __init__(self, stdbuf, membuf, encoding=None, errors=None, prestd=b'',
                 poststd=b''):
        """
        Parameters
        ----------
        stdbuf : BytesIO-like or StringIO-like
            The std stream buffer.
        membuf : BytesIO-like
            The in memory stream buffer.
        encoding : str or None, optional
            The encoding of the stream. Only used if stdbuf is a text stream,
            rather than a binary one. Defaults to $XONSH_ENCODING if None.
        errors : str or None, optional
            The error form for the encoding of the stream. Only used if stdbuf
            is a text stream, rather than a binary one. Deafults to
            $XONSH_ENCODING_ERRORS if None.
        prestd : bytes, optional
            The prefix to prepend to the standard buffer.
        poststd : bytes, optional
            The postfix to append to the standard buffer.
        """
        self.stdbuf = stdbuf
        self.membuf = membuf
        env = builtins.__xonsh_env__
        self.encoding = env.get('XONSH_ENCODING') if encoding is None else encoding
        self.errors = env.get('XONSH_ENCODING_ERRORS') if errors is None else errors
        self.prestd = prestd
        self.poststd = poststd
        self._std_is_binary = not hasattr(stdbuf, 'encoding')

    def fileno(self):
        """Returns the file descriptor of the std buffer."""
        return self.stdbuf.fileno()

    def seek(self, offset, whence=io.SEEK_SET):
        """Sets the location in both the stdbuf and the membuf."""
        self.stdbuf.seek(offset, whence)
        self.membuf.seek(offset, whence)

    def truncate(self, size=None):
        """Truncate both buffers."""
        self.stdbuf.truncate(size)
        self.membuf.truncate(size)

    def readinto(self, b):
        """Read bytes into buffer from both streams."""
        if self._std_is_binary:
            self.stdbuf.readinto(b)
        return self.membuf.readinto(b)

    def write(self, b):
        """Write bytes into both buffers."""
        std_b = b
        if self.prestd:
            std_b = self.prestd + b
        if self.poststd:
            std_b += self.poststd
        # write to stdbuf
        if self._std_is_binary:
            self.stdbuf.write(std_b)
        else:
            self.stdbuf.write(std_b.decode(encoding=self.encoding,
                                           errors=self.errors))
        return self.membuf.write(b)


class _TeeStd(io.TextIOBase):
    """Tees a std stream into an in-memory container and the original stream."""

    def __init__(self, name, mem, prestd='', poststd=''):
        """
        Parameters
        ----------
        name : str
            The name of the buffer in the sys module, e.g. 'stdout'.
        mem : io.TextIOBase-like
            The in-memory text-based representation.
        prestd : str, optional
            The prefix to prepend to the standard stream.
        poststd : str, optional
            The postfix to append to the standard stream.
        """
        self._name = name
        self.std = std = getattr(sys, name)
        self.mem = mem
        self.prestd = prestd
        self.poststd = poststd
        preb = prestd.encode(encoding=mem.encoding, errors=mem.errors)
        postb = poststd.encode(encoding=mem.encoding, errors=mem.errors)
        if hasattr(std, 'buffer'):
            buffer = _TeeStdBuf(std.buffer, mem.buffer,
                                prestd=preb, poststd=postb)
        else:
            # TextIO does not have buffer as part of the API, so std streams
            # may not either.
            buffer = _TeeStdBuf(std, mem.buffer, encoding=mem.encoding,
                                errors=mem.errors, prestd=preb, poststd=postb)
        self.buffer = buffer
        setattr(sys, name, self)

    @property
    def encoding(self):
        """The encoding of the in-memory buffer."""
        return self.mem.encoding

    @property
    def errors(self):
        """The errors of the in-memory buffer."""
        return self.mem.errors

    @property
    def newlines(self):
        """The newlines of the in-memory buffer."""
        return self.mem.newlines

    def _replace_std(self):
        std = self.std
        if std is None:
            return
        setattr(sys, self._name, std)
        self.std = self._name = None

    def __del__(self):
        self._replace_std()

    def close(self):
        """Restores the original std stream."""
        self._replace_std()

    def write(self, s):
        """Writes data to the original std stream and the in-memory object."""
        self.mem.write(s)
        if self.std is None:
            return
        std_s = s
        if self.prestd:
            std_s = self.prestd + std_s
        if self.poststd:
            std_s += self.poststd
        self.std.write(std_s)

    def flush(self):
        """Flushes both the original stdout and the buffer."""
        self.std.flush()
        self.mem.flush()

    def fileno(self):
        """Tunnel fileno() calls to the std stream."""
        return self.std.fileno()

    def seek(self, offset, whence=io.SEEK_SET):
        """Seek to a location in both streams."""
        self.std.seek(offset, whence)
        self.mem.seek(offset, whence)

    def truncate(self, size=None):
        """Seek to a location in both streams."""
        self.std.truncate(size)
        self.mem.truncate(size)

    def detach(self):
        """This operation is not supported."""
        raise io.UnsupportedOperation

    def read(self, size=None):
        """Read from the in-memory stream and seek to a new location in the
        std stream.
        """
        s = self.mem.read(size)
        loc = self.std.tell()
        self.std.seek(loc + len(s))
        return s

    def readline(self, size=-1):
        """Read a line from the in-memory stream and seek to a new location
        in the std stream.
        """
        s = self.mem.readline(size)
        loc = self.std.tell()
        self.std.seek(loc + len(s))
        return s


class Tee:
    """Class that merges tee'd stdout and stderr into a single stream.

    This represents what a user would actually see on the command line.
    This class has the same interface as io.TextIOWrapper, except that
    the buffer is optional.
    """
    # pylint is a stupid about counting public methods when using inheritance.
    # pylint: disable=too-few-public-methods

    def __init__(self, buffer=None, encoding=None, errors=None,
                 newline=None, line_buffering=False, write_through=False):
        self.buffer = io.BytesIO() if buffer is None else buffer
        self.memory = io.TextIOWrapper(self.buffer, encoding=encoding,
                                       errors=errors, newline=newline,
                                       line_buffering=line_buffering,
                                       write_through=write_through)
        self.stdout = _TeeStd('stdout', self.memory)
        env = builtins.__xonsh_env__
        prestderr = format_std_prepost(env.get('XONSH_STDERR_PREFIX'))
        poststderr = format_std_prepost(env.get('XONSH_STDERR_POSTFIX'))
        self.stderr = _TeeStd('stderr', self.memory, prestd=prestderr,
                              poststd=poststderr)

    @property
    def line_buffering(self):
        return self.memory.line_buffering

    def __del__(self):
        del self.stdout, self.stderr
        self.stdout = self.stderr = None

    def close(self):
        """Closes the buffer as well as the stdout and stderr tees."""
        self.stdout.close()
        self.stderr.close()
        self.memory.close()

    def getvalue(self):
        """Gets the current contents of the in-memory buffer."""
        m = self.memory
        loc = m.tell()
        m.seek(0)
        s = m.read()
        m.seek(loc)
        return s


class BaseShell(object):
    """The xonsh shell."""

    def __init__(self, execer, ctx, **kwargs):
        super().__init__()
        self.execer = execer
        self.ctx = ctx
        self.completer = Completer() if kwargs.get('completer', True) else None
        self.buffer = []
        self.need_more_lines = False
        self.mlprompt = None
        self._styler = DefaultNotGiven
        self.prompt_formatter = PromptFormatter()
        self.accumulated_inputs = ''

    @property
    def styler(self):
        if self._styler is DefaultNotGiven:
            if HAS_PYGMENTS:
                from xonsh.pyghooks import XonshStyle
                env = builtins.__xonsh_env__
                self._styler = XonshStyle(env.get('XONSH_COLOR_STYLE'))
            else:
                self._styler = None
        return self._styler

    @styler.setter
    def styler(self, value):
        self._styler = value

    @styler.deleter
    def styler(self):
        self._styler = DefaultNotGiven

    def emptyline(self):
        """Called when an empty line has been entered."""
        self.need_more_lines = False
        self.default('')

    def singleline(self, **kwargs):
        """Reads a single line of input from the shell."""
        msg = '{0} has not implemented singleline().'
        raise RuntimeError(msg.format(self.__class__.__name__))

    def precmd(self, line):
        """Called just before execution of line."""
        return line if self.need_more_lines else line.lstrip()

    def default(self, line):
        """Implements code execution."""
        line = line if line.endswith('\n') else line + '\n'
        src, code = self.push(line)
        if code is None:
            return

        events.on_precommand.fire(cmd=src)

        env = builtins.__xonsh_env__
        hist = builtins.__xonsh_history__  # pylint: disable=no-member
        ts1 = None
        enc = env.get('XONSH_ENCODING')
        err = env.get('XONSH_ENCODING_ERRORS')
        tee = Tee(encoding=enc, errors=err)
        try:
            ts0 = time.time()
            run_compiled_code(code, self.ctx, None, 'single')
            ts1 = time.time()
            if hist is not None and hist.last_cmd_rtn is None:
                hist.last_cmd_rtn = 0  # returncode for success
        except XonshError as e:
            print(e.args[0], file=sys.stderr)
            if hist is not None and hist.last_cmd_rtn is None:
                hist.last_cmd_rtn = 1  # return code for failure
        except Exception:  # pylint: disable=broad-except
            print_exception()
            if hist is not None and hist.last_cmd_rtn is None:
                hist.last_cmd_rtn = 1  # return code for failure
        finally:
            ts1 = ts1 or time.time()
            tee_out = tee.getvalue()
            self._append_history(inp=src, ts=[ts0, ts1], tee_out=tee_out)
            self.accumulated_inputs += src
            if (tee_out and env.get('XONSH_APPEND_NEWLINE') and
                    not tee_out.endswith(os.linesep)):
                print(os.linesep, end='')
            tee.close()
            self._fix_cwd()
        if builtins.__xonsh_exit__:  # pylint: disable=no-member
            return True

    def _append_history(self, tee_out=None, **info):
        """Append information about the command to the history.

        This also handles on_postcommand because this is the place where all the
        information is available.
        """
        hist = builtins.__xonsh_history__  # pylint: disable=no-member
        info['rtn'] = hist.last_cmd_rtn if hist is not None else None
        tee_out = tee_out or None
        last_out = hist.last_cmd_out if hist is not None else None
        if last_out is None and tee_out is None:
            pass
        elif last_out is None and tee_out is not None:
            info['out'] = tee_out
        elif last_out is not None and tee_out is None:
            info['out'] = last_out
        else:
            info['out'] = tee_out + '\n' + last_out
        events.on_postcommand.fire(
            cmd=info['inp'],
            rtn=info['rtn'],
            out=info.get('out', None),
            ts=info['ts']
        )
        if hist is not None:
            hist.append(info)
            hist.last_cmd_rtn = hist.last_cmd_out = None

    def _fix_cwd(self):
        """Check if the cwd changed out from under us."""
        env = builtins.__xonsh_env__
        try:
            cwd = os.getcwd()
        except (FileNotFoundError, OSError):
            cwd = None
        if cwd is None:
            # directory has been deleted out from under us, most likely
            pwd = env.get('PWD', None)
            if pwd is None:
                # we have no idea where we are
                env['PWD'] = '<invalid directory>'
            elif os.path.isdir(pwd):
                # unclear why os.getcwd() failed. do nothing.
                pass
            else:
                # OK PWD is really gone.
                msg = '{UNDERLINE_INTENSE_WHITE}{BACKGROUND_INTENSE_BLACK}'
                msg += "xonsh: working directory does not exist: " + pwd
                msg += '{NO_COLOR}'
                self.print_color(msg, file=sys.stderr)
        elif 'PWD' not in env:
            # $PWD is missing from env, recreate it
            env['PWD'] = cwd
        elif os.path.realpath(cwd) != os.path.realpath(env['PWD']):
            # The working directory has changed without updating $PWD, fix this
            old = env['PWD']
            env['PWD'] = cwd
            env['OLDPWD'] = old
            events.on_chdir.fire(olddir=old, newdir=cwd)

    def push(self, line):
        """Pushes a line onto the buffer and compiles the code in a way that
        enables multiline input.
        """
        self.buffer.append(line)
        if self.need_more_lines:
            return None, None
        src = ''.join(self.buffer)
        src = transform_command(src)
        return self.compile(src)

    def compile(self, src):
        """Compiles source code and returns the (possibly modified) source and
        a valid code object.
        """
        _cache = should_use_cache(self.execer, 'single')
        if _cache:
            codefname = code_cache_name(src)
            cachefname = get_cache_filename(codefname, code=True)
            usecache, code = code_cache_check(cachefname)
            if usecache:
                self.reset_buffer()
                return src, code
        lincont = get_line_continuation()
        if src.endswith(lincont + '\n'):
            self.need_more_lines = True
            return src, None
        try:
            code = self.execer.compile(src,
                                       mode='single',
                                       glbs=self.ctx,
                                       locs=None)
            if _cache:
                update_cache(code, cachefname)
            self.reset_buffer()
        except SyntaxError:
            partial_string_info = check_for_partial_string(src)
            in_partial_string = (partial_string_info[0] is not None and
                                 partial_string_info[1] is None)
            if (src == '\n' or src.endswith('\n\n')) and not in_partial_string:
                self.reset_buffer()
                print_exception()
                return src, None
            self.need_more_lines = True
            code = None
        except Exception:  # pylint: disable=broad-except
            self.reset_buffer()
            print_exception()
            code = None
        return src, code

    def reset_buffer(self):
        """Resets the line buffer."""
        self.buffer.clear()
        self.need_more_lines = False
        self.mlprompt = None

    def settitle(self):
        """Sets terminal title."""
        env = builtins.__xonsh_env__  # pylint: disable=no-member
        term = env.get('TERM', None)
        # Shells running in emacs sets TERM to "dumb" or "eterm-color".
        # Do not set title for these to avoid garbled prompt.
        if (term is None and not ON_WINDOWS) or term in ['dumb', 'eterm-color',
                                                         'linux']:
            return
        t = env.get('TITLE')
        if t is None:
            return
        t = self.prompt_formatter(t)
        if ON_WINDOWS and 'ANSICON' not in env:
            kernel32.SetConsoleTitleW(t)
        else:
            with open(1, 'wb', closefd=False) as f:
                # prevent xonsh from answering interactive questions
                # on the next command by writing the title
                f.write("\x1b]0;{0}\x07".format(t).encode())
                f.flush()

    @property
    def prompt(self):
        """Obtains the current prompt string."""
        if self.need_more_lines:
            if self.mlprompt is None:
                try:
                    self.mlprompt = multiline_prompt()
                except Exception:  # pylint: disable=broad-except
                    print_exception()
                    self.mlprompt = '<multiline prompt error> '
            return self.mlprompt
        env = builtins.__xonsh_env__  # pylint: disable=no-member
        p = env.get('PROMPT')
        try:
            p = self.prompt_formatter(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        self.settitle()
        return p

    def format_color(self, string, hide=False, force_string=False, **kwargs):
        """Formats the colors in a string. ``BaseShell``'s default implementation
        of this method uses colors based on ANSI color codes.
        """
        style = builtins.__xonsh_env__.get('XONSH_COLOR_STYLE')
        return ansi_partial_color_format(string, hide=hide, style=style)

    def print_color(self, string, hide=False, **kwargs):
        """Prints a string in color. This base implementation's colors are based
        on ANSI color codes if a string was given as input. If a list of token
        pairs is given, it will color based on pygments, if available. If
        pygments is not available, it will print a colorless string.
        """
        if isinstance(string, str):
            s = self.format_color(string, hide=hide)
        elif HAS_PYGMENTS:
            # assume this is a list of (Token, str) tuples and format it
            env = builtins.__xonsh_env__
            self.styler.style_name = env.get('XONSH_COLOR_STYLE')
            style_proxy = pyghooks.xonsh_style_proxy(self.styler)
            formatter = pyghooks.XonshTerminal256Formatter(style=style_proxy)
            s = pygments.format(string, formatter).rstrip()
        else:
            # assume this is a list of (Token, str) tuples and remove color
            s = ''.join([x for _, x in string])
        print(s, **kwargs)

    def color_style_names(self):
        """Returns an iterable of all available style names."""
        return ()

    def color_style(self):
        """Returns the current color map."""
        return {}

    def restore_tty_sanity(self):
        """An interface for resetting the TTY stdin mode. This is highly
        dependent on the shell backend. Also it is mostly optional since
        it only affects ^Z backgrounding behaviour.
        """
        pass
