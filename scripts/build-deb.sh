#!/bin/sh
set -eu
umask 022
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=0.2.8
if [ ! -f "$PROJECT_DIR/frontend/dist/index.html" ]; then
    echo 'Build the frontend first: ./scripts/build-frontend.sh' >&2
    exit 1
fi
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT HUP INT TERM
STAGE="$BUILD_DIR/sayall-linux"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/lib/sayall-linux/sayall_linux" \
    "$STAGE/usr/lib/udev/rules.d" "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/scalable/apps" \
    "$STAGE/usr/share/doc/sayall-linux" "$PROJECT_DIR/dist"
install -m 755 "$PROJECT_DIR/packaging/postinst" "$STAGE/DEBIAN/postinst"
install -m 644 "$PROJECT_DIR/packaging/70-sayall-input.rules" "$STAGE/usr/lib/udev/rules.d/"
install -m 644 "$PROJECT_DIR"/sayall_linux/*.py "$STAGE/usr/lib/sayall-linux/sayall_linux/"
cp -r "$PROJECT_DIR/frontend/dist" "$STAGE/usr/lib/sayall-linux/sayall_linux/web"
install -m 644 "$PROJECT_DIR/ATTRIBUTION.md" "$STAGE/usr/share/doc/sayall-linux/"
install -m 644 "$PROJECT_DIR/PORTING.md" "$STAGE/usr/share/doc/sayall-linux/"
install -m 644 "$PROJECT_DIR/frontend/UPSTREAM_THIRD_PARTY_NOTICES.md" "$STAGE/usr/share/doc/sayall-linux/"
install -m 644 "$PROJECT_DIR/packaging/sayall-linux.desktop" "$STAGE/usr/share/applications/"
install -m 644 "$PROJECT_DIR/packaging/sayall-linux-duck.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$PROJECT_DIR/packaging/sayall-linux.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$PROJECT_DIR/README.md" "$STAGE/usr/share/doc/sayall-linux/README.md"
install -m 644 "$PROJECT_DIR/LICENSE" "$STAGE/usr/share/doc/sayall-linux/copyright"
cat > "$STAGE/usr/bin/sayall-linux" <<'LAUNCHER'
#!/bin/sh
PYTHONPATH="/usr/lib/sayall-linux${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
exec /usr/bin/python3 -m sayall_linux "$@"
LAUNCHER
chmod 755 "$STAGE/usr/bin/sayall-linux"
cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: sayall-linux
Version: $VERSION
Section: sound
Priority: optional
Architecture: all
Maintainer: SayAll Linux contributors
Depends: python3 (>= 3.10), python3-evdev, python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, python3-bleak (>= 0.21), python3-bleak (<< 3), bluez, pulseaudio-utils
Description: Bluetooth remote microphone bridge for Ubuntu
 Connect compatible ATVV Bluetooth remotes and expose their audio as a
 temporary PulseAudio or PipeWire microphone. This is an unofficial port.
CONTROL
dpkg-deb --root-owner-group --build "$STAGE" "$PROJECT_DIR/dist/sayall-linux_${VERSION}_all.deb"
