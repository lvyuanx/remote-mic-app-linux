import configparser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock
from sayall_linux.icons import asset_path,write_launcher
from sayall_linux.desktop_api import DesktopAPI

class IconTests(unittest.TestCase):
    def test_options_have_different_resources(self):
        self.assertNotEqual(asset_path('standard').read_bytes(),asset_path('faceted-duck').read_bytes())
    def test_switch_preserves_launcher_commands_and_user_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'base.desktop'
            base.write_text('[Desktop Entry]\nType=Application\nName=SayAll\nExec=sayall-linux --custom\nIcon=sayall-linux\n')
            launcher=write_launcher('faceted-duck',tmp,base)
            config=configparser.ConfigParser(interpolation=None);config.optionxform=str;config.read(launcher)
            self.assertEqual(config['Desktop Entry']['Icon'],'sayall-linux-duck')
            self.assertEqual(config['Desktop Entry']['Exec'],'sayall-linux --custom')
            write_launcher('standard',tmp,base)
            config.read(launcher)
            self.assertEqual(config['Desktop Entry']['Icon'],'sayall-linux')
    def test_bad_identifier_cannot_modify_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):write_launcher('../invalid',tmp)
            self.assertFalse((Path(tmp)/'applications/sayall-linux.desktop').exists())

class IconAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_native_icon_failure_rolls_back_without_saving_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=DesktopAPI(tmp)
            api.native=AsyncMock(side_effect=[RuntimeError('icon unavailable'),'standard'])
            with self.assertRaises(RuntimeError):await api.command('set_app_icon',{'identifier':'faceted-duck'})
            self.assertEqual(api.settings.get('icon','standard'),'standard')
            self.assertEqual(api.native.await_count,2)
    async def test_icon_selection_is_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=DesktopAPI(tmp);api.native=AsyncMock(return_value='faceted-duck')
            await api.command('set_app_icon',{'identifier':'faceted-duck'})
            reloaded=DesktopAPI(tmp)
            self.assertEqual(await reloaded.command('get_app_icon',{}),'faceted-duck')
