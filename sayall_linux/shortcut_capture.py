"""Shortcut recording from focused GTK events, without global keyboard access."""


def key_from_name(name):
    """Map an unmodified GDK keysym name to the frontend's key vocabulary."""
    aliases = {
        'Control_L': 'left_control', 'Control_R': 'right_control',
        'Shift_L': 'left_shift', 'Shift_R': 'right_shift',
        'Alt_L': 'left_alt', 'Alt_R': 'right_alt',
        'ISO_Level3_Shift': 'right_alt',
        'Super_L': 'left_windows', 'Super_R': 'right_windows',
        'Meta_L': 'left_windows', 'Meta_R': 'right_windows',
        'Return': 'enter', 'Escape': 'escape', 'space': 'space',
        'Tab': 'tab', 'ISO_Left_Tab': 'tab', 'BackSpace': 'backspace',
        'Left': 'left', 'Right': 'right', 'Up': 'up', 'Down': 'down',
        'Home': 'home', 'End': 'end', 'Prior': 'page_up', 'Next': 'page_down',
        'Insert': 'insert', 'Delete': 'delete', 'Menu': 'apps',
        'semicolon': 'oem1', 'equal': 'oem_plus', 'comma': 'oem_comma',
        'minus': 'oem_minus', 'period': 'oem_period', 'slash': 'oem2',
        'grave': 'oem3', 'bracketleft': 'oem4', 'backslash': 'oem5',
        'bracketright': 'oem6', 'apostrophe': 'oem7',
        'KP_Enter': 'numpad_enter', 'KP_Add': 'numpad_add',
        'KP_Subtract': 'numpad_subtract', 'KP_Multiply': 'numpad_multiply',
        'KP_Divide': 'numpad_divide', 'KP_Decimal': 'numpad_decimal',
        'KP_Delete': 'numpad_decimal', 'Num_Lock': 'numlock',
        'KP_Insert': 'numpad0', 'KP_End': 'numpad1', 'KP_Down': 'numpad2',
        'KP_Next': 'numpad3', 'KP_Left': 'numpad4', 'KP_Begin': 'numpad5',
        'KP_Right': 'numpad6', 'KP_Home': 'numpad7', 'KP_Up': 'numpad8',
        'KP_Prior': 'numpad9',
        'XF86AudioMute': 'volume_mute', 'XF86AudioLowerVolume': 'volume_down',
        'XF86AudioRaiseVolume': 'volume_up', 'XF86AudioPlay': 'media_play_pause',
        'XF86AudioNext': 'media_next_track', 'XF86AudioPrev': 'media_previous_track',
    }
    if name in aliases:
        return aliases[name]
    if name and len(name) == 1 and name.isascii():
        if name.isalpha(): return name.lower()
        if name.isdigit(): return 'digit' + name
    if name and name.startswith('KP_') and name[3:] in tuple('0123456789'):
        return 'numpad' + name[3:]
    if name and name.startswith('F') and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return name.lower()
    return None


class ShortcutCapture:
    def __init__(self, report):
        self.report = report
        self.active = False
        self.pressed = {}
        self.preheld = set()
        self.swallowed = {}

    def start(self):
        if self.active:
            raise RuntimeError('快捷键录入已在进行中')
        self.active = True
        self.preheld = set(self.pressed)
        return list(dict.fromkeys(key for key in self.pressed.values() if key))

    def stop(self):
        self.active = False
        self.preheld.clear()
        # A cancelled key's release must not leak into WebKit without its press.
        return {'wetypeVoice': 'unknown'}

    def focus_lost(self):
        self.stop()
        self.pressed.clear()
        self.swallowed.clear()

    def edge(self, hardware_code, key, is_pressed):
        repeated = is_pressed and hardware_code in self.pressed
        if is_pressed:
            self.pressed.setdefault(hardware_code, key)
        else:
            key = self.pressed.pop(hardware_code, key)
        if hardware_code in self.swallowed:
            key = self.swallowed[hardware_code]
            if not is_pressed:
                del self.swallowed[hardware_code]
                was_preheld = hardware_code in self.preheld
                self.preheld.discard(hardware_code)
                if self.active and key and not was_preheld:
                    self.report({'key': key, 'isPressed': False})
            return True
        if hardware_code in self.preheld:
            if not is_pressed: self.preheld.discard(hardware_code)
            return False
        if not self.active or self.preheld:
            return False
        if is_pressed and not repeated:
            self.swallowed[hardware_code] = key
            if key: self.report({'key': key, 'isPressed': True})
            return True
        return False
