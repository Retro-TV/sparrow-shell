import QtQml
import Quickshell
QtObject {
    id: root
    default property list<QtObject> data
    property bool running: false
    property bool stdinEnabled: false
    property var command: []
    property QtObject stdout
    property QtObject stderr
    signal started()
    signal exited(int exitCode, int exitStatus)
    property var request: ({})
    function write(text) { Quickshell.probeRequests++; request = JSON.parse(text); }
    function signal(number) {
        Quickshell.heldProcesses = Quickshell.heldProcesses.filter(function(p) { return p !== root; });
        root.running = false;
    }
    function finish() {
        root.running = false;
        root.exited(0, 0);
    }
    onRunningChanged: if (running) Qt.callLater(function() {
        Quickshell.commands = Quickshell.commands.concat([root.command]);
        if (Quickshell.failStart) { Quickshell.failStart = false; root.running = false; return; }
        root.started();
        if ((Quickshell.holdMutations && ["set", "next", "recolor"].indexOf(root.command[2]) >= 0)
                || (Quickshell.holdProbes && root.command[1].indexOf("action-probe.py") >= 0)) {
            Quickshell.heldProcesses = Quickshell.heldProcesses.concat([root]); return;
        }
        if (root.stdout) {
            var observation = Object.assign({}, Quickshell.probeResult);
            if (root.request.type === "recovery") observation.safe = Quickshell.recoverySafe;
            if (root.request.type === "appearance.mode") {
                observation.persistedMode = root.request.params.value;
                observation.persistedPaletteMode = "dynamic";
            }
            root.stdout.text = root.command[1].indexOf("action-probe.py") >= 0 ? JSON.stringify(observation) : "";
        }
        root.finish();
    })
}
