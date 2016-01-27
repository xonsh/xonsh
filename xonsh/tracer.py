"""Implements a xonsh tracer."""
import sys
import inspect
import linecache    

from xonsh.tools import DefaultNotGiven, print_color, pygments_version
if pygments_version():
    from xonsh import pyghooks
    import pygments
    import pygments.formatters.terminal
else:
    pyghooks = None

class TracerType(object):
    """Represents a xonsh tracer object, which keeps track of all tracing
    state. This is a singleton.
    """

    _inst = None

    def __new__(cls, *args, **kwargs):
        if cls._inst is None:
            cls._inst = super(TracerType, cls).__new__(cls, *args, 
                                                           **kwargs)
        return cls._inst

    def __init__(self):
        self.prev_tracer = DefaultNotGiven
        self.files = set()
        self.usecolor = True
        self.lexer = pyghooks.XonshLexer()
        self.formatter = pygments.formatters.terminal.TerminalFormatter()

    def __del__(self):
        for f in set(self.files):
            self.stop(f)

    def start(self, filename):
        """Starts tracing a file."""
        if len(self.files) == 0:
            self.prev_tracer = sys.gettrace()
        self.files.add(filename)
        sys.settrace(self.trace)
        print(self.files)

    def stop(self, filename):
        """Stops tracing a file."""
        self.files.discard(filename)
        if len(self.files) == 0:
            sys.settrace(self.prev_tracer)
            self.prev_tracer = DefaultNotGiven

    def trace(self, frame, event, arg):
        """Implements a line tracing function."""
        fname = frame.f_code.co_filename
        #print(fname, frame.f_lineno)
        if event != 'line':
            return self.trace
        if fname in self.files:
            lineno = frame.f_back.f_lineno
            print(lineno)
            #line = linecache.getline(fname, lineno)
            line = inspect.getsource(frame)
            print(line)
            #s = format_line(fname, lineno, line, color=self.usecolor,
            #                lexer=self.lexer, formatter=self.formatter)
            print_color(s)
        return self.trace

tracer = TracerType()

COLORLESS_LINE = '{fname}:{lineno}:{line}'
COLOR_LINE = ('{{PURPLE}}{fname}{{BLUE}}:'
              '{{GREEN}}{lineno}{{BLUE}}:'
              '{{NO_COLOR}}{line}')

def format_line(fname, lineno, line, color=True, lexer=None, formatter=None):
    """Formats a trace line suitable for printing."""
    if not color:
        return COLORLESS_LINE.format(fname=fname, lineno=lineno, line=line)
    if pyghooks is not None:
        lexer = lexer or pyghooks.XonshLexer()
        formatter = formatter or pygments.formatters.terminal.TerminalFormatter()
        line = pygments.highlight(line, lexer, formatter)
        print(repr(line))
    return COLOR_LINE.format(fname=fname, lineno=lineno, line=line)
