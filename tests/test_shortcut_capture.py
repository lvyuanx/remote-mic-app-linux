import unittest
from sayall_linux.shortcut_capture import ShortcutCapture, key_from_name
from sayall_linux.input_mapping import InputController


class ShortcutCaptureTests(unittest.TestCase):
    def setUp(self):
        self.edges = []
        self.capture = ShortcutCapture(self.edges.append)

    def test_idle_typing_is_not_recorded_or_swallowed(self):
        self.assertFalse(self.capture.edge(38, 'a', True))
        self.assertFalse(self.capture.edge(38, 'a', False))
        self.assertEqual(self.edges, [])

    def test_chord_repeats_and_releases_keep_original_key_identity(self):
        self.assertEqual(self.capture.start(), [])
        for code, key, down in [(37,'left_control',True), (34,'oem4',True),
                                (34,'oem4',True), (34,None,False),
                                (37,'left_control',False)]:
            self.assertTrue(self.capture.edge(code,key,down))
        self.assertEqual(self.edges, [
            {'key':'left_control','isPressed':True}, {'key':'oem4','isPressed':True},
            {'key':'oem4','isPressed':False}, {'key':'left_control','isPressed':False}])

    def test_preheld_modifiers_are_released_before_recording_new_chord(self):
        self.capture.edge(37,'left_control',True)
        self.assertEqual(self.capture.start(), ['left_control'])
        self.assertFalse(self.capture.edge(38,'a',True))
        self.assertFalse(self.capture.edge(38,'a',False))
        self.assertFalse(self.capture.edge(37,'left_control',False))
        self.assertEqual(self.edges, [])
        self.assertTrue(self.capture.edge(56,'b',True))
        self.assertEqual(self.edges, [{'key':'b','isPressed':True}])

    def test_cancel_still_swallows_paired_release_and_then_restores_typing(self):
        self.capture.start()
        self.capture.edge(9,'escape',True)
        self.assertEqual(self.capture.stop(), {'wetypeVoice':'unknown'})
        self.assertTrue(self.capture.edge(9,'escape',True))
        self.assertTrue(self.capture.edge(9,'escape',False))
        self.assertFalse(self.capture.edge(38,'a',True))
        self.assertEqual(self.edges, [{'key':'escape','isPressed':True}])

    def test_focus_loss_clears_capture_without_recording_background_typing(self):
        self.capture.start()
        self.capture.edge(37,'left_control',True)
        self.capture.focus_lost()
        self.assertFalse(self.capture.active)
        self.assertEqual(self.capture.start(), [])
        self.capture.stop()
        self.capture.edge(38,'a',True)
        self.assertEqual(len(self.edges), 1)

    def test_restart_while_cancelled_modifier_is_held_waits_for_its_release(self):
        self.capture.start()
        self.capture.edge(37,'left_control',True)
        self.capture.stop()
        self.assertEqual(self.capture.start(), ['left_control'])
        self.assertTrue(self.capture.edge(37,'left_control',False))
        self.assertTrue(self.capture.edge(38,'a',True))
        self.assertEqual(self.edges, [
            {'key':'left_control','isPressed':True}, {'key':'a','isPressed':True}])

    def test_supported_gdk_names_are_executable_linux_keys(self):
        controller = InputController(lambda: {})
        for name, expected in [('Control_R','right_control'), ('bracketleft','oem4'),
                               ('KP_End','numpad1'), ('F12','f12'), ('a','a'),
                               ('Super_L','left_windows'), ('ISO_Level3_Shift','right_alt'),
                               ('5','digit5'), ('KP_Enter','numpad_enter')]:
            with self.subTest(name=name):
                self.assertEqual(key_from_name(name), expected)
                self.assertEqual(len(controller.chord_codes([expected])), 1)
        self.assertIsNone(key_from_name('not_a_key'))

    def test_second_capture_cannot_reset_a_chord_in_progress(self):
        self.capture.start()
        self.capture.edge(37,'left_control',True)
        with self.assertRaises(RuntimeError):self.capture.start()
        self.assertTrue(self.capture.edge(37,'left_control',False))
