import io
import os
import sys

from threading import Thread
from subprocess import Popen
from collections import Sequence


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
        self.stdin = None
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
            r = self.f(self.args, self.stdin, self.stdout, self.stderr)
            self.returncode = r if r is not None else True
        self._cleanup()

    def poll(self):
        return self.returncode

    def _cleanup(self):
        if self.p2cread != -1 and self.p2cwrite != -1:
            os.close(self.p2cread)
        if self.c2pwrite != -1 and self.c2pread != -1:
            os.close(self.c2pwrite)
        if self.errwrite != -1 and self.errread != -1:
            os.close(self.errwrite)


class SimpleProcProxy(ProcProxy):
    def __init__(self, f, args, stdin, stdout, stderr, universal_newlines):
        ProcProxy.__init__(self, f, args,
                           stdin, stdout, stderr,
                           universal_newlines)

    def run(self):
        if self.f is not None:
            try:
                if self.p2cread != -1:
                    inp = io.open(self.p2cread, 'rb', -1).read()
                else:
                    inp = b""
                r = self.f(self.args, inp.decode())
                if isinstance(r, tuple):
                    if self.stdout is not None:
                        os.write(self.c2pwrite, _prep(r[0]))
                    else:
                        print(r[0])
                    if self.stderr is not None:
                        os.write(self.errwrite, _prep(r[1]))
                    else:
                        print(r[1], file=sys.stderr)
                else:
                    if self.stdout is not None:
                        os.write(self.c2pwrite, _prep(r))
                    else:
                        print(r)
                self.returncode = True
            except:
                self.returncode = False
        self._cleanup()

def _prep(x):
    return (x or '').encode('utf-8')
