"""One desktop host per user, with a local socket for window activation.

Do not use SIGUSR1: JavaScriptCore reserves it for suspending GC threads.
"""
import fcntl
import os
from pathlib import Path
import socket

class DesktopInstance:
    def __init__(self):
        base = Path(os.environ.get('XDG_RUNTIME_DIR', Path.home()/'.cache'))/'sayall-linux'
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.socket_path = base/'desktop.sock'
        self.file = open(base/'desktop.lock', 'a+')
        self.acquired = False
        self.socket = None

    def acquire(self):
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as peer:
                    peer.settimeout(.5)
                    peer.sendto(b'present\n', str(self.socket_path))
            except OSError:
                # The owner may still be starting; it will show its first window.
                pass
            self.file.close()
            return False
        self.file.seek(0)
        self.file.truncate()
        self.file.flush()
        self.acquired = True
        return True

    def ready(self):
        if self.socket_path.exists():
            self.socket_path.unlink()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.socket.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        self.socket.setblocking(False)
        self.file.write(str(os.getpid()))
        self.file.flush()

    def receive_activation(self):
        try:
            return self.socket.recv(32) == b'present\n'
        except BlockingIOError:
            return False

    def close(self):
        if self.acquired:
            if self.socket:
                self.socket.close()
                self.socket_path.unlink(missing_ok=True)
                self.socket = None
            fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()
            self.acquired = False
