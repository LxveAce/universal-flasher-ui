# Universal Flasher & UI

Multi-firmware flasher + headless device controller with cross-device communication. Flash, control, and coordinate ESP32, Raspberry Pi, Flipper Zero, and ADB-based security hardware from one app.

**Evolution of [Universal Flasher](https://github.com/LxveAce/universal-flasher) and [Headless Marauder GUI](https://github.com/LxveAce/headless-marauder-gui).**

## What This Does

Three pillars in one desktop application:

### 1. Flash (from Universal Flasher)
- 14+ firmware profiles (Marauder, GhostESP, Bruce, HaleHound, Meshtastic, ESP32-DIV, Flock-You, OUI-Spy, CYT-NG, Momentum, Unleashed, and more)
- 4 flash backends: esptool (ESP32), SD image writer (Pi), qFlipper (Flipper Zero), ADB (Android)
- Batch flash, firmware backup/restore, device auto-detect, offline cache, update checker

### 2. UI / Device Communication (from Headless Marauder GUI)
- Full serial controller for every supported headless device
- Protocol-aware command interface per firmware (Marauder commands, GhostESP commands, Bruce commands, etc.)
- Live data tables (APs, stations, BLE devices, SubGHz captures)
- Target picker, data logging, session export

### 3. Cross-Device Communication (NEW)
- **Target sharing** -- when Device A discovers a MAC address, access point, or BLE target, it can push that target to Device B for immediate action
- **Coordinated attacks** -- Marauder deauths a target while a second ESP32 captures the handshake, orchestrated from one UI
- **Event bus** -- all connected devices publish discoveries to a shared event stream; any device can subscribe and act
- **Multi-device dashboard** -- see all connected devices, their status, current operation, and discovered targets in one view

## Architecture

```
universal-flasher-ui/
├── src/
│   ├── main.py                  # Entry point
│   ├── app.py                   # QApplication + main window
│   ├── ui/
│   │   ├── main_window.py       # Tab bar: Flash | Devices | Cross-Comm | Settings
│   │   ├── flash_tab.py         # Firmware selection, flash progress, batch queue
│   │   ├── device_tab.py        # Per-device serial terminal + command palette
│   │   ├── cross_comm_tab.py    # Target sharing, event stream, coordination
│   │   └── settings_tab.py      # Config, profiles, theme
│   ├── core/
│   │   ├── device_manager.py    # USB detection, connect/disconnect, device registry
│   │   ├── serial_handler.py    # Async serial read/write per device
│   │   ├── flash_engine.py      # esptool, SD writer, qFlipper, ADB backends
│   │   ├── cross_comm.py        # Event bus + target broker between devices
│   │   └── profile_loader.py    # Firmware profile JSON loader + validator
│   ├── protocols/
│   │   ├── base.py              # Abstract protocol (parse output, build commands)
│   │   ├── marauder.py          # ESP32 Marauder serial protocol
│   │   ├── ghost_esp.py         # GhostESP protocol
│   │   ├── bruce.py             # Bruce firmware protocol
│   │   ├── halehound.py         # HaleHound CYD protocol
│   │   └── flipper.py           # Flipper Zero CLI protocol
│   ├── models/
│   │   ├── device.py            # Connected device model
│   │   ├── target.py            # Discovered target (AP, MAC, BLE, SubGHz)
│   │   └── message.py           # Cross-comm event message
│   └── config/
│       ├── settings.py          # Persistent app settings
│       └── profiles/            # Firmware profile JSONs
│           └── marauder.json
├── tests/
├── assets/
│   └── icons/
├── requirements.txt
└── .gitignore
```

## Cross-Communication Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Marauder    │     │  Event Bus   │     │  Sniffer     │
│  (Gold #1)   │────>│  (Target     │────>│  (Gold #2)   │
│  scanap      │     │   Broker)    │     │  sniff MAC   │
│  found AP X  │     │              │     │  from bus    │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                    │
       v                    v                    v
  "AP: MyNetwork"    Shared Target Pool    "sniffpmkid MyNetwork"
  "MAC: AA:BB:..."   ┌──────────────┐     auto-targeted
                     │ AP: MyNetwork│
                     │ MAC: AA:BB   │
                     │ Ch: 6        │
                     │ Source: #1   │
                     └──────────────┘
```

## Tech Stack

- **Python 3.10+**
- **PyQt5** -- desktop UI framework (consistent with Headless Marauder GUI)
- **pyserial** -- serial communication
- **esptool** -- ESP32 flashing
- **adb** -- Android device bridge
- **pyudev / pyserial.tools** -- USB device detection

## Status

**Early scaffolding** -- project structure and architecture defined. Core modules stubbed. Not yet functional.

## Relationship to Other Projects

| Project | Role | Status |
|---------|------|--------|
| [Headless Marauder GUI](https://github.com/LxveAce/headless-marauder-gui) | Original Marauder controller. Device communication code migrates here. | v1.3.0 -- stable, continues as Marauder-only tool |
| [Universal Flasher](https://github.com/LxveAce/universal-flasher) | Original multi-firmware flasher. Flash engine migrates here. | v1.0.0 -- stable, continues as flash-only tool |
| **Universal Flasher & UI** | Unified successor. Flash + control + cross-comm in one app. | Scaffolding |

## License

MIT
