#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""guncon3-linux: Namco GunCon 3 (USB 0b9a:0800) as an absolute mouse on Linux.

The gun only talks after it receives an 8-byte key, and its reports are
encrypted with it. The decryption (key table and algorithm) is ported from
beardypig/guncon3 and pcnimdock/guncon3-linux-pyusb (both GPL-2.0). The output
is a uinput absolute pointer plus a small keyboard, the way Sinden, Gun4IR and
AimTrak guns appear, so games where "the mouse is the gun" work without setup.

  guncon3-mouse.py              run the driver (waits for the gun, reconnects)
  guncon3-mouse.py --calibrate  shoot the four corners of the screen
  guncon3-mouse.py --debug      print raw position and buttons
  guncon3-mouse.py --version

Calibration is kept in ~/.config/guncon3/calibration.json.
https://github.com/leandrolalanne/guncon3-linux
"""
import errno, json, os, sys, time

VERSION = "1.0.0"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib"))
try:
    import usb.core, usb.util  # noqa: E402
    import libevdev  # noqa: E402
    from libevdev import InputEvent, InputAbsInfo  # noqa: E402
except ImportError as e:
    sys.exit(f"Missing Python module: {e.name}. Run install.sh, or: "
             f"python3 -m pip install --target {os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')} pyusb libevdev")

VID, PID = 0x0B9A, 0x0800
KEY = bytes([0x01, 0x12, 0x6F, 0x32, 0x24, 0x60, 0x17, 0x21])
CAL_FILE = os.path.expanduser("~/.config/guncon3/calibration.json")
SMOOTH = 0.5          # 0 = no smoothing, closer to 1 = smoother but laggier
ABS_MAX = 65535

KEY_TABLE = bytes([
    0x75, 0xC3, 0x10, 0x31, 0xB5, 0xD3, 0x69, 0x84, 0x89, 0xBA, 0xD6, 0x89, 0xBD, 0x70, 0x19, 0x8E, 0x58, 0xA8,
    0x3D, 0x9B, 0x5D, 0xF0, 0x49, 0xE8, 0xAD, 0x9D, 0x7A, 0x0D, 0x7E, 0x24, 0xDA, 0xFC, 0x0D, 0x14, 0xC5, 0x23,
    0x91, 0x11, 0xF5, 0xC0, 0x4B, 0xCD, 0x44, 0x1C, 0xC5, 0x21, 0xDF, 0x61, 0x54, 0xED, 0xA2, 0x81, 0xB7, 0xE5,
    0x74, 0x94, 0xB0, 0x47, 0xEE, 0xF1, 0xA5, 0xBB, 0x21, 0xC8, 0x91, 0xFD, 0x4C, 0x8B, 0x20, 0xC1, 0x7C, 0x09, 0x58,
    0x14, 0xF6, 0x00, 0x52, 0x55, 0xBF, 0x41, 0x75, 0xC0, 0x13, 0x30, 0xB5, 0xD0, 0x69, 0x85, 0x89, 0xBB, 0xD6, 0x88,
    0xBC, 0x73, 0x18, 0x8D, 0x58, 0xAB, 0x3D, 0x98, 0x5C, 0xF2, 0x48, 0xE9, 0xAC, 0x9F, 0x7A, 0x0C, 0x7C, 0x25, 0xD8,
    0xFF, 0xDC, 0x7D, 0x08, 0xDB, 0xBC, 0x18, 0x8C, 0x1D, 0xD6, 0x3C, 0x35, 0xE1, 0x2C, 0x14, 0x8E, 0x64, 0x83, 0x39,
    0xB0, 0xE4, 0x4E, 0xF7, 0x51, 0x7B, 0xA8, 0x13, 0xAC, 0xE9, 0x43, 0xC0, 0x08, 0x25, 0x0E, 0x15, 0xC4, 0x20, 0x93,
    0x13, 0xF5, 0xC3, 0x48, 0xCC, 0x47, 0x1C, 0xC5, 0x20, 0xDE, 0x60, 0x55, 0xEE, 0xA0, 0x40, 0xB4, 0xE7, 0x74,
    0x95, 0xB0, 0x46, 0xEC, 0xF0, 0xA5, 0xB8, 0x23, 0xC8, 0x04, 0x06, 0xFC, 0x28, 0xCB, 0xF8, 0x17, 0x2C, 0x25, 0x1C,
    0xCB, 0x18, 0xE3, 0x6C, 0x80, 0x85, 0xDD, 0x7E, 0x09, 0xD9, 0xBC, 0x19, 0x8F, 0x1D, 0xD4, 0x3D, 0x37, 0xE1, 0x2F,
    0x15, 0x8D, 0x64, 0x06, 0x04, 0xFD, 0x29, 0xCF, 0xFA, 0x14, 0x2E, 0x25, 0x1F, 0xC9, 0x18, 0xE3, 0x6D, 0x81, 0x84,
    0x80, 0x3B, 0xB1, 0xE5, 0x4D, 0xF7, 0x51, 0x78, 0xA9, 0x13, 0xAD, 0xE9, 0x80, 0xC1, 0x0B, 0x25, 0x93, 0xFC,
    0x4D, 0x89, 0x23, 0xC2, 0x7C, 0x0B, 0x59, 0x15, 0xF6, 0x01, 0x50, 0x55, 0xBF, 0x81, 0x75, 0xC3, 0x10, 0x31, 0xB5,
    0xD3, 0x69, 0x84, 0x89, 0xBA, 0xD6, 0x89, 0xBD, 0x70, 0x19, 0x8E, 0x58, 0xA8, 0x3D, 0x9B, 0x5D, 0xF0, 0x49,
    0xE8, 0xAD, 0x9D, 0x7A, 0x0D, 0x7E, 0x24, 0xDA, 0xFC, 0x0D, 0x14, 0xC5, 0x23, 0x91, 0x11, 0xF5, 0xC0, 0x4B, 0xCD,
    0x44, 0x1C, 0xC5, 0x21, 0xDF, 0x61, 0x54, 0xED, 0xA2, 0x81, 0xB7, 0xE5, 0x74, 0x94, 0xB0, 0x47, 0xEE, 0xF1,
    0xA5, 0xBB, 0x21, 0xC8])

# Gun button -> what it sends. Mouse buttons go to the pointer device, KEY_* to
# the keyboard device. Time Crisis: left = shoot, right = pedal (hold it).
BUTTONS = {
    "trigger": ("mouse", libevdev.EV_KEY.BTN_LEFT),
    "B1": ("mouse", libevdev.EV_KEY.BTN_RIGHT),
    "B2": ("mouse", libevdev.EV_KEY.BTN_RIGHT),
    "A1": ("key", libevdev.EV_KEY.KEY_5),        # coin
    "A2": ("key", libevdev.EV_KEY.KEY_ENTER),    # start
    "C1": ("key", libevdev.EV_KEY.KEY_ESC),      # menu
    "C2": ("key", libevdev.EV_KEY.KEY_R),        # reload
    "stickA": ("key", libevdev.EV_KEY.KEY_F2),   # test mode
    "stickB": ("key", libevdev.EV_KEY.KEY_9),    # service
}


def decode(data):
    """Decrypt one 15-byte report; None if its checksum is wrong."""
    b_sum = (((data[13] ^ data[12]) + data[11] + data[10] - data[9] - data[8]) ^ data[7]) & 0xFF
    a_sum = ((((data[6] ^ b_sum) - data[5] - data[4]) ^ data[3]) + data[2] + data[1] - data[0]) & 0xFF
    if a_sum != KEY[7]:
        return None
    off = (((((KEY[1] ^ KEY[2]) - KEY[3] - KEY[4]) ^ KEY[5]) + KEY[6] - KEY[7]) ^ data[14]) + 0x26
    off &= 0xFF
    ki = 4
    out = bytearray(13)
    for x in range(12, -1, -1):
        b = data[x]
        for _ in range(3):
            off -= 1
            bk = KEY_TABLE[off + 0x41]
            kr = KEY[ki]
            ki -= 1
            if ki == 0:
                ki = 7
            if bk & 3 == 0:
                b = b - bk - kr
            elif bk & 3 == 1:
                b = b + bk + kr
            else:
                b = b ^ bk ^ kr
        out[x] = b & 0xFF
    return out


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def parse(d):
    return {
        "x": s16(d[4] << 8 | d[3]),
        "y": s16(d[6] << 8 | d[5]),
        "offscreen": bool(d[1] & 0x08),
        "trigger": bool(d[1] & 0x20),
        "A1": bool(d[0] & 0x04), "A2": bool(d[0] & 0x02),
        "B1": bool(d[1] & 0x04), "B2": bool(d[1] & 0x02),
        "C1": bool(d[1] & 0x80), "C2": bool(d[0] & 0x08),
        "stickA": bool(d[2] & 0x80), "stickB": bool(d[2] & 0x40),
    }


def open_gun():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        return None
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError):
        pass
    dev.set_configuration()
    intf = dev.get_active_configuration()[(0, 0)]
    ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
    ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
    ep_out.write(KEY)
    return dev, ep_in


def reports(dev, ep_in):
    while True:
        try:
            raw = dev.read(ep_in.bEndpointAddress, ep_in.wMaxPacketSize, timeout=200)
        except usb.core.USBTimeoutError:
            continue
        if len(raw) < 15:
            continue
        d = decode(raw)
        if d is not None:
            yield parse(d)


def make_devices():
    m = libevdev.Device()
    m.name = "GunCon3 Light Gun"
    m.id = {"bustype": 0x03, "vendor": VID, "product": PID}
    info = InputAbsInfo(minimum=0, maximum=ABS_MAX, resolution=1)
    m.enable(libevdev.EV_ABS.ABS_X, info)
    m.enable(libevdev.EV_ABS.ABS_Y, info)
    k = libevdev.Device()
    k.name = "GunCon3 Light Gun Keys"
    k.id = {"bustype": 0x03, "vendor": VID, "product": PID + 1}
    for kind, code in BUTTONS.values():
        (m if kind == "mouse" else k).enable(code)
    m.enable(libevdev.EV_KEY.BTN_MIDDLE)
    return m.create_uinput_device(), k.create_uinput_device()


def solve(a, b):
    """Solve the linear system a x = b (Gaussian elimination, small n)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        if abs(m[c][c]) < 1e-12:
            raise ValueError("degenerate calibration")
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def homography(src, dst):
    """3x3 projective map (as 8 numbers) taking 4 src points to 4 dst points."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return solve(a, b)


def apply_h(h, x, y):
    w = h[6] * x + h[7] * y + 1
    return (h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w


CORNERS = (("TOP-LEFT", (0, 0)), ("TOP-RIGHT", (1, 0)), ("BOTTOM-RIGHT", (1, 1)), ("BOTTOM-LEFT", (0, 1)))


def load_cal():
    """Function raw (x, y) -> screen (0..1, 0..1), or None."""
    try:
        with open(CAL_FILE) as f:
            c = json.load(f)
    except (OSError, ValueError):
        return None
    if "h" in c:
        h = c["h"]
        return lambda x, y: apply_h(h, x, y)
    if "x0" in c:  # old two-corner calibration
        x0, y0, x1, y1 = c["x0"], c["y0"], c["x1"], c["y1"]
        return lambda x, y: ((x - x0) / (x1 - x0), (y - y0) / (y1 - y0))
    return None


def calibrate(dev, ep_in):
    """Shoot the four corners; each point is the average of the aim just
    before the trigger (pulling it jerks the gun)."""
    points = []
    recent = []
    for name, _ in CORNERS:
        print(f"Aim at the {name} corner of the screen, hold steady, pull the trigger...", flush=True)
        was = True
        recent.clear()
        for r in reports(dev, ep_in):
            if not r["offscreen"]:
                recent.append((r["x"], r["y"]))
                del recent[:-8]
            else:
                recent.clear()
            if r["trigger"] and not was and recent:
                sample = recent[:-1] or recent
                x = sum(p[0] for p in sample) / len(sample)
                y = sum(p[1] for p in sample) / len(sample)
                points.append((x, y))
                print(f"  {name}: x={x:.0f} y={y:.0f} ({len(sample)} readings)", flush=True)
                break
            was = r["trigger"]
    try:
        h = homography(points, [c for _, c in CORNERS])
    except ValueError:
        sys.exit("The corners do not make a shape; run --calibrate again.")
    os.makedirs(os.path.dirname(CAL_FILE), exist_ok=True)
    with open(CAL_FILE, "w") as f:
        json.dump({"h": h, "points": points}, f)
    print(f"Saved to {CAL_FILE}", flush=True)


def run(dev, ep_in, debug):
    to_screen = load_cal()
    if to_screen is None:
        print("No calibration yet: run with --calibrate. Using a rough guess.", flush=True)
        to_screen = lambda x, y: ((x + 28000) / 56000, (28000 - y) / 56000)
    mouse, keys = make_devices()
    print("GunCon 3 ready.", flush=True)
    sx = sy = ABS_MAX // 2
    pressed = {}
    for r in reports(dev, ep_in):
        if r["offscreen"]:
            # Point at the window's edge: games read that as "off screen" (reload).
            tx, ty = 0, ABS_MAX // 2
            sx, sy = tx, ty
        else:
            u, v = to_screen(r["x"], r["y"])
            tx, ty = u * ABS_MAX, v * ABS_MAX
            tx = min(max(tx, 0), ABS_MAX)
            ty = min(max(ty, 0), ABS_MAX)
            sx = SMOOTH * sx + (1 - SMOOTH) * tx
            sy = SMOOTH * sy + (1 - SMOOTH) * ty
        ev_m = [InputEvent(libevdev.EV_ABS.ABS_X, int(sx)), InputEvent(libevdev.EV_ABS.ABS_Y, int(sy))]
        ev_k = []
        state = {}
        for name, (kind, code) in BUTTONS.items():
            state[code] = state.get(code, False) or r[name]
        for name, (kind, code) in BUTTONS.items():
            v = state[code]
            if pressed.get(code) != v:
                pressed[code] = v
                (ev_m if kind == "mouse" else ev_k).append(InputEvent(code, int(v)))
        mouse.send_events(ev_m + [InputEvent(libevdev.EV_SYN.SYN_REPORT, 0)])
        if ev_k:
            keys.send_events(ev_k + [InputEvent(libevdev.EV_SYN.SYN_REPORT, 0)])
        if debug:
            on = [n for n in BUTTONS if r[n]]
            print(f"raw x={r['x']:6d} y={r['y']:6d} off={int(r['offscreen'])} -> {int(sx):5d},{int(sy):5d} {' '.join(on)}", flush=True)


def main():
    args = sys.argv[1:]
    if "--version" in args:
        print(f"guncon3-linux {VERSION}")
        return
    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return
    waited = False
    while True:
        try:
            gun = open_gun()
        except usb.core.USBError as e:
            if e.errno == errno.EBUSY:
                sys.exit("The GunCon 3 is in use by another program, most likely the driver service.\n"
                         "Stop it first:  systemctl --user stop guncon3")
            if e.errno == errno.EACCES:
                sys.exit("No permission to open the GunCon 3: install 70-guncon3.rules into "
                         "/etc/udev/rules.d/ and re-plug the gun (install.sh does this).")
            sys.exit(f"Cannot open the GunCon 3 ({e}).")
        if gun is None:
            if not waited:
                print("Waiting for the GunCon 3...", flush=True)
                waited = True
            time.sleep(2)
            continue
        waited = False
        try:
            if "--calibrate" in args:
                calibrate(*gun)
                return
            run(*gun, debug="--debug" in args)
        except usb.core.USBError as e:
            print(f"GunCon 3 lost ({e}); waiting for it again.", flush=True)
            time.sleep(1)


if __name__ == "__main__":
    main()
