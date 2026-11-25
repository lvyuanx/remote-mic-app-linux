"""Resolve paired BlueZ devices without requiring fresh BLE advertisements."""
import logging
from bleak.backends.device import BLEDevice
from dbus_fast import Message
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageType

log = logging.getLogger('sayall.connection')

async def cached_devices():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        reply = await bus.call(Message(destination='org.bluez', path='/', interface='org.freedesktop.DBus.ObjectManager', member='GetManagedObjects'))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError('无法读取系统蓝牙设备：' + str(reply.error_name))
        devices = []
        for path, interfaces in reply.body[0].items():
            if 'org.bluez.Device1' not in interfaces:
                continue
            props = {key: value.value for key, value in interfaces['org.bluez.Device1'].items()}
            if props.get('Address'):
                devices.append(BLEDevice(props['Address'], props.get('Name') or props.get('Alias'), {'path': path, 'props': props}))
        return devices
    finally:
        bus.disconnect()

async def resolve_device(address):
    for device in await cached_devices():
        if device.address.lower() == address.lower():
            log.info('event=device_resolved source=bluez_cache paired=%s connected=%s', device.details['props'].get('Paired', False), device.details['props'].get('Connected', False))
            return device
    # An as-yet-unpaired device may need a fresh advertisement. Bleak handles
    # this path; already paired peripherals use their cached object above.
    log.info('event=device_resolved source=advertisement_required')
    return address
