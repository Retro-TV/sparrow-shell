import QtQuick
import Quickshell
import Quickshell.Wayland

ShellRoot {
    PanelWindow {
        id: pillWindow

        anchors {
            top: true
        }

        implicitWidth: 180
        implicitHeight: 44

        color: "transparent"
        exclusionMode: ExclusionMode.Ignore

        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "sparrow-shell"

        Rectangle {
            anchors.fill: parent
            radius: 22
            color: "#181818"

            Text {
                anchors.centerIn: parent
                text: "Sparrow"
                color: "white"
                font.pixelSize: 14
            }
        }
    }
}
