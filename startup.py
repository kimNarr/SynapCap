"""Windows Run-on-Startup management via HKCU registry.

Network-free, dependency-free, and safe on non-Windows platforms.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE_NAME = "SynapCap"


def _launch_command() -> str:
    """Return the quoted command line required to launch SynapCap."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_script = Path(__file__).resolve().parent / "main.py"
    return f'"{sys.executable}" "{main_script}"'


def is_startup_enabled() -> bool:
    """Check if SynapCap is registered in the Windows startup registry."""
    if os.name != "nt":
        return False

    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_KEY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, REG_VALUE_NAME)
            return bool(value)
    except (OSError, FileNotFoundError):
        return False


def set_startup_enabled(enable: bool) -> bool:
    """Register or unregister SynapCap from the Windows startup registry."""
    if os.name != "nt":
        return False

    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enable:
                winreg.SetValueEx(
                    key,
                    REG_VALUE_NAME,
                    0,
                    winreg.REG_SZ,
                    _launch_command(),
                )
            else:
                try:
                    winreg.DeleteValue(key, REG_VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as exc:
        print(f"[SynapCap Startup] Failed to update startup registry: {exc}")
        return False
