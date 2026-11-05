import QtQml
QtObject {
    property real startedAt: Date.now()
    function restart() { startedAt=Date.now(); }
    function elapsedMs() { return Date.now()-startedAt; }
}
