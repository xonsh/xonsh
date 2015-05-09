import io
import os
import sys

from threading import Thread
from subprocess import Popen
from collections import Sequence

class ProcProxy(Thread, Popen):
    def __init__(self, f, args, stdin, stdout, stderr):
        self.f = f
        self.args = args
        self.pid = None
        self.returncode = None
       
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

        (self.p2cread, self.p2cwrite,
         self.c2pread, self.c2pwrite,
         self.errread, self.errwrite) = self._get_handles(stdin, stdout, stderr)
    
        if self.p2cwrite != -1:
            self.stdin = io.open(self.p2cwrite, 'wb', -1)
            self.stdin = io.TextIOWrapper(self.stdin, write_through=True,
                                          line_buffering=(bufsize==1))

        if self.c2pread != -1:
            self.stdout = io.open(self.c2pread, 'rb', -1)
            self.stdout = io.TextIOWrapper(self.stdout)
        if self.errread != -1:
            self.stderr = io.open(self.errread, 'rb', -1)
            self.stderr = io.TextIOWrapper(self.stderr)

        if self.stdout is None:
            self.stdout = sys.stdout
        if self.stderr is None:
            self.stderr = sys.stderr

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
    def __init__(self, f, args, stdin, stdout, stderr):
        ProcProxy.__init__(self, f, args, stdin, stdout, stderr)

    def run(self):
        if self.f is not None:
            try:
                r = self.f(self.args, self.stdin.read() if self.stdin is not None else "")
                if isinstance(r, tuple):
                    if self.stdout is not None:
                        self.stdout.write(r[0] or '')
                    if self.stderr is not None:
                        self.stderr.write(r[1] or '')
                else:
                    if self.stdout is not None:
                        self.stdout.write(r or '')
                self.returncode = True
            except:
                self.returncode = False
        self._cleanup()
