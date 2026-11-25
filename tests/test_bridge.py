import asyncio
import unittest
from sayall_linux.bridge import _connected
from sayall_linux.protocol import AUDIO, CONTROL, TRANSMIT, GET_CAPABILITIES

class Characteristic:
    properties = ['write']
class Services:
    def get_characteristic(self, uuid):
        return Characteristic() if uuid in (AUDIO, CONTROL, TRANSMIT) else None
class FakeClient:
    instance = None
    def __init__(self, address, disconnected_callback, timeout):
        FakeClient.instance = self
        self.services = Services()
        self.callbacks = {}
        self.writes = []
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def start_notify(self, uuid, callback): self.callbacks[uuid] = callback
    async def write_gatt_char(self, characteristic, data, response): self.writes.append(bytes(data))
    def emit(self, uuid, data): self.callbacks[uuid](None, data)
class Microphone:
    def __init__(self): self.data = []
    def push(self, data): self.data.append(data)

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_session(self):
        stop, mic, statuses = asyncio.Event(), Microphone(), []
        task = asyncio.create_task(_connected('AA', stop, mic, statuses.append, FakeClient))
        await asyncio.sleep(0.01)
        client = FakeClient.instance
        self.assertEqual(client.writes, [GET_CAPABILITIES])
        client.emit(CONTROL, bytes.fromhex('0b010002030004'))
        client.emit(CONTROL, b'\x08')
        client.emit(CONTROL, bytes.fromhex('04030207'))
        client.emit(AUDIO, bytes.fromhex('007f80ff'))
        client.emit(CONTROL, b'\x00')
        await asyncio.sleep(0.05)
        self.assertIn(b'\x0c\x00', client.writes)
        self.assertEqual(len(mic.data[0]), 16)
        self.assertTrue(any('正在接收语音' in text for text in statuses))
        stop.set()
        await asyncio.wait_for(task, 1)

    async def test_stop_while_streaming_sends_close(self):
        stop = asyncio.Event()
        task = asyncio.create_task(_connected('AA', stop, Microphone(), lambda _: None, FakeClient))
        await asyncio.sleep(0.01)
        client = FakeClient.instance
        client.emit(CONTROL, bytes.fromhex('0b010002030004'))
        client.emit(CONTROL, bytes.fromhex('04030207'))
        await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(task, 1)
        self.assertIn(b'\x0d\x07', client.writes)

    async def test_interruption_is_published_when_cancelled_mid_stream(self):
        events=[]
        stop=asyncio.Event()
        task=asyncio.create_task(_connected('AA',stop,Microphone(),lambda _:None,FakeClient,lambda kind,value:events.append(kind)))
        await asyncio.sleep(.01)
        client=FakeClient.instance
        client.emit(CONTROL,bytes.fromhex('0b010002030004'))
        client.emit(CONTROL,bytes.fromhex('04030207'))
        await asyncio.sleep(.03)
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        self.assertIn('start',events)
        self.assertEqual(events[-1],'interrupted')
