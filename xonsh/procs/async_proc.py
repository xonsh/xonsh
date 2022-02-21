import asyncio
import asyncio.subprocess as asp
import sys


class SubProcStreamProtocol(asp.SubprocessStreamProtocol):
    """store writes to streams"""


class XonshProcBase:
    """attributes and methods that are expected from a xonshProc implementation"""

    @property
    def pid(self):
        raise NotImplementedError


class AsyncProc(XonshProcBase):
    def __init__(
        self,
        args: "list[str]",
        loop=None,
        universal_newlines=False,
        stdin=None,
        stdout=None,
        stderr=None,
        **kwargs,
    ):
        # todo: check if unbuffered read work all the time
        kwargs["bufsize"] = 0

        self.is_text = universal_newlines
        if loop is None:
            loop = asyncio.get_event_loop_policy().get_event_loop()
        self.loop = loop
        self.stdin = stdin
        self.stdout = sys.stdout if stdout is None else stdout
        self.stderr = sys.stdout if stderr is None else stderr

        self.proc: asp.Process = self.loop.run_until_complete(
            self.get_proc(*args, **kwargs)
        )

    async def get_proc(
        self,
        program: str,
        *args,
        limit=2**16,
        **kwargs,
    ):
        """wrap ``create_subprocess_exec`` call"""
        protocol_factory = lambda: SubProcStreamProtocol(limit=limit, loop=self.loop)
        transport, protocol = await self.loop.subprocess_exec(
            protocol_factory,
            program,
            *args,
            stdin=self.stdin,
            stdout=self.stdout,
            stderr=self.stderr,
            **kwargs,
        )
        return asp.Process(transport, protocol, self.loop)

    @property
    def pid(self):
        return self.proc.pid

    def wait(self):
        if self.proc:
            self.loop.run_until_complete(self.proc.wait())

    @property
    def returncode(self):
        return self.proc.returncode


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
