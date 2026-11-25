# Saved mappings had no effect

The 0.2.3 frontend saved mappings but its Linux backend had no physical input
listener or action executor. This was an unfinished platform port, not a user
configuration failure.

0.2.4 adds capture restricted to the selected paired Bluetooth remote with
VID 2717 / PID 32b8, verified from the device's sysfs identity. It does not open
ordinary keyboard event devices. udev uaccess rules grant the active desktop
session access to this remote and /dev/uinput. Original unmapped keys pass through;
mapped gestures replace the original action. All held outputs are reference
counted and released on stop, disconnect and exit. Linux kernel uinput is used
for compatibility with Wayland.

Validation:
- Actual selected remote left direction DOWN observed.
- Saved left→Escape mapping executed.
- A GTK widget in the user's Wayland session received Escape.
- Synthetic tests cover immediate paired shortcuts, suppression of singles for
  double/long gestures, cancellation on shutdown, reverse release ordering and
  overlapping modifier ownership.

Explicit holdRepeat, application launching/focus, macro execution and custom
shortcut capture remain outside this implementation; do not claim them tested.
