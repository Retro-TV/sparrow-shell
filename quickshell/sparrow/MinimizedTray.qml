import QtQuick

// Niri has no special:minimized workspace. Keep this historical layout slot
// inert until a native dynamic-workspace design is explicitly chosen.
Row {
    property real s: 1
    property string screenName: ""
    readonly property int count: 0
}
