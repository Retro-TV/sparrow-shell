#!/usr/bin/env python3
"""Persist Sparrow's hotspot profile through NetworkManager's libnm API.

Credentials arrive as one JSON line on stdin. They are never command-line
arguments, shell text, or temporary plaintext files. NetworkManager remains the
owner of the persistent profile and its normal Polkit authorization path.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid


PROFILE_ID = "SparrowHotspot"


def valid_password(password: str) -> bool:
    """NetworkManager's WPA-PSK: printable ASCII passphrase or 64 hex digits."""
    if len(password) == 64:
        return all(char in "0123456789abcdefABCDEF" for char in password)
    return 8 <= len(password) <= 63 and all(32 <= ord(char) <= 126 for char in password)


def _networkmanager():
    import gi

    gi.require_version("NM", "1.0")
    from gi.repository import GLib, NM

    return GLib, NM


def _set(setting, name: str, value) -> None:
    setting.set_property(name, value)


def build_profile(data: dict, existing=None):
    GLib, NM = _networkmanager()
    connection = NM.SimpleConnection.new_clone(existing) if existing else NM.SimpleConnection.new()

    def setting(cls, name: str):
        result = connection.get_setting_by_name(name)
        if result is None:
            result = cls.new()
            connection.add_setting(result)
        return result

    base = setting(NM.SettingConnection, "connection")
    _set(base, "id", PROFILE_ID)
    _set(base, "type", "802-11-wireless")
    if existing is None:
        _set(base, "uuid", str(uuid.uuid4()))
    _set(base, "interface-name", data["interface"])
    _set(base, "autoconnect", False)

    wireless = setting(NM.SettingWireless, "802-11-wireless")
    _set(wireless, "ssid", GLib.Bytes.new(data["name"].encode("utf-8")))
    _set(wireless, "mode", "ap")

    security = setting(NM.SettingWirelessSecurity, "802-11-wireless-security")
    _set(security, "key-mgmt", "wpa-psk")
    _set(security, "psk", data["password"])
    _set(security, "psk-flags", NM.SettingSecretFlags.NONE)

    ipv4 = setting(NM.SettingIP4Config, "ipv4")
    _set(ipv4, "method", "shared")
    return connection


def _finish_async(loop, finish, result, errors: list[Exception]) -> None:
    try:
        finish(result)
    except Exception as exc:  # surfaced as a concise helper error, never secret data
        errors.append(exc)
    loop.quit()


def persist_profile(data: dict) -> None:
    GLib, NM = _networkmanager()
    client = NM.Client.new(None)
    if client is None:
        raise RuntimeError("NetworkManager is unavailable")
    existing = client.get_connection_by_id(PROFILE_ID)
    connection = build_profile(data, existing)
    loop = GLib.MainLoop()
    errors: list[Exception] = []

    if existing:
        variant = connection.to_dbus(NM.ConnectionSerializationFlags.ALL)
        existing.update2(
            variant,
            NM.SettingsUpdate2Flags.TO_DISK,
            None,
            None,
            lambda source, result, _data: _finish_async(loop, source.update2_finish, result, errors),
            None,
        )
    else:
        client.add_connection_async(
            connection,
            True,
            None,
            lambda source, result, _data: _finish_async(loop, source.add_connection_finish, result, errors),
            None,
        )
    loop.run()
    if errors:
        raise RuntimeError(str(errors[0]))


def main(argv: list[str]) -> int:
    if argv not in (["save"], ["apply"]):
        print("usage: hotspot-profile.py {save|apply}", file=sys.stderr)
        return 2

    try:
        data = json.loads(sys.stdin.readline())
        if not isinstance(data, dict):
            raise ValueError("Invalid hotspot data")
        name = data.get("name")
        password = data.get("password")
        interface = data.get("interface")
        if not all(isinstance(value, str) and value for value in (name, password, interface)):
            raise ValueError("Hotspot name, password, and interface are required")
        if not valid_password(password):
            raise ValueError("Invalid WPA-PSK")
        persist_profile({"name": name, "password": password, "interface": interface})
        if argv == ["apply"]:
            # No credential appears in argv; NetworkManager reads it from its
            # stored profile and applies its own normal permissions/policy.
            subprocess.run(["nmcli", "connection", "up", PROFILE_ID], check=True)
        return 0
    except Exception:
        # Library/D-Bus diagnostics can embed setting values; do not echo them.
        print("Sparrow hotspot: could not configure the NetworkManager profile", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
