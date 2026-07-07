# Universal Flasher & UI

> ## ⚠️ Superseded — this was a prototype
> The unified flasher + controller work continues in **[Cyber Controller](https://github.com/LxveAce/cyber-controller)**,
> which supersedes this repo. For day-to-day use: **[universal-flasher](https://github.com/LxveAce/universal-flasher)**
> for flashing + **[headless-marauder-gui](https://github.com/LxveAce/headless-marauder-gui)** for Marauder control.
> This v0.1.0 snapshot is kept for reference and is **archived (read-only)**.

[![Status: Alpha](https://img.shields.io/badge/status-alpha%20(v0.1.0)-orange)](https://github.com/LxveAce/universal-flasher-ui/releases)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![UI: PyQt5](https://img.shields.io/badge/ui-PyQt5-green)](https://pypi.org/project/PyQt5/)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](#license)

> ⚠️ **Authorized, lawful use only.** A security-research tool — use it only on systems you own or have explicit permission to test. Provided as-is, no warranty; you assume all risk. See [DISCLAIMER.md](DISCLAIMER.md).

A single desktop app that **flashes firmware**, **talks to headless devices over serial**, and **coordinates discoveries between devices** — for ESP32, Raspberry Pi, Flipper Zero, and ADB-based hardware.

> **⚡ Hardware in the works** — [LxveLabs](https://github.com/LxveAce) is developing a custom security-hardware board **in collaboration with [PCBWay](https://www.pcbway.com)**.

This is the unified successor to two earlier tools by the same author:
[Universal Flasher](https://github.com/LxveAce/universal-flasher) (flashing) and
[Headless Marauder GUI](https://github.com/LxveAce/headless-marauder-gui) (device control). It merges their core ideas into one PyQt5 application and adds a cross-device event bus.

> ## ⚠️ Project status — alpha, and superseded
>
> **v0.1.0 ("First Functional Release")** is the current and final tag of this repo. The flash engine,
> serial controller, protocol parsers, and all four UI tabs are **implemented and wired** (this is no
> longer a stub-only scaffold). It is, however, **early alpha** — lightly tested, with only a young
> unit-test suite (protocol parsers, profile loader, cross-comm broker, settings) — so treat it as experimental.
>
> Development of the unified-controller idea has **moved on to [cyber-controller](https://github.com/LxveAce)**,
> which supersedes this repo. The mature, single-purpose tools — **[Universal Flasher](https://github.com/LxveAce/universal-flasher)**
> and **[Headless Marauder GUI](https://github.com/LxveAce/headless-marauder-gui)** — remain the recommended
> options for day-to-day flashing and Marauder control. This repo is kept as a working snapshot of the unified prototype.

## What it does

Four tabs, one window: **Flash · Devices · Cross-Comm · Settings**.

### 1. Flash

Profile-driven firmware flashing with four backends:

| Backend | Target | Status |
|---------|--------|--------|
| `esptool` | ESP32 (Marauder, GhostESP, Bruce, HaleHound, …) | Implemented — flash, erase, backup (read-flash), verify, with live progress parsing |
| `qflipper` | Flipper Zero | Implemented — firmware update via the qFlipper CLI |
| `adb` | Android / ADB devices | Implemented — APK install and file push via `adb` |
| `sd-image` | Raspberry Pi SD/USB images | Implemented on Linux/macOS (`dd`); on Windows it points you to Raspberry Pi Imager / balenaEtcher |

Flashing runs on a background `QThread`, so the UI stays responsive and streams esptool/qFlipper output line-by-line into the log. A batch queue lets you line up multiple (port, firmware) jobs.

A **Device Operations** row exposes the esptool extras on demand — **Erase Flash**, **Backup (read-flash)** to a `.bin`, and **Verify** against the selected firmware — each on its own background worker (they're enabled only for esptool profiles). For a single flash, two of them also run automatically when you turn them on in Settings: *auto-backup before flash* (which aborts the flash if the backup fails) and *verify after flash*. The batch queue keeps things simple and skips both.

Firmware is described by JSON profiles in [`src/config/profiles/`](src/config/profiles). Six ship in the box:

- **ESP32 Marauder** (`marauder.json`)
- **GhostESP** (`ghost_esp.json`)
- **Bruce** (`bruce.json`)
- **HaleHound** (`halehound.json`)
- **Flipper Zero — Momentum** (`flipper_momentum.json`)
- **Flipper Zero — Unleashed** (`flipper_unleashed.json`)

Each profile declares its backend, board variants, upstream download URL, and flash arguments. Adding a firmware is just dropping in another JSON file.

### 2. Devices (serial control)

A per-device serial terminal with protocol awareness. `DeviceManager` enumerates serial ports (matching known USB VIDs for CH340, CP2102, FTDI, and native ESP32-S2/S3 USB to friendly chip names) and polls in the background to detect disconnects, while a per-device reader thread streams output without blocking the UI.

Five firmware protocols are implemented, each translating between the app's unified `Target` model and the firmware's serial interface:

- **Marauder** — `scanap`, `scansta`, `sniffpmkid`, deauth/beacon attacks, list/select, channel control, and more
- **GhostESP**
- **Bruce**
- **HaleHound**
- **Flipper Zero** (CLI)

A protocol parses discovery lines (e.g. an AP `SSID/BSSID/Ch/RSSI`) into `Target` objects and builds the right command string for a given action.

### 3. Cross-Comm (cross-device coordination)

The piece that's new to this project. `CrossCommBroker` is an event bus and shared target pool:

- When any connected device discovers a target (AP, station, BLE device, SubGHz signal, …), it **publishes** to the broker.
- The broker de-duplicates and adds it to a **shared target pool** visible across the app.
- **Auto-routing rules** can forward matching targets to another device with a templated command — e.g. *"any AP that Device A finds → send `sniffpmkid {identifier}` to Device B."*

This lets you orchestrate multi-device workflows (one device scans, another acts) from a single UI, using a rule dialog with placeholders like `{identifier}`, `{mac}`, and `{channel}`.

### 4. Settings

Serial, flash, and cross-comm defaults, persisted to `~/.universal-flasher-ui/settings.json`, plus a **Reload Profiles** button that re-reads the firmware profiles directory.

> **Alpha note:** the flash **verify** and **auto-backup** settings are now applied on a single flash. Some other saved preferences persist but aren't consumed at runtime yet (e.g. the serial connect path uses a fixed baud, and the stored `theme` has no selector). Wiring the rest into the live flow is left for a later pass.

## Architecture

```
universal-flasher-ui/
├── src/
│   ├── main.py                  # Entry point (QApplication)
│   ├── app.py                   # Main window: Flash | Devices | Cross-Comm | Settings
│   ├── ui/
│   │   ├── main_window.py        # Menu bar (File/View/Help) + window mixin
│   │   ├── flash_tab.py          # Firmware/profile selection, batch queue, progress
│   │   ├── device_tab.py         # Per-device serial terminal + command palette
│   │   ├── cross_comm_tab.py     # Target pool, event stream, auto-routing rules
│   │   └── settings_tab.py       # Config, profiles, theme
│   ├── core/
│   │   ├── device_manager.py     # USB/serial detection, connect/disconnect, registry
│   │   ├── serial_handler.py     # Background per-device serial reader threads
│   │   ├── flash_engine.py       # esptool / sd-image / adb / qflipper backends
│   │   ├── cross_comm.py         # Event bus + target broker + auto-routing
│   │   └── profile_loader.py     # Firmware profile JSON loader
│   ├── protocols/
│   │   ├── base.py               # Abstract protocol (parse output, build commands)
│   │   ├── marauder.py · ghost_esp.py · bruce.py · halehound.py · flipper.py
│   ├── models/
│   │   ├── device.py · target.py · message.py
│   └── config/
│       ├── settings.py
│       └── profiles/             # Firmware profile JSONs (6 included)
├── tests/                        # Pytest suite (protocols, loader, broker, settings)
├── build.py                      # PyInstaller build script
├── pyproject.toml · requirements.txt
└── .github/workflows/build-release.yml
```

## Cross-Comm flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Device A     │     │  CrossComm   │     │  Device B     │
│  (scanner)    │────>│  Broker      │────>│  (actor)      │
│  scanap       │     │  (target     │     │  acts on the  │
│  found AP X   │     │   pool +     │     │  routed       │
│               │     │  auto-route) │     │  target       │
└──────────────┘     └──────────────┘     └──────────────┘
        │                    │                    │
        v                    v                    v
   "AP: MyNetwork"     Shared Target Pool   "sniffpmkid MyNetwork"
   "MAC: AA:BB:…"      AP / MAC / Ch / src   (auto-targeted)
```

## Tech stack

- **Python 3.12+**
- **PyQt5** — desktop UI and threading (`QThread`, signals/slots)
- **pyserial** — serial detection and I/O
- **esptool** — ESP32 flashing (invoked as a subprocess)
- **requests** — declared for planned profile/firmware downloads (no downloader is wired up yet)
- External CLIs used when present: **`adb`** (Android), **`qFlipper`** (Flipper Zero), **`dd`** (SD imaging on Linux/macOS)

## Install & run (from source)

Requires Python 3.12+.

```bash
git clone https://github.com/LxveAce/universal-flasher-ui.git
cd universal-flasher-ui
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/mac: source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

External tools are only needed for the backends you actually use: `adb` for Android targets, `qFlipper` for Flipper firmware updates, and (on Linux/macOS) `dd` for SD imaging.

## Prebuilt binaries

The **[v0.1.0 release](https://github.com/LxveAce/universal-flasher-ui/releases/tag/v0.1.0)** ships standalone executables built with PyInstaller:

- `universal-flasher-ui-v0.1.0-windows-x64.exe`
- `universal-flasher-ui-v0.1.0-macos`
- `universal-flasher-ui-v0.1.0-linux-x64`

Builds are produced by the [Build & Release](.github/workflows/build-release.yml) GitHub Actions workflow on each published release. To build locally:

```bash
pip install pyinstaller
python build.py            # directory bundle
python build.py --onefile  # single executable
```

## Relationship to other projects

| Project | Role | Status |
|---------|------|--------|
| [Universal Flasher](https://github.com/LxveAce/universal-flasher) | Original multi-firmware flasher; the flash engine here grew from it. | Stable, recommended for flashing |
| [Headless Marauder GUI](https://github.com/LxveAce/headless-marauder-gui) | Original Marauder serial controller; the device-control ideas here grew from it. | Stable, recommended for Marauder control |
| **Universal Flasher & UI** *(this repo)* | Unified prototype — flash + serial control + cross-device coordination in one app. | **Alpha (v0.1.0)**, superseded |
| [cyber-controller](https://github.com/LxveAce) | Successor to this unified-controller idea. | Where active work continues |

## Legal & safety

This software flashes firmware and drives wireless security tools (Marauder, GhostESP, Bruce, HaleHound, Flipper Zero, …). Some of that firmware can transmit on regulated radio bands and perform offensive actions.

Use it **only** on hardware and networks you own or are explicitly authorized to test. You are responsible for complying with all applicable laws and regulations in your jurisdiction. This project is provided for education and authorized testing; the author accepts no liability for misuse or for any damage to devices. Flashing always carries a risk of bricking — back up first.

## License

Released under the **MIT License**. This is a self-taught, hobby project; contributions and bug reports are welcome.

## Connect

- 💬 **Discord:** [discord.gg/lxvelabs](https://discord.gg/lxvelabs) — questions, help, or to talk through this project
- 🐙 **GitHub:** [@LxveAce](https://github.com/LxveAce)
- ✉️ **Email:** LxveLabs@proton.me (business) · lxveace@proton.me (direct)
- 🌐 **Website:** [lxvelabs.com](https://lxvelabs.com) · personal: [lxveace.com](https://lxveace.com)
- 🛰️ **Project site:** [esp32marauder.com](https://esp32marauder.com)

---

### Built by LxveLabs

A **LxveLabs** project by LxveAce — hardware & security tools. LxveLabs is developing custom multi-radio ESP32 hardware in collaboration with [PCBWay](https://www.pcbway.com). More at [github.com/LxveAce](https://github.com/LxveAce).
