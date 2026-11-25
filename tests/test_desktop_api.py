import tempfile
import unittest
from sayall_linux.desktop_api import DesktopAPI

class DesktopAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.api=DesktopAPI(self.temp.name)
        self.api.input.candidates=lambda:[]
    async def asyncTearDown(self):
        await self.api.disconnect()
        self.temp.cleanup()
    async def test_settings_survive_restart(self):
        await self.api.command('set_theme_preference',{'preference':'dark'})
        mappings={'enabled':True,'actions':{'button.ok':{'single':{'type':'disabled'}}}}
        await self.api.command('save_button_mappings',{'mappings':mappings})
        reloaded=DesktopAPI(self.temp.name)
        self.assertEqual(await reloaded.command('get_theme_preference',{}),'dark')
        self.assertEqual(await reloaded.command('get_button_mappings',{}),mappings)
    async def test_no_preview_activity(self):
        usage=await self.api.command('get_usage_profile',{})
        self.assertEqual(usage['totalButtonPresses'],0)
        self.assertEqual(await self.api.command('get_combined_actions',{}),{'formatVersion':1,'definitions':[]})
        self.assertEqual(self.api.snapshot()['platform']['platform'],'linux')
        self.assertTrue((await self.api.command('get_capture_support',{}))['available'])
    async def test_unsupported_actions_fail_explicitly(self):
        with self.assertRaisesRegex(RuntimeError,'监听尚未就绪'):
            await self.api.command('test_button_mapping',{})
    async def test_macro_save_and_referenced_delete(self):
        definition={'macroId':'one','steps':[]}
        await self.api.command('save_macro',{'definition':definition})
        self.assertEqual((await self.api.command('get_combined_actions',{}))['definitions'],[definition])
        self.api.save('mappings',{'actions':{'button.ok':{'single':{'type':'run_macro','macroId':'one'}}}})
        with self.assertRaises(ValueError): await self.api.command('delete_macro',{'macroId':'one'})
