"""BlueZ BLE connection and ATVV session lifecycle."""
import asyncio
import time
import struct
import logging
import re
from .bluez import cached_devices, resolve_device
from .battery import monitor_battery

log = logging.getLogger("sayall.connection")

def safe_error(exc):
    text = str(exc) or type(exc).__name__
    text = re.sub(r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", "[遥控器]", text)
    text = re.sub(r"/org/bluez/[^\s,\"\']+", "[蓝牙设备]", text)
    return type(exc).__name__ + ": " + text
from .audio import VirtualMicrophone
from .protocol import AUDIO, CONTROL, TRANSMIT, GET_CAPABILITIES, Pipeline

async def scan(timeout=6):
    from bleak import BleakScanner
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    devices = [(device.name, device.address) for device in await cached_devices() if device.name and device.details['props'].get('Paired')]
    for device, adv in found.values():
        name = device.name or adv.local_name or ''
        if name:
            devices.append((name, device.address))
    return sorted(set(devices), key=lambda item: (not any(x in item[0].lower() for x in ('remote', 'rc001', 'rc003', '遥控')), item[0].lower()))

async def run(address, stop, status=print, observer=None, gain_provider=None, microphone_name=None):
    from bleak import BleakClient
    microphone = VirtualMicrophone(microphone_name)
    await microphone.start()
    status('虚拟麦克风已创建：SayAll_Microphone')
    if observer: observer('microphone', microphone.source)
    try:
        delay = 2
        while not stop.is_set():
            try:
                target = await resolve_device(address)
                if stop.is_set(): break
                if observer:
                    observer('connecting', None)
                    if getattr(target, 'name', None): observer('device', target.name)
                await _connected(target, stop, microphone, status, BleakClient, observer, gain_provider)
                delay = 2
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if stop.is_set():
                    break
                error = safe_error(exc)
                log.warning('event=connection_failed retry_seconds=%s error=%s', delay, error)
                status(f'连接中断：{error}；{delay} 秒后重试')
                try:
                    await asyncio.wait_for(stop.wait(), delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2, 30)
    finally:
        await microphone.close()
        status('已断开，虚拟麦克风已移除')

async def _connected(address, stop, microphone, status, client_type, observer=None, gain_provider=None):
    events = asyncio.Queue(maxsize=512)
    disconnected = asyncio.Event()
    def callback(kind):
        def receive(_, data):
            try:
                events.put_nowait((kind, bytes(data)))
            except asyncio.QueueFull:
                # Losing protocol events can corrupt decoder state. Reconnect cleanly.
                disconnected.set()
        return receive
    def on_disconnect(_):
        disconnected.set()
    status('正在连接遥控器…')
    log.info('event=connect_started')
    async with client_type(address, disconnected_callback=on_disconnect, timeout=20) as client:
        battery_task = None
        try:
            transmit = client.services.get_characteristic(TRANSMIT)
            if not transmit or not client.services.get_characteristic(AUDIO) or not client.services.get_characteristic(CONTROL):
                raise RuntimeError('设备没有 ATVV 语音服务，请确认型号及蓝牙配对')
            response = 'write' in transmit.properties
            async def write(data):
                await client.write_gatt_char(transmit, data, response=response)
            log.info('event=gatt_connected')
            await client.start_notify(AUDIO, callback('audio'))
            await client.start_notify(CONTROL, callback('control'))
            log.info('event=notifications_subscribed')
            await write(GET_CAPABILITIES)
            log.info('event=capabilities_requested')
            pipeline = Pipeline()
            ready_deadline = time.monotonic() + 10
            last_audio = 0
            next_extend = 0
            opened = False
            session_samples = 0
            while not stop.is_set() and not disconnected.is_set():
                try:
                    kind, data = await asyncio.wait_for(events.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    kind, data = None, None
                now = time.monotonic()
                if kind == 'control':
                    event = pipeline.control(data)
                    if observer and event in ('ready', 'start', 'stop'):
                        observer(event, pipeline.capabilities if event == 'ready' else None)
                    if event == 'ready':
                        if observer and battery_task is None:
                            battery_task = asyncio.create_task(monitor_battery(client, observer))
                        log.info('event=voice_ready sample_rate=16000 frame_size=%s', pipeline.capabilities.frame_size)
                        status('已连接。按住遥控器语音键说话')
                    elif event == 'open' and not opened and not pipeline.streaming:
                        await write(pipeline.capabilities.open_command())
                        opened = True
                    elif event == 'start':
                        session_samples=0
                        log.info('event=voice_stream_started session=%s',pipeline.session_id)
                        opened = True
                        last_audio, next_extend = now, now + 2.5
                        status('正在接收语音…')
                    elif event == 'stop':
                        log.info('event=voice_stream_stopped decoded_samples=%s',session_samples)
                        opened = False
                        status('已连接。按住遥控器语音键说话')
                elif kind == 'audio' and pipeline.streaming:
                    last_audio = now
                    pcm = pipeline.audio(data)
                    if pcm and gain_provider:
                        gain = 10 ** (max(0, min(24, gain_provider())) / 20)
                        samples = struct.unpack('<' + 'h'*(len(pcm)//2), pcm)
                        pcm = struct.pack('<' + 'h'*len(samples), *(max(-32768,min(32767,round(sample*gain))) for sample in samples))
                    session_samples += len(pcm)//2
                    microphone.push(pcm)
                    if observer: observer('samples', len(pcm)//2)
                if not pipeline.capabilities and now > ready_deadline:
                    raise RuntimeError('设备未响应能力协商')
                if pipeline.streaming and now - last_audio > 5:
                    if pipeline.capabilities.version >= 0x100:
                        await write(bytes((0x0d, pipeline.session_id)))
                    else:
                        await write(bytes((0x0d,)))
                    raise RuntimeError('语音流超时')
                if pipeline.streaming and now >= next_extend:
                    if pipeline.capabilities.version >= 0x100:
                        await write(bytes((0x0e, pipeline.session_id)))
                    next_extend = now + 2.5
            if disconnected.is_set() and not stop.is_set():
                raise RuntimeError('蓝牙连接已断开或接收队列溢出')
            if pipeline.streaming:
                try:
                    command = bytes((0x0d, pipeline.session_id)) if pipeline.capabilities.version >= 0x100 else bytes((0x0d,))
                    await write(command)
                except Exception:
                    pass
        finally:
            if observer:observer('interrupted',None)
            if battery_task is not None:
                battery_task.cancel()
                await asyncio.gather(battery_task, return_exceptions=True)
