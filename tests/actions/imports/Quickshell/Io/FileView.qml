import QtQml
QtObject {
    property string path: ""
    property bool blockLoading: false
    property bool watchChanges: false
    property bool printErrors: false
    signal loaded()
    signal fileChanged()
    signal loadFailed()
    function text() { return ""; }
    function reload() { loaded(); }
}
