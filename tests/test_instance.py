import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from sayall_linux.instance import DesktopInstance

class InstanceTests(unittest.TestCase):
    def test_second_process_cannot_take_lock_and_exit_releases_it(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'XDG_RUNTIME_DIR':tmp}):
            first=DesktopInstance()
            self.assertTrue(first.acquire())
            result=subprocess.run([sys.executable,'-c','from sayall_linux.instance import DesktopInstance; instance=DesktopInstance(); print(instance.acquire())'],capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.strip(),'False')
            first.close()
            second=DesktopInstance()
            self.assertTrue(second.acquire())
            second.close()

    def test_repeat_launch_requests_activation_over_socket(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'XDG_RUNTIME_DIR':tmp}):
            first=DesktopInstance()
            self.assertTrue(first.acquire())
            first.ready()
            try:
                result=subprocess.run([sys.executable,'-c','from sayall_linux.instance import DesktopInstance; instance=DesktopInstance(); print(instance.acquire())'],capture_output=True,text=True,check=True)
                self.assertEqual(result.stdout.strip(),'False')
                self.assertTrue(first.receive_activation())
                self.assertFalse(first.receive_activation())
            finally:
                first.close()
            self.assertFalse(first.socket_path.exists())
