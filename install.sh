#!/usr/bin/env bash
# guncon3-linux installer: https://github.com/leandrolalanne/guncon3-linux
#
#   ./install.sh               install (or update), enable the service, offer calibration
#   ./install.sh --no-service  install, but do not start the driver with your session
#   ./install.sh --no-udev     skip the udev rule (it needs sudo; install it yourself)
#   ./install.sh --uninstall   remove everything (the calibration stays unless --purge)
#
# Installs to ~/.local/share/guncon3-linux, a user service (systemd --user) and one
# udev rule. Needs python3 and libusb-1.0; downloads pyusb and python-libevdev from
# PyPI (no pip needed) and checks their SHA-256.
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DEST="$HOME/.local/share/guncon3-linux"
UNIT_DIR="$HOME/.config/systemd/user"
RULE=/etc/udev/rules.d/70-guncon3.rules
CAL="$HOME/.config/guncon3"

service=1 udev=1 uninstall=0 purge=0
for a in "$@"; do
  case "$a" in
    --no-service) service=0 ;;
    --no-udev) udev=0 ;;
    --uninstall) uninstall=1 ;;
    --purge) uninstall=1; purge=1 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $a (try --help)"; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*"; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
gun_present() { [ -n "$(grep -l '^0b9a$' /sys/bus/usb/devices/*/idVendor 2>/dev/null | while read -r f; do d=${f%/idVendor}; [ "$(cat "$d/idProduct")" = 0800 ] && echo y; done)" ]; }

if [ "$uninstall" = 1 ]; then
  say "Removing guncon3-linux"
  if have systemctl; then systemctl --user disable --now guncon3.service 2>/dev/null || true; fi
  rm -f "$UNIT_DIR/guncon3.service"
  have systemctl && systemctl --user daemon-reload 2>/dev/null || true
  rm -rf "$DEST"
  if [ "$udev" = 1 ] && [ -f "$RULE" ]; then
    say "Removing $RULE (sudo)"
    sudo rm -f "$RULE" && sudo udevadm control --reload || warn "Could not remove $RULE; remove it by hand."
  fi
  [ "$purge" = 1 ] && rm -rf "$CAL" && say "Calibration removed."
  say "Done."
  exit 0
fi

# ------------------------------------------------------------------ checks
have python3 || die "python3 is needed."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' || die "Python 3.8 or newer is needed."
libs="$(ldconfig -p 2>/dev/null || /sbin/ldconfig -p 2>/dev/null || true)"
if ! grep -q 'libusb-1\.0\.so' <<<"$libs"; then
  die "libusb-1.0 is missing. Install it (Debian/Ubuntu: libusb-1.0-0, Fedora/Arch: libusb1 / libusb)."
fi
if ! grep -q 'libevdev\.so' <<<"$libs"; then
  die "libevdev is missing. Install it (Debian/Ubuntu: libevdev2, Fedora/Arch: libevdev)."
fi

# ------------------------------------------------------------------ files
say "Installing to $DEST"
mkdir -p "$DEST/lib"
install -m 755 "$HERE/guncon3-mouse.py" "$DEST/guncon3-mouse.py"
install -m 644 "$HERE/70-guncon3.rules" "$DEST/70-guncon3.rules"
install -m 644 "$HERE/LICENSE" "$DEST/LICENSE"

say "Fetching pyusb and python-libevdev from PyPI"
python3 -I - "$DEST/lib" <<'PY'
import hashlib, io, json, sys, urllib.request, zipfile
dest = sys.argv[1]
for pkg, mod in (("pyusb", "usb"), ("libevdev", "libevdev")):
    meta = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=30))
    wheel = next(u for u in meta["urls"] if u["packagetype"] == "bdist_wheel" and u["filename"].endswith("-none-any.whl"))
    data = urllib.request.urlopen(wheel["url"], timeout=60).read()
    if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
        sys.exit(f"{wheel['filename']}: SHA-256 does not match PyPI")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest, [n for n in z.namelist() if n.startswith(mod + "/")])
    print(f"   {wheel['filename']} (sha256 ok)")
PY
python3 -I "$DEST/guncon3-mouse.py" --version >/dev/null || die "The driver does not start; see the message above."

# ------------------------------------------------------------------ udev
if [ "$udev" = 1 ]; then
  if [ -f "$RULE" ] && cmp -s "$HERE/70-guncon3.rules" "$RULE"; then
    say "udev rule already installed"
  else
    say "Installing the udev rule to $RULE (asks for your password)"
    if sudo install -m 644 "$HERE/70-guncon3.rules" "$RULE"; then
      sudo udevadm control --reload
      sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=0b9a || true
      sudo udevadm trigger --subsystem-match=misc --sysname-match=uinput || true
    else
      warn "Could not install the udev rule. Without it only root can open the gun:"
      warn "  sudo install -m 644 $HERE/70-guncon3.rules $RULE && sudo udevadm control --reload"
    fi
  fi
  if [ ! -e /dev/uinput ]; then
    say "Loading the uinput module (sudo)"
    sudo modprobe uinput && echo uinput | sudo tee /etc/modules-load.d/guncon3-uinput.conf >/dev/null || warn "Could not load uinput."
  fi
fi

# ------------------------------------------------------------------ service
if [ "$service" = 1 ] && have systemctl; then
  say "Enabling the user service (starts with your session)"
  mkdir -p "$UNIT_DIR"
  install -m 644 "$HERE/guncon3.service" "$UNIT_DIR/guncon3.service"
  systemctl --user daemon-reload
  systemctl --user enable guncon3.service >/dev/null
  systemctl --user restart guncon3.service
elif [ "$service" = 1 ]; then
  warn "No systemd here: start the driver yourself with  python3 $DEST/guncon3-mouse.py"
fi

# ------------------------------------------------------------------ calibration
if [ -f "$CAL/calibration.json" ]; then
  say "Keeping your calibration ($CAL/calibration.json)."
elif [ -t 0 ] && gun_present; then
  echo
  read -r -p "Calibrate now? Aim at the four corners of the screen and shoot each [Y/n] " ans
  if [ "${ans:-y}" != n ] && [ "${ans:-y}" != N ]; then
    have systemctl && systemctl --user stop guncon3.service 2>/dev/null || true
    python3 -I "$DEST/guncon3-mouse.py" --calibrate || warn "Calibration did not finish; run it later."
    [ "$service" = 1 ] && have systemctl && systemctl --user start guncon3.service || true
  fi
else
  warn "Not calibrated yet. With the gun plugged in:"
  warn "  systemctl --user stop guncon3 && python3 $DEST/guncon3-mouse.py --calibrate && systemctl --user start guncon3"
fi

echo
say "Done. The GunCon 3 is now a mouse: aim and shoot."
