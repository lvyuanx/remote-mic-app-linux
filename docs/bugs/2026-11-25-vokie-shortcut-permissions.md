# Vokie onboarding could not detect Right Alt

Environment: Ubuntu Wayland, Vokie 2.0.18-2165 installed from the official Linux
download. Onboarding remained on the shortcut test page.

Evidence before the fix:
- Vokie's input helper was running, but had only two accessible input devices.
- The physical keyboard and SayAll Virtual Input were not readable by the active
  desktop user.
- The package included `resources/linux/69-vokie-input.rules`, but no installed
  Vokie rule was present in `/etc/udev/rules.d` or `/usr/lib/udev/rules.d`.

Applied the setup instructions shipped in that rule: copied the official rule to
`/etc/udev/rules.d/69-vokie-input.rules`, copied the bundled uinput module-load
configuration, loaded uinput, reloaded udev and retriggered input/misc devices.
No Vokie account settings, databases, tokens or onboarding state were edited.

Readback after the fix: the active session could read the keyboard and SayAll's
virtual keyboard; the already-running Vokie helper reopened 16 input devices.
The user confirmed that the Right Alt test passed and the Continue button proceeded.
