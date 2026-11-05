pragma Singleton
import QtQml
QtObject {
    property var probeResult: ({supported:true, value:"/test/current.png", revision:"0"})
    property int probeRequests: 0
    property bool failStart: false
    property bool holdProbes: false
    property bool recoverySafe: true
    property bool holdMutations: false
    property var heldProcesses: []
    property var commands: []
    function releaseProcesses() {
        var held = heldProcesses; heldProcesses = [];
        held.forEach(function(p) { p.finish(); });
    }
    function env(name) { return "/test"; }
    function shellPath(path) { return path; }
}
