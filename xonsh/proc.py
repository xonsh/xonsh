import io
import os
import sys

from threading import Thread
from subprocess import Popen
from collections import Sequence

from xonsh.tools import redirect_stdout, redirect_stderr

class ProcProxy(Thread, Popen):
    def __init__(self, f, args, stdin, stdout, stderr, universal_newlines):
        self.f = f
        self.args = args
        self.pid = None
        self.returncode = None
       
        handles = self._get_handles(stdin, stdout, stderr)
        (self.p2cread, self.p2cwrite,
         self.c2pread, self.c2pwrite,
         self.errread, self.errwrite) = handles

        # default values
        self.stdin = stdin
        self.stdout = None
        self.stderr = None

        if self.p2cwrite != -1:
            self.stdin = io.open(self.p2cwrite, 'wb', -1)
            if universal_newlines:
                self.stdin = io.TextIOWrapper(self.stdin, write_through=True,
                                              line_buffering=False)
        if self.c2pread != -1:
            self.stdout = io.open(self.c2pread, 'rb', -1)
            if universal_newlines:
                self.stdout = io.TextIOWrapper(self.stdout)
        if self.errread != -1:
            self.stderr = io.open(self.errread, 'rb', -1)
            if universal_newlines:
                self.stderr = io.TextIOWrapper(self.stderr)

        Thread.__init__(self)
        self.start()

    def run(self):
        if self.f is not None:
            # need to make file-likes here that work in the "opposite" direction
            if self.stdin is not None:
                sp_stdin = io.TextIOWrapper(self.stdin)
            else:
                sp_stdin = io.StringIO("")
            if self.c2pwrite != -1:
                sp_stdout = io.TextIOWrapper(io.open(self.c2pwrite, 'wb', -1))
            else:
                sp_stdout = sys.stdout
            if self.errwrite != -1:
                sp_stderr = io.TextIOWrapper(io.open(self.errwrite, 'wb', -1))
            else:
                sp_stderr = sys.stderr
            r = self.f(self.args, sp_stdin, sp_stdout, sp_stderr)
            self.returncode = r if r is not None else True

    def poll(self):
        return self.returncode

def _simple_wrapper(f):
    def wrapped_simple_command_proxy(args, stdin, stdout, stderr):
        try:
            i = stdin.read()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                r = f(args, i)
            if isinstance(r, str):
                stdout.write(r)
            if isinstance(r, Sequence):
                if r[0] is not None:
                    stdout.write(r[0])
                if r[1] is not None:
                    stderr.write(r[1])
            elif r is not None:
                stdout.write(str(r))
            return True
        except:
            return False
    return wrapped_simple_command_proxy

class SimpleProcProxy(ProcProxy):
    def __init__(self, f, args, stdin, stdout, stderr, universal_newlines):
        ProcProxy.__init__(self, _simple_wrapper(f), args,
                           stdin, stdout, stderr,
                           universal_newlines)
