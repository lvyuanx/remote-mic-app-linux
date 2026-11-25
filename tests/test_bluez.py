import unittest
from unittest.mock import AsyncMock, patch
from bleak.backends.device import BLEDevice
from sayall_linux.bluez import resolve_device

class CachedDeviceTests(unittest.IsolatedAsyncioTestCase):
    async def test_connected_remote_uses_cached_object_without_advertising(self):
        device=BLEDevice('00:11:22:33:44:55','Remote',{'path':'/org/bluez/hci0/dev_test','props':{'Paired':True,'Connected':True}})
        with patch('sayall_linux.bluez.cached_devices',AsyncMock(return_value=[device])):
            self.assertIs(await resolve_device('00:11:22:33:44:55'),device)
    async def test_unknown_remote_retains_discovery_path(self):
        with patch('sayall_linux.bluez.cached_devices',AsyncMock(return_value=[])):
            self.assertEqual(await resolve_device('00:11:22:33:44:55'),'00:11:22:33:44:55')
