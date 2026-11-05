pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

/**
 * Wallpaper bridge: keeps a warm in-memory snapshot of the wallpaper folder so
 * the wallpaper strip opens instantly without shelling out on demand. A
 * refresh first runs the thumbnail script (generating or updating 512px
 * previews), then re-lists the directory
 * newest-first and finally re-reads the state file wallpaper.sh maintains, so
 * `current` always names the wallpaper on screen. Thumbnails land before the
 * list so strip delegates never bind to a not-yet-existing file; a refresh
 * arriving while the pipeline runs sets `pending` and replays once the state
 * lands. Applying routes through wallpaper.sh so the picker shares the exact
 * transition, palette and state path with the random keybind.
 *
 * Wallpaper helpers are Sparrow-owned and default to ~/Pictures/wallpapers.
 *
 * Entries are plain objects: { path, name, mtime, thumb } where path is the
 * absolute source file, mtime its modification time in epoch seconds and
 * thumb the absolute path of the cached preview png.
 */
Singleton {
    id: root

    property var personalEntries: []
    readonly property string bundledWallpaperPath: Quickshell.shellPath("wallpapers/default.png")
    readonly property var entries: [{
        path: bundledWallpaperPath,
        name: "Sparrow Default",
        mtime: 0,
        thumb: bundledWallpaperPath,
        builtIn: true
    }].concat(personalEntries)
    readonly property int count: entries.length
    property string current: ""
    property bool pending: false
    property var outputWallpapers: ({})

    property string resolvedDir: ""
    readonly property string wpDir: Flags.wallpaperDir.length > 0 ? Flags.wallpaperDir
        : (resolvedDir.length > 0 ? resolvedDir : Quickshell.env("HOME") + "/Pictures/wallpapers")
    readonly property string thumbDir: (Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")) + "/sparrow-shell/wallpaper-thumbs/"
    readonly property string thumbScript: Quickshell.shellPath("scripts/wallpaper-thumbs.sh")
    readonly property string setScript: Quickshell.shellPath("scripts/wallpaper.sh")
    readonly property string stateFile: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/sparrow-shell/wallpaper"
    readonly property string outputMapFile: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/sparrow-shell/wallpaper-map"
    readonly property string dirStateFile: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/sparrow-shell/wallpaper-dir"

    onWpDirChanged: refresh()

    function loadOutputWallpapers(text) {
        var next = {};
        var lines = text.split("\n");
        for (var i = 0; i < lines.length; i++) {
            var tab = lines[i].indexOf("\t");
            if (tab > 0 && tab < lines[i].length - 1)
                next[lines[i].slice(0, tab)] = lines[i].slice(tab + 1).trim();
        }
        outputWallpapers = next;
    }

    function wallpaperForOutput(outputName) {
        return outputWallpapers[outputName] || current;
    }

    FileView {
        id: outputMapFile
        path: root.outputMapFile
        blockLoading: true
        watchChanges: true
        printErrors: false
        onLoaded: root.loadOutputWallpapers(outputMapFile.text())
        onFileChanged: reload()
        onLoadFailed: root.outputWallpapers = ({})
    }

    FileView {
        id: dirFile
        path: root.dirStateFile
        blockLoading: true
        watchChanges: true
        printErrors: false
        onLoaded: root.resolvedDir = dirFile.text().trim()
        onFileChanged: reload()
        onLoadFailed: root.resolvedDir = ""
    }

    function refresh() {
        if (resolveProc.running || thumbProc.running || listProc.running || stateProc.running) {
            pending = true;
            return;
        }
        /**
         * Re-resolve the folder first when autodetect is in play: it only runs
         * inside wallpaper.sh, so a shell restart used to leave the strip on
         * the stale state file. An explicit folder skips that hop entirely and
         * swaps straight away.
         */
        if (Flags.wallpaperDir.length > 0) {
            thumbProc.running = true;
            return;
        }
        resolveProc.command = ["bash", root.setScript, "resolve"];
        resolveProc.running = true;
    }

    function contextArgs() {
        var names = Niri.outputs.map(function(output) { return output.name; });
        return [Niri.focusedOutput, names.join(",")];
    }

    function startSessionRestore() {
        var names = Niri.outputs.map(function(output) { return output.name; }).sort().join(",");
        if (operationBusy || names.length === 0 || names === initializedOutputs)
            return;
        initializedOutputs = names;
        startupProc.command = ["bash", root.setScript, "init"].concat(contextArgs());
        startupProc.running = true;
    }

    property string initializedOutputs: ""

    function next() {
        actionRevision++;
        // Coalesce selections by recency: an older queued selection must not
        // overwrite a newer manual choice when the active helper finishes.
        queuedApply = "";
        queuedOutput = "";
        if (operationBusy) { queuedNext = true; return; }
        queuedNext = false;
        nextProc.command = ["bash", root.setScript, "next"].concat(contextArgs());
        nextProc.running = true;
    }

    Process {
        id: resolveProc
        onExited: thumbProc.running = true
    }

    /**
     * wallpaper.sh blocks through the whole transition (awww wave, matugen,
     * reload), easily 1-2s; a pick landing in that window used to be silently
     * swallowed. Now the newest request is queued and replayed once the
     * running transition exits, so rapid iteration converges on the last pick.
     */
    property string queuedApply: ""
    property string queuedOutput: ""

    function apply(path, output) {
        actionRevision++;
        queuedNext = false;
        var out = output === undefined ? "" : output;
        if (operationBusy) {
            queuedApply = path;
            queuedOutput = out;
            return;
        }
        queuedApply = "";
        queuedOutput = "";
        applyProc.command = out.length > 0
            ? ["bash", root.setScript, "set", path, out].concat(contextArgs())
            : ["bash", root.setScript, "set", path, ""].concat(contextArgs());
        applyProc.running = true;
    }

    // Action-engine requests share this owner and its helper, never a second
    // wallpaper controller. Busy requests fail explicitly instead of superseding.
    property bool queuedNext: false
    property bool queuedRecolor: false
    readonly property bool operationBusy: actionBusy || applyProc.running || nextProc.running || startupProc.running || recolorProc.running

    function drainRequests() {
        if (operationBusy) return;
        if (queuedApply.length) {
            var path = queuedApply;
            var output = queuedOutput;
            queuedApply = "";
            queuedOutput = "";
            apply(path, output);
        } else if (queuedNext) { queuedNext = false; next(); }
        else if (queuedRecolor) { queuedRecolor = false; recolor(); }
        else startSessionRestore();
    }
    function recolor() {
        actionRevision++;
        if (operationBusy) { queuedRecolor = true; return; }
        recolorProc.running = true;
    }
    Process {
        id: recolorProc
        command: ["bash", root.setScript, "recolor"]
        stderr: StdioCollector {
            onStreamFinished: if (this.text.trim().length) console.warn(this.text.trim())
        }
        onExited: root.drainRequests()
    }
    property int actionRevision: 0
    property int actionSerial: 0
    property var actionCallback: null
    property var actionAccepted: null
    readonly property bool actionBusy: actionCallback !== null

    function runAction(kind, path, output, callback, accepted) {
        if (kind !== "set" && kind !== "recolor") {
            callback({ok:false, accepted:false, message:"Unsupported wallpaper operation"}); return;
        }
        if (operationBusy || queuedApply.length || queuedNext || queuedRecolor) {
            callback({ok: false, accepted: false, message: "Wallpaper owner is busy"});
            return;
        }
        actionSerial++;
        actionCallback = callback;
        actionAccepted = accepted || null;
        actionRevision++;
        actionProc.command = kind === "recolor"
            ? ["bash", root.setScript, "recolor"].concat(contextArgs())
            : ["bash", root.setScript, "set", path, output].concat(contextArgs());
        actionProc.running = true;
    }

    Process {
        id: actionProc
        onStarted: if (root.actionAccepted) root.actionAccepted()
        onRunningChanged: if (!running) {
            let serial = root.actionSerial;
            Qt.callLater(function() {
            if (root.actionSerial === serial && root.actionCallback) {
                var callback = root.actionCallback;
                root.actionCallback = null;
                root.actionAccepted = null;
                callback({ok:false, accepted:false, message:"Wallpaper helper did not complete"});
                root.drainRequests();
            }
            });
        }
        stderr: StdioCollector { id: actionErrors }
        onExited: (exitCode, exitStatus) => {
            var callback = root.actionCallback;
            root.actionCallback = null;
            root.actionAccepted = null;
            stateProc.running = true;
            if (callback) callback({ok: exitCode === 0, accepted: true,
                applied: exitCode === 0, guarantee: "degraded",
                message: actionErrors.text.trim() || "Wallpaper helper failed; state may have changed"});
            Qt.callLater(root.drainRequests);
        }
    }

    function trash(path) {
        trashProc.command = ["gio", "trash", path];
        trashProc.running = true;
        var kept = [];
        for (var i = 0; i < personalEntries.length; i++)
            if (personalEntries[i].path !== path)
                kept.push(personalEntries[i]);
        personalEntries = kept;
    }

    Process {
        id: trashProc
        onExited: function(exitCode) {
            if (exitCode !== 0)
                root.refresh();
        }
    }

    Process {
        id: thumbProc
        command: ["bash", root.thumbScript, root.wpDir]
        onExited: listProc.running = true
    }

    Process {
        id: listProc
        command: ["sh", "-c", "if [ -d \"$1\" ]; then find \"$1\" -type f \\( -iname '*.jpg' -o -iname '*.png' -o -iname '*.gif' -o -iname '*.webp' -o -iname '*.mp4' -o -iname '*.webm' -o -iname '*.mkv' -o -iname '*.mov' \\) -printf '%T@\\t%p\\n' | sort -rn; fi", "_", root.wpDir]
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.split("\n");
                var out = [];
                for (var i = 0; i < lines.length; i++) {
                    var tab = lines[i].indexOf("\t");
                    if (tab < 1)
                        continue;
                    var path = lines[i].substring(tab + 1);
                    var name = path.substring(path.lastIndexOf("/") + 1);
                    out.push({
                        path: path,
                        name: name,
                        mtime: parseFloat(lines[i].substring(0, tab)),
                        thumb: root.thumbDir + name + ".png"
                    });
                }
                root.personalEntries = out;
                stateProc.running = true;
            }
        }
    }

    Process {
        id: stateProc
        command: ["sh", "-c", "cat \"$1\" 2>/dev/null || true", "_", root.stateFile]
        stdout: StdioCollector {
            onStreamFinished: {
                root.current = this.text.trim();
                outputMapFile.reload();
                if (root.pending) {
                    root.pending = false;
                    Qt.callLater(root.refresh);
                }
            }
        }
    }

    Process {
        id: applyProc
        stderr: StdioCollector {
            onStreamFinished: if (this.text.trim().length > 0) console.warn(this.text.trim())
        }
        onExited: {
            stateProc.running = true;
            Qt.callLater(root.drainRequests);
        }
    }

    Process {
        id: nextProc
        stderr: StdioCollector {
            onStreamFinished: if (this.text.trim().length > 0) console.warn(this.text.trim())
        }
        onExited: { root.refresh(); Qt.callLater(root.drainRequests); }
    }

    Connections {
        target: Niri
        function onOutputsChanged() { root.startSessionRestore(); }
    }

    Process {
        id: startupProc
        stderr: StdioCollector {
            onStreamFinished: if (this.text.trim().length > 0) console.warn(this.text.trim())
        }
        onExited: {
            outputMapFile.reload();
            root.refresh();
            Qt.callLater(root.drainRequests);
        }
    }

    Component.onCompleted: Qt.callLater(root.startSessionRestore)
}
