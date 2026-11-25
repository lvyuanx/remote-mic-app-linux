# Remote audio worked but did not trigger Vokie

0.2.5 saved the user's Right Alt preference and displayed “automatically set”,
but did not emit the shortcut on ATVV voice-stream start/stop. The remote's
native HID F5 report (observed code 63) was also forwarded to the desktop, where
it could refresh an application or invalidate the intended voice chord.

0.2.6 connects confirmed ATVV stream events to the existing ref-counted uinput
output. Start presses the configured chord once, stop releases it. Disconnect,
stream failure, input stop, application exit and shortcut changes release held
keys. The selected remote's F5 reports are swallowed, without reading or
suppressing F5 on ordinary keyboards.

The status badge now requires a ready output backend and no longer equates a
saved preference with a working shortcut. Desktop microphone names are stable
across restarts; after the first upgrade the voice app must select the new
SayAll_Microphone once. Only reserved modules with this app's exact description
are reclaimed after an unclean shutdown.

Verification:
- Python tests cover one DOWN/UP pair, duplicate lifecycle events, config changes,
  disabled shortcuts, interruption cleanup, missing-device errors, and the F5
  report filter.
- Real PulseAudio/PipeWire test verified microphone identity across two starts.
- Frontend: 725 passed, 13 existing/platform-specific tests skipped.
- Backend: 33 passed.
- Vokie's running helper was verified to have the current SayAll virtual input
  device open (matching the device inode, not an obsolete descriptor).
- End-to-end Vokie activation and text input require the user's live test.
