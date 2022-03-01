import asyncio
import os

import xonsh.lazyimps as xli
import xonsh.platform as xp
from xonsh.procs.utils import _safe_pipe_properties, safe_open


class StreamReader(asyncio.Protocol):
    """much like StreamReader and StreamProtocol merged"""

    def __init__(self, loop: "asyncio.AbstractEventLoop | None" = None):
        self._buffer = bytearray()
        self.loop = loop or asyncio.get_event_loop_policy().get_event_loop()
        self.exited = asyncio.Future(loop=loop)
        self._eof = False

    def connection_made(self, transport):
        self.transport = transport
        super().connection_made(transport)

    def data_received(self, data):
        self._buffer.extend(data)
        super().data_received(data)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        self.exited.set_result(True)
        self._eof = True

    async def _start(self, pipe):
        await self.loop.connect_read_pipe(lambda: self, pipe)

    def start(self, pipe):
        self.loop.run_until_complete(self._start(pipe))

    async def _read(self, timeout=0.0):
        """send data received so far. Only blocks when data is yet to be arrived for the maximum timeout"""
        waited = False
        while True:
            data = bytes(self._buffer)
            if data:
                self._buffer.clear()
                break

            if self._eof or waited:
                break

            # wait for sometime to data to be received
            await asyncio.sleep(timeout)
            waited = True
        return data

    def read(self, timeout=0.0):
        return self.loop.run_until_complete(self._read(timeout))

    async def _wait(self):
        """block until the proc is exited"""
        await self.exited

    def wait(self):
        self.loop.run_until_complete(self.exited)


class StreamHandler:
    def __init__(self, capture=False, tee=False, use_tty=False) -> None:
        self.capture = capture
        self.tee = tee

        if tee and use_tty:
            # it is two-way
            parent, child = xli.pty.openpty()
            _safe_pipe_properties(child, use_tty=use_tty)
            _safe_pipe_properties(parent, use_tty=use_tty)
        elif xp.ON_WINDOWS:
            # windows proactorEventloop needs named pipe
            from asyncio.windows_utils import pipe

            parent, child = pipe()
        else:
            # one-way pipe
            parent, child = os.pipe()

        self.write_bin = safe_open(
            child,
            "wb",
        )
        read_bin = safe_open(parent, "rb")

        # start async reading
        self.reader = StreamReader()
        self.reader.start(read_bin)

    def close(self):
        self.write_bin.close()
