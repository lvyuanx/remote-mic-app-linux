import tempfile
import unittest
from evdev import ecodes as e
from sayall_linux.desktop_api import DesktopAPI
from sayall_linux.voice_hotkey import VoiceHotkey
from sayall_linux.input_mapping import InputController

class Output:
    def __init__(self):self.events=[]
    def write(self,*event):self.events.append(event)
    def syn(self):pass

class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.settings={'hotkey':{'keys':['right_alt']}}
        self.input=InputController(lambda:self.settings)
        self.input.ui=Output()
        self.voice=VoiceHotkey(lambda:self.settings,self.input)
    def test_stream_has_one_paired_hotkey_even_with_duplicate_events(self):
        self.voice.begin();self.voice.begin()
        self.voice.end('stop');self.voice.end('stop')
        self.assertEqual(self.input.ui.events,[(e.EV_KEY,e.KEY_RIGHTALT,1),(e.EV_KEY,e.KEY_RIGHTALT,0)])
    def test_interrupt_releases_the_original_chord_after_config_change(self):
        self.voice.begin()
        self.settings['hotkey']={'keys':['left_alt']}
        self.voice.end('disconnect')
        self.assertEqual(self.input.ui.events[-1],(e.EV_KEY,e.KEY_RIGHTALT,0))
        self.assertFalse(self.input.key_counts)
    def test_disabled_hotkey_does_not_inject(self):
        self.settings['hotkey']=None
        self.assertFalse(self.voice.begin())
        self.voice.end('stop')
        self.assertEqual(self.input.ui.events,[])
    def test_missing_virtual_device_is_an_explicit_failure(self):
        self.input.ui=None
        with self.assertRaisesRegex(RuntimeError,'未就绪'):self.voice.begin()
        self.voice.end('stop')
    def test_remote_voice_report_is_swallowed_without_touching_keyboard_f5(self):
        self.assertTrue(self.input.consume_voice_key(e.KEY_F5,1))
        self.assertTrue(self.input.consume_voice_key(e.KEY_F5,0))
        self.assertFalse(self.input.consume_voice_key(e.KEY_LEFT,1))
        self.assertEqual(self.input.ui.events,[])

class APIIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_interrupted_session_releases_modifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=DesktopAPI(tmp)
            api.settings['hotkey']={'keys':['right_alt']}
            api.input.ui=Output()
            api.observe('start',None)
            api.observe('interrupted',None)
            self.assertEqual(api.input.ui.events,[(e.EV_KEY,e.KEY_RIGHTALT,1),(e.EV_KEY,e.KEY_RIGHTALT,0)])
            api.input.ui=None
            await api.disconnect()
