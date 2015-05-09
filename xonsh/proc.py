import io
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
       
        self.stdin = None
        self.stdout = None
        self.stderr = None

        (p2cread, p2cwrite,
         c2pread, c2pwrite,
         errread, errwrite) = self._get_handles(stdin, stdout, stderr)
    
        if p2cwrite != -1:
            self.stdin = io.open(p2cwrite, 'wb', -1)
            self.stdin = io.TextIOWrapper(self.stdin, write_through=True,
                                          line_buffering=(bufsize==1))

        if c2pread != -1:
            self.stdout = io.open(c2pread, 'rb', -1)
            self.stdout = io.TextIOWrapper(self.stdout)
        if errread != -1:
            self.stderr = io.open(errread, 'rb', -1)
            self.stderr = io.TextIOWrapper(self.stderr)

        if self.stdout is None:
            self.stdout = sys.stdout
        if self.stderr is None:
            self.stderr = sys.stderr

        Thread.__init__(self)
        self.start() # start executing the function

    def run(self):
        if self.f is not None:
            r = self.f(self.args, self.stdin, self.stdout, self.stderr)
            self.returncode = r if r is not None else True

    def poll(self):
        return self.returncode

class SimpleProcProxy(ProcProxy):
    def __init__(self, f, args, stdin, stdout, stderr):
        ProcProxy.__init__(self, f, args, stdin, stdout, stderr)

    def run(self):
        if self.f is not None:
            try:
                r = self.f(self.args, self.stdin.read() if self.stdin is not None else "")
                if isinstance(r, Sequence):
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
