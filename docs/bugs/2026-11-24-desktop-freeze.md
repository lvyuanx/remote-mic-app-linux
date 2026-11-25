# Linux desktop freeze in WebKit GC

Observed in installed 0.2.2 on Ubuntu 26.04. The UI stopped responding while the
button-action editor was visible; SIGTERM and duplicate-launch activation could
not complete. Bluetooth remained connected, so a voice failure was not the trigger.

Live gdb evidence (captured before terminating the hung instance):

- UI thread: `JSC::Heap::acquireAccessSlow` → condition variable wait.
- Collector thread: `WTF::Thread::suspend` → semaphore wait.
- The application registered `GLib.unix_signal_add(SIGUSR1, present)` for
  duplicate-launch activation, replacing a signal used by JavaScriptCore GC.

WebKit documents its use of SIGUSR1 for thread suspension:
https://bugs.webkit.org/show_bug.cgi?id=223069
https://bugs.webkit.org/show_bug.cgi?id=220641

Fix: keep the existing per-user file lock; send a `present` message over an
owner-only Unix-domain socket, handled by the GTK main loop. The application no
longer installs a SIGUSR1 handler or sends SIGUSR1. No changes to WebKit GC or
system-wide WebKit settings are required.

Verification:

- Injecting the previous SIGUSR1 handler in the real desktop host reproduced
  the freeze under IPC/GC pressure (30-second external watchdog timeout).
- With socket activation, the same host sustained 154 successful UI heartbeats
  and about 7,700 IPC messages, kept the button editor open, and shut down cleanly.
- Python regression tests: 17 passed, including second-process activation over
  the socket and file-lock cleanup.

The reproducible GUI regression is `scripts/stress-desktop.py`; run in an isolated
XDG_CONFIG_HOME with an external timeout (35 seconds). Set SAYALL_STRESS_BLUETOOTH=1
only when the user's paired remote is available. It edits a mapping in memory
but does not press Save. User configuration is isolated by the test runner.

Installed 0.2.3 verification also passed: 153 UI heartbeat responses under the
same load, repeated-launch socket activation, button editor preset selection,
Bluetooth `ready`, battery level `100`, and clean shutdown. The test used an
isolated configuration directory and did not save changes to the user's mappings.
