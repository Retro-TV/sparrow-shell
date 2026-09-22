pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property string currentPath: ""

    readonly property string statePath: (Quickshell.env("XDG_STATE_HOME")
        || (Quickshell.env("HOME") + "/.local/state")) + "/sparrow-shell/wallpaper"
    readonly property string thumbDir: (Quickshell.env("XDG_CACHE_HOME")
        || (Quickshell.env("HOME") + "/.cache")) + "/sparrow-shell/wallpaper-thumbs/"
    readonly property string source: {
        var path = currentPath.trim();
        if (!path)
            return "";
        var name = path.substring(path.lastIndexOf("/") + 1);
        if (/\.(mp4|webm|mkv|mov)$/i.test(path))
            return thumbDir + name + ".png";
        return path;
    }

    FileView {
        id: wallpaperState
        path: root.statePath
        blockLoading: true
        watchChanges: true
        printErrors: false

        onLoaded: root.currentPath = wallpaperState.text().trim()
        onFileChanged: reload()
        onLoadFailed: root.currentPath = ""
    }
}
