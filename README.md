# GunCon 3 on Linux: absolute-mouse driver for Steam Deck, SteamOS, Bazzite & any distro

**Use the Namco GunCon 3 (the PS3 light gun) on Linux as a plain absolute mouse**: aim at the
screen and shoot, in any game or emulator where *the mouse is the gun*. No kernel module, no
compiling: a small userspace driver, one udev rule, a calibration that takes 20 seconds, and a
service that starts with your session.

![GunCon 3](https://img.shields.io/badge/GunCon%203-0b9a%3A0800-e4002b)
![Steam Deck](https://img.shields.io/badge/Steam%20Deck-supported-1a9fff)
![SteamOS](https://img.shields.io/badge/SteamOS-supported-1a9fff)
![Bazzite](https://img.shields.io/badge/Bazzite-tested-8a2be2)
![Linux](https://img.shields.io/badge/Linux-any%20distro-success)
![License: GPL-2.0](https://img.shields.io/badge/License-GPL--2.0-blue)

---

## Table of contents

- [Why](#why)
- [Features](#features)
- [What you need](#what-you-need)
- [Installation](#installation)
- [Calibration](#calibration)
- [Buttons](#buttons)
- [Playing Time Crisis](#playing-time-crisis)
- [Other games and emulators](#other-games-and-emulators)
- [Updating and uninstalling](#updating-and-uninstalling)
- [Troubleshooting / FAQ](#troubleshooting--faq)
- [How it works](#how-it-works)
- [Credits](#credits)
- [License](#license)

---

## Why

The GunCon 3 is not a HID device: it speaks a vendor-specific USB protocol, waits for an
encryption key before it sends anything, and encrypts every report. Linux has no driver for it.
The projects that exist ([beardypig/guncon3](https://github.com/beardypig/guncon3), a kernel module,
and [pcnimdock/guncon3-linux-pyusb](https://github.com/pcnimdock/guncon3-linux-pyusb)) make it a
**joystick**, and the kernel module has to be rebuilt for every kernel, which is painful on
image-based systems like SteamOS and Bazzite.

Most modern light-gun setups (Sinden, Gun4IR, AimTrak, OpenFIRE) work differently: the gun is an
**absolute mouse**. Games and ports built for those guns, such as the
[Namco System 22 PC ports](https://github.com/spacestate1/namco22-decompile) (*Time Crisis*), take
the mouse as the gun. This driver makes the GunCon 3 behave the same way.

## Features

- **Absolute mouse**: the pointer goes exactly where the gun points. No drift, no recentring.
- **4-corner calibration** with a perspective (homography) fit, which handles a tilted gun, IR
  emitters that are not perfectly level, and sitting off-centre. Each corner averages the aim
  from just *before* the trigger, so the jerk of pulling it does not count.
- **Reload off-screen**: aiming outside the IR emitters' view puts the pointer on the screen's
  edge, which light-gun games read as "off screen".
- **Buttons as mouse buttons and keys**: trigger = left click, B buttons = right click (the
  Time Crisis pedal), the rest = coin, start, menu, and so on.
- **Userspace only**: Python, pyusb and python-libevdev. No kernel module and no DKMS, so it keeps
  working across SteamOS and Bazzite updates.
- **Hot-plug**: the service waits for the gun and reconnects when it is unplugged.
- **No pip needed**: the installer fetches the two Python libraries from PyPI and checks their
  SHA-256 hashes.

## What you need

- A **Namco GunCon 3** (USB ID `0b9a:0800`) with its **two IR emitters** plugged into the box on
  its cable, placed at the top (or bottom) corners of your screen and facing you.
- Linux with **Python 3.8+**, **libusb-1.0** and **libevdev**. SteamOS, Bazzite, Fedora, Ubuntu
  and Arch all have them already.
- `sudo` once, for the udev rule. On a Steam Deck, set a password first with `passwd` in Desktop
  Mode.

## Installation

```bash
git clone https://github.com/leandrolalanne/guncon3-linux.git
cd guncon3-linux
./install.sh
```

The installer:

1. copies the driver to `~/.local/share/guncon3-linux/`,
2. downloads **pyusb** and **python-libevdev** from PyPI into a private folder (SHA-256 checked),
3. installs `70-guncon3.rules` into `/etc/udev/rules.d/` (**asks for your password**), so your
   user can open the gun and create the virtual mouse,
4. enables a **user service** (`guncon3.service`) that starts the driver with your session,
5. offers to **calibrate** if the gun is plugged in.

Options: `--no-service` (start the driver yourself), `--no-udev` (install the rule yourself),
`--uninstall`, `--purge` (also removes the calibration).

**Steam Deck / SteamOS / Bazzite:** run it in Desktop Mode from Konsole. Everything goes in your
home folder and `/etc`, both of which survive OS updates. The service also runs in Game Mode.

## Calibration

Calibrate once, from where you sit, holding the gun the way you will play:

```bash
systemctl --user stop guncon3
python3 ~/.local/share/guncon3-linux/guncon3-mouse.py --calibrate
systemctl --user start guncon3
```

Shoot the four corners **of the lit picture**, in this order: top-left, top-right, bottom-right,
bottom-left. Hold steady for a second before each shot. The result goes to
`~/.config/guncon3/calibration.json`.

Recalibrate if you move the IR emitters or where you sit. If the picture changes resolution or
aspect ratio, you do not need to: the calibration maps to the whole screen.

## Buttons

| GunCon 3 | Sends | Time Crisis |
|---|---|---|
| Trigger | left mouse button | shoot |
| B1 / B2 | right mouse button | **foot pedal** (hold to come out of cover) |
| A1 | `5` | insert coin |
| A2 | `Enter` | start |
| C1 | `Esc` | menu |
| C2 | `R` | reload |
| Stick click (one) | `F2` | test mode |
| Stick click (other) | `9` | service |
| Aim off-screen | pointer at screen edge | reload |

To change the mapping, edit the `BUTTONS` table near the top of `guncon3-mouse.py`. Any
`libevdev` key or mouse-button code works.

## Playing Time Crisis

[spacestate1/namco22-decompile](https://github.com/spacestate1/namco22-decompile) rebuilds
Namco System 22 arcade games for the PC; *Time Crisis* (1995) is one of them, with **"the mouse is
the gun"**. With this driver running:

1. Get the `TimeCrisis-x86_64.AppImage` from its releases, and put your own `timecris.zip` (MAME
   set) into `~/.local/share/namco22/timecris/roms/`.
2. Add the AppImage to Steam as a non-Steam game and start it from Game Mode.
3. A1 = coin (a game takes three), trigger = shoot, hold B = pedal.
4. Optional: **Esc → Display → Crosshair off** (a real gun needs none), and **F8** cycles a white
   border if your IR setup likes one.

Tested this way on Bazzite (Game Mode, 4K TV): shots land where the gun points.

## Other games and emulators

Anything that takes an absolute mouse as a light gun should work, as it would with a Sinden or a
Gun4IR. In MAME, use the mouse as the light gun (`-lightgun -lightgun_device mouse`, or the
equivalent in your frontend), and in RetroArch, set the core's gun input to the mouse. These have
not been tested here yet; reports are welcome.

## Updating and uninstalling

```bash
cd guncon3-linux && git pull && ./install.sh      # update (keeps the calibration)
./install.sh --uninstall                          # remove (keeps the calibration)
./install.sh --purge                              # remove everything
```

## Troubleshooting / FAQ

**"The GunCon 3 is in use by another program"**: the service already has the gun. Stop it
(`systemctl --user stop guncon3`) before `--calibrate` or `--debug`.

**"No permission to open the GunCon 3"**: the udev rule is missing. Run `./install.sh` again,
or install `70-guncon3.rules` into `/etc/udev/rules.d/` by hand, then re-plug the gun.

**The pointer never moves / everything reads as off-screen**: the gun does not see the IR
emitters. Check that both are plugged into the box on the gun's cable, facing you, and that you
are within range. `--debug` prints `off=1` while they are not seen.

**Shots land slightly off**: recalibrate, holding the gun the way you play and aiming at the
very edge of the lit picture.

**Is it running?** `systemctl --user status guncon3` and `journalctl --user -u guncon3 -f`.
A working driver creates two input devices, `GunCon3 Light Gun` and `GunCon3 Light Gun Keys`.

**Live view of what the gun sends:**
```bash
systemctl --user stop guncon3
python3 ~/.local/share/guncon3-linux/guncon3-mouse.py --debug
```

## How it works

1. The driver opens the gun with **pyusb** (interface 0: interrupt OUT `0x02`, interrupt IN
   `0x82`) and sends the 8-byte key. Until it gets one, the gun stays silent.
2. Every 15-byte report is **decrypted**: a checksum against the key, then each of 13 bytes is
   unscrambled with a 320-entry table. This algorithm and the table come from
   [beardypig/guncon3](https://github.com/beardypig/guncon3) and
   [pcnimdock/guncon3-linux-pyusb](https://github.com/pcnimdock/guncon3-linux-pyusb).
3. The decrypted report holds the aim (signed 16-bit X/Y from the IR camera), an "out of view"
   flag, the buttons and the two analog sticks.
4. A **homography** fitted from the four calibration corners maps the aim to screen coordinates,
   with light smoothing.
5. **uinput** (via python-libevdev) creates an absolute pointer (`ABS_X`/`ABS_Y` + mouse buttons,
   which udev tags as `ID_INPUT_MOUSE`) and a small keyboard.

Notes: one more bit of the report (byte 1, `0x01`) changes, probably the second stick's click,
and is not mapped. The analog sticks are not used yet.

## Credits

- [**beardypig/guncon3**](https://github.com/beardypig/guncon3): the protocol, the key and the
  decryption (Linux kernel driver).
- [**pcnimdock/guncon3-linux-pyusb**](https://github.com/pcnimdock/guncon3-linux-pyusb) and
  pcnimdock's other GunCon 3 tools: the userspace approach in Python.
- [**spacestate1/namco22-decompile**](https://github.com/spacestate1/namco22-decompile): the
  Time Crisis port this was made for.
- [pyusb](https://github.com/pyusb/pyusb) and
  [python-libevdev](https://gitlab.freedesktop.org/libevdev/python-libevdev).

Written with the help of Claude (Anthropic).

## License

**GPL-2.0-or-later** (see `LICENSE`), as the decryption code is derived from GPL-2.0-or-later code
([beardypig/guncon3](https://github.com/beardypig/guncon3)).

GunCon, Time Crisis and Namco are trademarks of Bandai Namco Entertainment; this project is not
affiliated with or endorsed by them.
