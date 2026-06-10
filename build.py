"""
PyInstaller build script for Universal Flasher & UI.

Usage:
    python build.py             # Build a directory bundle
    python build.py --onefile   # Build a single executable
"""

import sys
import os
import argparse
import subprocess


def build(onefile=False):
    app_name = "universal-flasher-ui"
    entry = os.path.join("src", "main.py")

    hidden_imports = [
        "src",
        "src.app",
        "src.core",
        "src.core.device_manager",
        "src.core.serial_handler",
        "src.core.flash_engine",
        "src.core.cross_comm",
        "src.core.profile_loader",
        "src.models",
        "src.models.device",
        "src.models.target",
        "src.models.message",
        "src.protocols",
        "src.protocols.base",
        "src.protocols.marauder",
        "src.protocols.ghost_esp",
        "src.protocols.bruce",
        "src.protocols.halehound",
        "src.protocols.flipper",
        "src.ui",
        "src.ui.main_window",
        "src.ui.flash_tab",
        "src.ui.device_tab",
        "src.ui.cross_comm_tab",
        "src.ui.settings_tab",
        "src.config",
        "src.config.settings",
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtWidgets",
        "PyQt5.QtGui",
        "serial",
        "serial.tools",
        "serial.tools.list_ports",
        "esptool",
        "requests",
    ]

    # Data files: firmware profiles
    datas = [
        (os.path.join("src", "config", "profiles"), os.path.join("src", "config", "profiles")),
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--noconfirm",
        "--clean",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Hidden imports
    for hi in hidden_imports:
        cmd.extend(["--hidden-import", hi])

    # Data files
    for src_path, dest_path in datas:
        sep = ";" if sys.platform == "win32" else ":"
        cmd.extend(["--add-data", f"{src_path}{sep}{dest_path}"])

    # No console window on Windows
    if sys.platform == "win32":
        cmd.append("--noconsole")

    cmd.append(entry)

    print(f"Building {app_name}...")
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd)
    if result.returncode == 0:
        print(f"\nBuild complete. Output in dist/{app_name}")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Universal Flasher & UI")
    parser.add_argument("--onefile", action="store_true", help="Build single executable")
    args = parser.parse_args()
    build(onefile=args.onefile)
