import unittest

from global_hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    GlobalHotkeyManager,
    parse_hotkey_string,
)


class GlobalHotkeyTests(unittest.TestCase):
    def test_parse_hotkey_string(self):
        mods, vk = parse_hotkey_string("Ctrl+Alt+S")
        self.assertEqual(mods, MOD_NOREPEAT | MOD_CONTROL | MOD_ALT)
        self.assertEqual(vk, 0x53)  # 'S'

        mods2, vk2 = parse_hotkey_string("Win+Shift+C")
        self.assertEqual(mods2, MOD_NOREPEAT | MOD_WIN | MOD_SHIFT)
        self.assertEqual(vk2, 0x43)  # 'C'

    def test_hotkey_manager_initialization(self):
        manager = GlobalHotkeyManager()
        self.assertEqual(manager.hotkey_id, 0x5943)
        self.assertFalse(manager._registered)


if __name__ == "__main__":
    unittest.main()
