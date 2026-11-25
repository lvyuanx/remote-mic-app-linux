import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sayall_linux.vokie import desktop_entry

class VokieDetectionTests(unittest.TestCase):
    def test_detects_public_desktop_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            apps=home/'.local/share/applications';apps.mkdir(parents=True)
            binary=home/'vokie';binary.write_text('');binary.chmod(0o755)
            entry=apps/'vokie.desktop'
            entry.write_text('[Desktop Entry]\nName=Vokie\nExec='+str(binary)+' %U\n')
            with patch('sayall_linux.vokie.Path.home',return_value=home):
                self.assertEqual(desktop_entry(),(entry,binary))
                entry.write_text('[Desktop Entry]\nName=Vokie\nHidden=true\nExec='+str(binary)+'\n')
                detected=desktop_entry()
                self.assertTrue(detected is None or detected[0]!=entry)
