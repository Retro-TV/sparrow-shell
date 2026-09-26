#!/usr/bin/env python3
"""Choose a recording folder through the active XDG Desktop Portal."""

import os
import secrets
import sys

try:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError) as exc:
    print(f"Sparrow folder chooser requires Python GObject/GIO: {exc}", file=sys.stderr)
    raise SystemExit(2)


PORTAL = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
FILE_CHOOSER = "org.freedesktop.portal.FileChooser"
REQUEST = "org.freedesktop.portal.Request"


def main() -> int:
    initial_folder = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Videos/Recordings")
    token = "sparrow_recdir_" + secrets.token_hex(12)
    responses: dict[str, tuple[int, dict]] = {}
    request_handle = ""
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        def on_response(_connection, _sender, object_path, _interface, _signal, parameters, _data):
            response, results = parameters.unpack()
            responses[object_path] = (response, results)

        subscription = connection.signal_subscribe(
            PORTAL,
            REQUEST,
            "Response",
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            on_response,
            None,
        )

        options = {
            "handle_token": GLib.Variant("s", token),
            "directory": GLib.Variant("b", True),
            # The Pill releases its layer-shell focus while this standalone chooser is open.
            "modal": GLib.Variant("b", False),
            "current_folder": GLib.Variant("ay", list(os.fsencode(initial_folder) + b"\0")),
        }
        reply = connection.call_sync(
            PORTAL,
            PORTAL_PATH,
            FILE_CHOOSER,
            "OpenFile",
            GLib.Variant("(ssa{sv})", ("", "Choose recording folder", options)),
            GLib.VariantType.new("(o)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        request_handle = reply.unpack()[0]

        # Subscribe before opening to avoid losing even an immediate portal response.
        context = GLib.MainContext.default()
        while request_handle not in responses:
            context.iteration(True)

        response, results = responses[request_handle]
        connection.signal_unsubscribe(subscription)
        if response == 1:
            return 1
        if response != 0:
            print("The desktop portal could not choose a folder.", file=sys.stderr)
            return 2

        uris = results.get("uris", [])
        if not uris:
            print("The desktop portal returned no folder.", file=sys.stderr)
            return 2
        folder = Gio.File.new_for_uri(uris[0]).get_path()
        if not folder:
            print("The selected location is not a local folder.", file=sys.stderr)
            return 2
        sys.stdout.write(folder + "\n")
        return 0
    except (GLib.Error, OSError, ValueError) as exc:
        print(f"Could not open the desktop folder chooser: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
