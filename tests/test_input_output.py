import unittest
from unittest.mock import patch
from sayall_linux.input_mapping import InputController
try:
    from evdev import ecodes as e
except ImportError:
    e=None
class Output:
    def __init__(self):self.events=[]
    def write(self,*event):self.events.append(event)
    def syn(self):pass

@unittest.skipIf(e is None,'requires python3-evdev')
class OutputTests(unittest.TestCase):
    def setUp(self):
        self.controller=InputController(lambda:{})
        self.controller.ui=Output()
    def test_chord_releases_in_reverse_order(self):
        self.controller.execute({'type':'shortcut','chord':{'keys':['control','c']}},'pulse','one')
        self.assertEqual(self.controller.ui.events,[(e.EV_KEY,e.KEY_LEFTCTRL,1),(e.EV_KEY,e.KEY_C,1),(e.EV_KEY,e.KEY_C,0),(e.EV_KEY,e.KEY_LEFTCTRL,0)])
    def test_overlapping_shortcuts_do_not_release_shared_modifier(self):
        for owner,key in [('one','c'),('two','v')]:
            self.controller.execute({'type':'shortcut','chord':{'keys':['control',key]}},'begin',owner)
        self.controller.release('one')
        self.assertNotIn((e.EV_KEY,e.KEY_LEFTCTRL,0),self.controller.ui.events)
        self.controller.release('two')
        self.assertEqual(self.controller.ui.events[-1],(e.EV_KEY,e.KEY_LEFTCTRL,0))
    def test_unknown_key_fails_before_pressing_modifiers(self):
        with self.assertRaises(ValueError):self.controller.execute({'type':'shortcut','chord':{'keys':['control','not_a_key']}},'pulse','one')
        self.assertEqual(self.controller.ui.events,[])
