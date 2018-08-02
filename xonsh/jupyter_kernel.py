# -*- coding: utf-8 -*-
"""Hooks for Jupyter Xonsh Kernel."""
import sys
import json
import hmac
import uuid
import errno
import hashlib
import datetime
import builtins
import threading
from pprint import pformat

import zmq
from zmq.eventloop import ioloop, zmqstream
from zmq.error import ZMQError

from xonsh import __version__ as version
from xonsh.main import main_context
from xonsh.completer import Completer


MAX_SIZE = 8388608  # 8 Mb
DELIM = b"<IDS|MSG>"


def dump_bytes(*args, **kwargs):
    """Converts an object to JSON and returns the bytes."""
    return json.dumps(*args, **kwargs).encode('ascii')


class XonshKernel:
    """Xonsh xernal for Jupyter"""
    implementation = 'Xonsh ' + version
    implementation_version = version
    language = 'xonsh'
    language_version = version
    banner = 'Xonsh - Python-powered, cross-platform shell'
    language_info = {'name': 'xonsh',
                     'version': version,
                     'pygments_lexer': 'xonsh',
                     'codemirror_mode': 'shell',
                     'mimetype': 'text/x-sh',
                     'file_extension': '.xsh',
                     }

    def __init__(self, debug_level=3, session_id=None, **kwargs):
        """
        Parameters
        ----------
        debug_level : int, optional
            Integer from 0 (no debugging) to 3 (all debugging), default: 0.
        session_id : str or None, optional
            Unique string id representing the kernel session. If None, this will
            be replaced with a random UUID.
        """
        self.debug_level = debug_level
        self.session_id = str(uuid.uuid4()) if session_id is None else session_id

        self.exiting = False
        self.completer = Completer()

    def shutdown(self):
        """Shutsdown the kernel"""
        self.exiting = True
        ioloop.IOLoop.instance().stop()

    def dprint(self, level, *args, **kwargs):
        """Print but with debug information."""
        if level <= self.debug_level:
            print("DEBUG" + str(level) + ':', *args, **kwargs)
            sys.stdout.flush()

    def sign(self, messages):
        """Sign a message list with a secure signature."""
        h = self.auth.copy()
        for m in messages:
            h.update(m)
        return h.hexdigest().encode('ascii')

    def new_header(self, message_type):
        """Make a new header"""
        return {
            "date": datetime.datetime.now().isoformat(),
            "msg_id": str(uuid.uuid4()),
            "username": "kernel",
            "session": self.session_id,
            "msg_type": message_type,
            "version": "5.0",
        }

    def send(self, stream, message_type, content=None, parent_header=None, metadata=None,
             identities=None):
        """Send data to the client via a stream"""
        header = self.new_header(message_type)
        if content is None:
            content = {}
        if parent_header is None:
            parent_header = {}
        if metadata is None:
            metadata = {}

        messages = list(map(dump_bytes, [header, parent_header, metadata, content]))
        signature = sign(messages)
        parts = [DELIM, signature] + messages
        if identities:
            parts = identities + parts
        self.dprint(3, "send parts:", parts)
        stream.send_multipart(parts)
        stream.flush()

    def run_thread(self, loop, name):
        """Run main thread"""
        self.dprint(2, "Starting loop for {name!r}...".format(name=name))
        while not self.exiting:
            self.dprint(2, "{} Loop!".format(name))
            try:
                loop.start()
            except ZMQError as e:
                self.dprint(1, "{} ZMQError!\n  {}".format(name, e))
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise
            except Exception:
                self.dprint(2, "{} Exception!".format(name))
                if self.exiting:
                    break
                else:
                    raise
            else:
                self.dprint(2, "{} Break!".format(name))
                break

    def heartbeat_loop(self):
        """Run heartbeat"""
        self.dprint(2, "Starting heartbeat loop...")
        while not self.exiting:
            self.dprint(3, ".", end="")
            try:
                zmq.device(zmq.FORWARDER, heartbeat_socket, heartbeat_socket)
            except zmq.ZMQError as e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise
            else:
                break

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        """Execute user code."""
        if len(code.strip()) == 0:
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        shell = builtins.__xonsh_shell__
        hist = builtins.__xonsh_history__
        try:
            shell.default(code)
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True

        if not silent:  # stdout response
            if hasattr(builtins, '_') and builtins._ is not None:
                # rely on sys.displayhook functionality
                self._respond_in_chunks('stdout', pformat(builtins._))
                builtins._ = None
            if hist is not None and len(hist) > 0:
                self._respond_in_chunks('stdout', hist.outs[-1])

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        rtn = 0 if (hist is None or len(hist) == 0) else hist.rtns[-1]
        if 0 < rtn:
            message = {'status': 'error', 'execution_count': self.execution_count,
                       'ename': '', 'evalue': str(rtn), 'traceback': []}
        else:
            message = {'status': 'ok', 'execution_count': self.execution_count,
                       'payload': [], 'user_expressions': {}}
        return message

    def _respond_in_chunks(self, name, s, chunksize=1024):
        if s is None:
            return
        n = len(s)
        if n == 0:
            return
        lower = range(0, n, chunksize)
        upper = range(chunksize, n + chunksize, chunksize)
        for l, u in zip(lower, upper):
            response = {'name': name, 'text': s[l:u], }
            self.send_response(self.iopub_socket, 'stream', response)

    def do_complete(self, code, pos):
        """Get completions."""
        shell = builtins.__xonsh_shell__
        line = code.split('\n')[-1]
        line = builtins.aliases.expand_alias(line)
        prefix = line.split(' ')[-1]
        endidx = pos
        begidx = pos - len(prefix)
        rtn, _ = self.completer.complete(prefix, line, begidx,
                                         endidx, shell.ctx)
        message = {'matches': rtn, 'cursor_start': begidx, 'cursor_end': endidx,
                   'metadata': {}, 'status': 'ok'}
        return message


if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    # must manually pass in args to avoid interfering w/ Jupyter arg parsing
    with main_context(argv=['--shell-type=readline']):
        IPKernelApp.launch_instance(kernel_class=XonshKernel)
