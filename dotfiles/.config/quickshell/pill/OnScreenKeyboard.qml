import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import "Singletons"

// Sparrow's tablet-friendly desktop keyboard. It is deliberately a separate
// overlay: it never reserves a tile or changes the layout of other windows.
Scope {
    id: root

    property bool opened: false
    property var held: ({})
    readonly property int keyWidth: 48
    readonly property int keyHeight: 44

    readonly property var rows: [
        [ {l:"Esc",c:1,t:"normal"}, {l:"F1",c:59,t:"normal"}, {l:"F2",c:60,t:"normal"}, {l:"F3",c:61,t:"normal"}, {l:"F4",c:62,t:"normal"}, {l:"F5",c:63,t:"normal"}, {l:"F6",c:64,t:"normal"}, {l:"F7",c:65,t:"normal"}, {l:"F8",c:66,t:"normal"}, {l:"F9",c:67,t:"normal"}, {l:"F10",c:68,t:"normal"}, {l:"F11",c:87,t:"normal"}, {l:"F12",c:88,t:"normal"}, {l:"Prt",c:99,t:"normal"}, {l:"Del",c:111,t:"normal"} ],
        [ {l:"`",c:41,t:"normal"}, {l:"1",c:2,t:"normal"}, {l:"2",c:3,t:"normal"}, {l:"3",c:4,t:"normal"}, {l:"4",c:5,t:"normal"}, {l:"5",c:6,t:"normal"}, {l:"6",c:7,t:"normal"}, {l:"7",c:8,t:"normal"}, {l:"8",c:9,t:"normal"}, {l:"9",c:10,t:"normal"}, {l:"0",c:11,t:"normal"}, {l:"-",c:12,t:"normal"}, {l:"=",c:13,t:"normal"}, {l:"Backspace",c:14,t:"wide"} ],
        [ {l:"Tab",c:15,t:"wide"}, {l:"Q",c:16,t:"normal"}, {l:"W",c:17,t:"normal"}, {l:"E",c:18,t:"normal"}, {l:"R",c:19,t:"normal"}, {l:"T",c:20,t:"normal"}, {l:"Y",c:21,t:"normal"}, {l:"U",c:22,t:"normal"}, {l:"I",c:23,t:"normal"}, {l:"O",c:24,t:"normal"}, {l:"P",c:25,t:"normal"}, {l:"[",c:26,t:"normal"}, {l:"]",c:27,t:"normal"}, {l:"\\",c:43,t:"normal"} ],
        [ {l:"Caps",c:58,t:"wide"}, {l:"A",c:30,t:"normal"}, {l:"S",c:31,t:"normal"}, {l:"D",c:32,t:"normal"}, {l:"F",c:33,t:"normal"}, {l:"G",c:34,t:"normal"}, {l:"H",c:35,t:"normal"}, {l:"J",c:36,t:"normal"}, {l:"K",c:37,t:"normal"}, {l:"L",c:38,t:"normal"}, {l:";",c:39,t:"normal"}, {l:"'",c:40,t:"normal"}, {l:"Enter",c:28,t:"wide"} ],
        [ {l:"Shift",c:42,t:"mod"}, {l:"Z",c:44,t:"normal"}, {l:"X",c:45,t:"normal"}, {l:"C",c:46,t:"normal"}, {l:"V",c:47,t:"normal"}, {l:"B",c:48,t:"normal"}, {l:"N",c:49,t:"normal"}, {l:"M",c:50,t:"normal"}, {l:",",c:51,t:"normal"}, {l:".",c:52,t:"normal"}, {l:"/",c:53,t:"normal"}, {l:"Shift",c:54,t:"mod"}, {l:"↑",c:103,t:"normal"} ],
        [ {l:"Ctrl",c:29,t:"mod"}, {l:"Super",c:125,t:"mod"}, {l:"Alt",c:56,t:"mod"}, {l:"Space",c:57,t:"normal"}, {l:"Alt",c:100,t:"mod"}, {l:"Ctrl",c:97,t:"mod"}, {l:"←",c:105,t:"normal"}, {l:"↓",c:108,t:"normal"}, {l:"→",c:106,t:"normal"} ],
        [ {l:"Home",c:102,t:"normal"}, {l:"End",c:107,t:"normal"}, {l:"PgUp",c:104,t:"normal"}, {l:"PgDn",c:109,t:"normal"}, {l:"Insert",c:110,t:"normal"}, {l:"Menu",c:139,t:"normal"}, {l:"Pause",c:119,t:"normal"} ]
    ]

    function runKey(code, down) {
        var p = Qt.createQmlObject('import Quickshell.Io; Process {}', root);
        p.command = ["ydotool", "key", String(code) + ":" + (down ? "1" : "0")];
        p.running = true;
        p.exited.connect(function() { p.destroy(); });
    }

    function tap(key) {
        runKey(key.c, true);
        runKey(key.c, false);
    }

    function toggleHeld(key) {
        var k = String(key.c);
        var active = !!held[k];
        runKey(key.c, !active);
        var next = Object.assign({}, held);
        if (active) delete next[k]; else next[k] = true;
        held = next;
    }

    function releaseAll() {
        Object.keys(held).forEach(function(k) { runKey(Number(k), false); });
        held = {};
    }

    IpcHandler {
        target: "osk"
        function toggle(): void { root.opened = !root.opened; }
        function open(): void { root.opened = true; }
        function close(): void { root.opened = false; root.releaseAll(); }
    }

    GlobalShortcut {
        appid: "quickshell"
        name: "oskToggle"
        description: "Toggle Sparrow desktop keyboard"
        onPressed: root.opened = !root.opened
    }

    Loader {
        active: root.opened
        sourceComponent: PanelWindow {
            id: keyboardWindow
            visible: root.opened
            anchors { left: true; right: true; bottom: true }
            implicitHeight: keyboardCard.implicitHeight + 24
            exclusiveZone: 0
            color: "transparent"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "sparrow-osk"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

            Rectangle {
                id: keyboardCard
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12 }
                implicitHeight: content.implicitHeight + 24
                radius: 18
                color: Qt.alpha(Theme.cardBot, 0.98)
                border.width: 1
                border.color: Theme.border

                Column {
                    id: content
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                    spacing: 6

                    RowLayout {
                        width: parent.width
                        height: 28
                        Text { text: "Sparrow keyboard"; color: Theme.cream; font.family: Theme.font; font.pixelSize: 13; Layout.fillWidth: true }
                        Rectangle {
                            width: 62; height: 26; radius: 13; color: Theme.cardTop
                            Text { anchors.centerIn: parent; text: "hide"; color: Theme.subtle; font.family: Theme.font; font.pixelSize: 12 }
                            MouseArea { anchors.fill: parent; onClicked: { root.opened = false; root.releaseAll(); } }
                        }
                    }

                    Repeater {
                        model: root.rows
                        delegate: Row {
                            width: content.width
                            height: root.keyHeight
                            spacing: 5
                            Repeater {
                                model: modelData
                                delegate: Rectangle {
                                    required property var modelData
                                    width: modelData.t === "wide" ? root.keyWidth * 1.65 : modelData.t === "mod" ? root.keyWidth * 1.35 : root.keyWidth
                                    height: root.keyHeight
                                    radius: 9
                                    color: mouse.pressed || !!root.held[String(modelData.c)] ? Theme.verm : Theme.cardTop
                                    border.width: 1
                                    border.color: Theme.border
                                    Text { anchors.centerIn: parent; text: modelData.l; color: Theme.bright; font.family: Theme.font; font.pixelSize: modelData.l.length > 5 ? 11 : 14 }
                                    MouseArea {
                                        id: mouse
                                        anchors.fill: parent
                                        onPressed: modelData.t === "mod" ? root.toggleHeld(modelData) : root.tap(modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
