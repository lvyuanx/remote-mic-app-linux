"""Battery Service readback; best-effort and independent of the voice stream."""
import asyncio
import logging
from dbus_fast import Message
from dbus_fast.aio import MessageBus
from dbus_fast.constants import BusType, MessageType

BATTERY_LEVEL = '00002a19-0000-1000-8000-00805f9b34fb'
log = logging.getLogger('sayall.connection')

def percentage(value):
    return value if type(value) is int and 0 <= value <= 100 else None

async def read_battery(client):
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        reply = await bus.call(Message(destination='org.bluez', path='/', interface='org.freedesktop.DBus.ObjectManager', member='GetManagedObjects'))
        if reply.message_type != MessageType.ERROR:
            for interfaces in reply.body[0].values():
                props = interfaces.get('org.bluez.Device1', {})
                if getattr(props.get('Address'), 'value', '').lower() != client.address.lower():
                    continue
                battery = interfaces.get('org.bluez.Battery1', {})
                level = percentage(getattr(battery.get('Percentage'), 'value', None))
                if level is not None:
                    return level
    finally:
        bus.disconnect()
    # BlueZ normally exposes Battery1. Some adapters/daemon configurations do
    # not, so use the standard GATT Battery Level characteristic if available.
    char = client.services.get_characteristic(BATTERY_LEVEL)
    if char and 'read' in char.properties:
        data = await client.read_gatt_char(char)
        if len(data) == 1:
            return percentage(data[0])
    return None

async def monitor_battery(client, observer, interval=60):
    previous = None
    while True:
        try:
            value = await asyncio.wait_for(read_battery(client), timeout=5)
            if value is not None and value != previous:
                previous = value
                observer('battery', value)
                log.info('event=battery_updated level=%s', value)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # A battery query must never terminate or reconnect a voice session.
            log.info('event=battery_read_failed error_type=%s', type(exc).__name__)
        await asyncio.sleep(interval)
