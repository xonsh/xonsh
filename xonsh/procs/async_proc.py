import asyncio


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
