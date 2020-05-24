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
from argparse import ArgumentParser
from collections.abc import Set

import zmq
from zmq.eventloop import ioloop, zmqstream
from zmq.error import ZMQError

from xonsh import __version__ as version
from xonsh.main import setup
from xonsh.completer import Completer
from xonsh.commands_cache import predict_true


MAX_SIZE = 8388608  # 8 Mb
DELIM = b"<IDS|MSG>"


def dump_bytes(*args, **kwargs):
    """Converts an object to JSON and returns the bytes."""
    return json.dumps(*args, **kwargs).encode("ascii")


def load_bytes(b):
    """Converts bytes of JSON to an object."""
    return json.loads(b.decode("ascii"))


def bind(socket, connection, port):
    """Binds a socket to a port, or a random port if needed. Returns the port."""
    if port <= 0:
        return socket.bind_to_random_port(connection)
    else:
        socket.bind("{}:{}".format(connection, port))
    return port


class XonshKernel:
    """Xonsh xernal for Jupyter"""

    implementation = "Xonsh " + version
    implementation_version = version
    language = "xonsh"
    language_version = version.split(".")[:3]
    banner = "Xonsh - Python-powered, cross-platform shell"
    language_info = {
        "name": "xonsh",
        "version": version,
        "pygments_lexer": "xonsh",
        "codemirror_mode": "shell",
        "mimetype": "text/x-sh",
        "file_extension": ".xsh",
    }
    signature_schemes = {"hmac-sha256": hashlib.sha256}

    def __init__(self, debug_level=0, session_id=None, config=None, **kwargs):
        """
        Parameters
        ----------
        debug_level : int, optional
            Integer from 0 (no debugging) to 3 (all debugging), default: 0.
        session_id : str or None, optional
            Unique string id representing the kernel session. If None, this will
            be replaced with a random UUID.
        config : dict or None, optional
            Configuration dictionary to start server with. BY default will
            search the command line for options (if given) or use default
            configuration.
        """
        self.debug_level = debug_level
        self.session_id = str(uuid.uuid4()) if session_id is None else session_id
        self._parser = None
        self.config = self.make_default_config() if config is None else config

        self.exiting = False
        self.execution_count = 1
        self.completer = Completer()

    @property
    def parser(self):
        if self._parser is None:
            p = ArgumentParser("jupyter_kerenel")
            p.add_argument("-f", dest="config_file", default=None)
            self._parser = p
        return self._parser

    def make_default_config(self):
        """Provides default configuration"""
        ns, unknown = self.parser.parse_known_args(sys.argv)
        if ns.config_file is None:
            self.dprint(1, "Starting xonsh kernel with default args...")
            config = {
                "control_port": 0,
                "hb_port": 0,
                "iopub_port": 0,
                "ip": "127.0.0.1",
                "key": str(uuid.uuid4()),
                "shell_port": 0,
                "signature_scheme": "hmac-sha256",
                "stdin_port": 0,
                "transport": "tcp",
            }
        else:
            self.dprint(1, "Loading simple_kernel with args:", sys.argv)
            self.dprint(1, "Reading config file {!r}...".format(ns.config_file))
            with open(ns.config_file) as f:
                config = json.load(f)
        return config

    def iopub_handler(self, message):
        """Handles iopub requests."""
        self.dprint(2, "iopub received:", message)

    def control_handler(self, wire_message):
        """Handles control requests"""
        self.dprint(1, "control received:", wire_message)
        identities, msg = self.deserialize_wire_message(wire_message)
        if msg["header"]["msg_type"] == "shutdown_request":
            self.shutdown()

    def stdin_handler(self, message):
        self.dprint(2, "stdin received:", message)

    def start(self):
        """Starts the server"""
        ioloop.install()
        connection = self.config["transport"] + "://" + self.config["ip"]
        secure_key = self.config["key"].encode()
        digestmod = self.signature_schemes[self.config["signature_scheme"]]
        self.auth = hmac.HMAC(secure_key, digestmod=digestmod)

        # Heartbeat
        ctx = zmq.Context()
        self.heartbeat_socket = ctx.socket(zmq.REP)
        self.config["hb_port"] = bind(
            self.heartbeat_socket, connection, self.config["hb_port"]
        )

        # IOPub/Sub, aslo called SubSocketChannel in IPython sources
        self.iopub_socket = ctx.socket(zmq.PUB)
        self.config["iopub_port"] = bind(
            self.iopub_socket, connection, self.config["iopub_port"]
        )
        self.iopub_stream = zmqstream.ZMQStream(self.iopub_socket)
        self.iopub_stream.on_recv(self.iopub_handler)

        # Control
        self.control_socket = ctx.socket(zmq.ROUTER)
        self.config["control_port"] = bind(
            self.control_socket, connection, self.config["control_port"]
        )
        self.control_stream = zmqstream.ZMQStream(self.control_socket)
        self.control_stream.on_recv(self.control_handler)

        # Stdin:
        self.stdin_socket = ctx.socket(zmq.ROUTER)
        self.config["stdin_port"] = bind(
            self.stdin_socket, connection, self.config["stdin_port"]
        )
        self.stdin_stream = zmqstream.ZMQStream(self.stdin_socket)
        self.stdin_stream.on_recv(self.stdin_handler)

        # Shell
        self.shell_socket = ctx.socket(zmq.ROUTER)
        self.config["shell_port"] = bind(
            self.shell_socket, connection, self.config["shell_port"]
        )
        self.shell_stream = zmqstream.ZMQStream(self.shell_socket)
        self.shell_stream.on_recv(self.shell_handler)

        # start up configurtation
        self.dprint(2, "Config:", json.dumps(self.config))
        self.dprint(1, "Starting loops...")
        self.hb_thread = threading.Thread(target=self.heartbeat_loop)
        self.hb_thread.daemon = True
        self.hb_thread.start()
        self.dprint(1, "Ready! Listening...")
        ioloop.IOLoop.instance().start()

    def shutdown(self):
        """Shutsdown the kernel"""
        self.exiting = True
        ioloop.IOLoop.instance().stop()

    def dprint(self, level, *args, **kwargs):
        """Print but with debug information."""
        if level <= self.debug_level:
            print("DEBUG" + str(level) + ":", file=sys.__stdout__, *args, **kwargs)
            sys.__stdout__.flush()

    def sign(self, messages):
        """Sign a message list with a secure signature."""
        h = self.auth.copy()
        for m in messages:
            h.update(m)
        return h.hexdigest().encode("ascii")

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

    def send(
        self,
        stream,
        message_type,
        content=None,
        parent_header=None,
        metadata=None,
        identities=None,
    ):
        """Send data to the client via a stream"""
        header = self.new_header(message_type)
        if content is None:
            content = {}
        if parent_header is None:
            parent_header = {}
        if metadata is None:
            metadata = {}

        messages = list(map(dump_bytes, [header, parent_header, metadata, content]))
        signature = self.sign(messages)
        parts = [DELIM, signature] + messages
        if identities:
            parts = identities + parts
        self.dprint(3, "send parts:", parts)
        stream.send_multipart(parts)
        if isinstance(stream, zmqstream.ZMQStream):
            stream.flush()

    def deserialize_wire_message(self, wire_message):
        """Split the routing prefix and message frames from a message on the wire"""
        delim_idx = wire_message.index(DELIM)
        identities = wire_message[:delim_idx]
        m_signature = wire_message[delim_idx + 1]
        msg_frames = wire_message[delim_idx + 2 :]

        keys = ("header", "parent_header", "metadata", "content")
        m = {k: load_bytes(v) for k, v in zip(keys, msg_frames)}
        check_sig = self.sign(msg_frames)
        if check_sig != m_signature:
            raise ValueError("Signatures do not match")
        return identities, m

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
                zmq.device(zmq.FORWARDER, self.heartbeat_socket, self.heartbeat_socket)
            except zmq.ZMQError as e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise
            else:
                break

    def shell_handler(self, message):
        """Dispatch shell messages to their handlers"""
        self.dprint(1, "received:", message)
        identities, msg = self.deserialize_wire_message(message)
        handler = getattr(self, "handle_" + msg["header"]["msg_type"], None)
        if handler is None:
            self.dprint(0, "unknown message type:", msg["header"]["msg_type"])
            return
        handler(msg, identities)

    def handle_execute_request(self, message, identities):
        """Handle execute request messages."""
        self.dprint(2, "Xonsh Kernel Executing:", pformat(message["content"]["code"]))
        # Start by sending busy signal
        content = {"execution_state": "busy"}
        self.send(self.iopub_stream, "status", content, parent_header=message["header"])

        # confirm the input that we are executing
        content = {
            "execution_count": self.execution_count,
            "code": message["content"]["code"],
        }
        self.send(
            self.iopub_stream, "execute_input", content, parent_header=message["header"]
        )

        # execute the code
        metadata = {
            "dependencies_met": True,
            "engine": self.session_id,
            "status": "ok",
            "started": datetime.datetime.now().isoformat(),
        }
        content = self.do_execute(parent_header=message["header"], **message["content"])
        self.send(
            self.shell_stream,
            "execute_reply",
            content,
            metadata=metadata,
            parent_header=message["header"],
            identities=identities,
        )
        self.execution_count += 1

        # once we are done, send a signal that we are idle
        content = {"execution_state": "idle"}
        self.send(self.iopub_stream, "status", content, parent_header=message["header"])

    def do_execute(
        self,
        code="",
        silent=False,
        store_history=True,
        user_expressions=None,
        allow_stdin=False,
        parent_header=None,
        **kwargs
    ):
        """Execute user code."""
        if len(code.strip()) == 0:
            return {
                "status": "ok",
                "execution_count": self.execution_count,
                "payload": [],
                "user_expressions": {},
            }
        shell = builtins.__xonsh__.shell
        hist = builtins.__xonsh__.history
        try:
            shell.default(code, self, parent_header)
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True

        if interrupted:
            return {"status": "abort", "execution_count": self.execution_count}

        rtn = 0 if (hist is None or len(hist) == 0) else hist.rtns[-1]
        if 0 < rtn:
            message = {
                "status": "error",
                "execution_count": self.execution_count,
                "ename": "",
                "evalue": str(rtn),
                "traceback": [],
            }
        else:
            message = {
                "status": "ok",
                "execution_count": self.execution_count,
                "payload": [],
                "user_expressions": {},
            }
        return message

    def _respond_in_chunks(self, name, s, chunksize=1024, parent_header=None):
        if s is None:
            return
        n = len(s)
        if n == 0:
            return
        lower = range(0, n, chunksize)
        upper = range(chunksize, n + chunksize, chunksize)
        for l, u in zip(lower, upper):
            response = {"name": name, "text": s[l:u]}
            self.send(
                self.iopub_socket, "stream", response, parent_header=parent_header
            )

    def handle_complete_request(self, message, identities):
        """Handles kernel info requests."""
        content = self.do_complete(
            message["content"]["code"], message["content"]["cursor_pos"]
        )
        self.send(
            self.shell_stream,
            "complete_reply",
            content,
            parent_header=message["header"],
            identities=identities,
        )

    def do_complete(self, code, pos):
        """Get completions."""
        shell = builtins.__xonsh__.shell
        line = code.split("\n")[-1]
        line = builtins.aliases.expand_alias(line)
        prefix = line.split(" ")[-1]
        endidx = pos
        begidx = pos - len(prefix)
        rtn, _ = self.completer.complete(prefix, line, begidx, endidx, shell.ctx)
        if isinstance(rtn, Set):
            rtn = list(rtn)
        message = {
            "matches": rtn,
            "cursor_start": begidx,
            "cursor_end": endidx,
            "metadata": {},
            "status": "ok",
        }
        return message

    def handle_kernel_info_request(self, message, identities):
        """Handles kernel info requests."""
        content = {
            "protocol_version": "5.0",
            "ipython_version": [1, 1, 0, ""],
            "language": self.language,
            "language_version": self.language_version,
            "implementation": self.implementation,
            "implementation_version": self.implementation_version,
            "language_info": self.language_info,
            "banner": self.banner,
        }
        self.send(
            self.shell_stream,
            "kernel_info_reply",
            content,
            parent_header=message["header"],
            identities=identities,
        )


if __name__ == "__main__":
    setup(
        shell_type="jupyter",
        env={"PAGER": "cat"},
        aliases={"less": "cat"},
        xontribs=["coreutils"],
        threadable_predictors={"git": predict_true, "man": predict_true},
    )
    if builtins.__xonsh__.commands_cache.is_only_functional_alias("cat"):
        # this is needed if the underlying system doesn't have cat
        # we supply our own, because we can
        builtins.aliases["cat"] = "xonsh-cat"
        builtins.__xonsh__.env["PAGER"] = "xonsh-cat"
    shell = builtins.__xonsh__.shell
    kernel = shell.kernel = XonshKernel()
    kernel.start()
