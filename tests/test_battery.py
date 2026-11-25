import asyncio
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from sayall_linux.battery import monitor_battery, percentage
from sayall_linux.desktop_api import DesktopAPI

class BatteryTests(unittest.IsolatedAsyncioTestCase):
    def test_zero_is_a_known_level_and_invalid_values_stay_unknown(self):
        self.assertEqual(percentage(0), 0)
        self.assertEqual(percentage(100), 100)
        for value in (None, -1, 101, True, '100', 50.5):
            self.assertIsNone(percentage(value))

    async def test_read_failure_recovers_without_ending_session(self):
        updates=[]
        with patch('sayall_linux.battery.read_battery', AsyncMock(side_effect=[RuntimeError('temporary'),100,100,99])):
            task=asyncio.create_task(monitor_battery(object(), lambda *args: updates.append(args), interval=.01))
            try:
                for _ in range(30):
                    if len(updates)==2: break
                    await asyncio.sleep(.005)
                self.assertEqual(updates,[('battery',100),('battery',99)])
            finally:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)

    async def test_snapshot_carries_level_and_disconnect_clears_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=DesktopAPI(tmp)
            api.observe('battery',100)
            self.assertEqual(api.snapshot()['platform']['connection']['batteryLevel'],100)
            await api.disconnect()
            self.assertIsNone(api.connection['batteryLevel'])
