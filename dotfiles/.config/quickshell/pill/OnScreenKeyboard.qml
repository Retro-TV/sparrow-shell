import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import "Singletons"

// Compact desktop keyboard based on end-4's full physical-keyboard layout.
// Modifiers are one-shot: tapping Super then Q emits Super+Q atomically.
Scope {
    id: root

    property bool opened: false
    property var latched: ({})
    readonly property int keyW: 44
    readonly property int keyH: 44
    readonly property int gap: 4

    readonly property var rows: [
        [
            {l:"Esc", c:1, t:"fn"}, {l:"F1", c:59, t:"fn"}, {l:"F2", c:60, t:"fn"}, {l:"F3", c:61, t:"fn"},
            {l:"F4", c:62, t:"fn"}, {l:"F5", c:63, t:"fn"}, {l:"F6", c:64, t:"fn"}, {l:"F7", c:65, t:"fn"},
            {l:"F8", c:66, t:"fn"}, {l:"F9", c:67, t:"fn"}, {l:"F10", c:68, t:"fn"}, {l:"F11", c:87, t:"fn"},
            {l:"F12", c:88, t:"fn"}, {l:"PrtSc", c:99, t:"fn"}, {l:"Del", c:111, t:"fn"}
        ],
        [
            {l:"\`", s:"~", c:41}, {l:"1", s:"!", c:2}, {l:"2", s:"@", c:3}, {l:"3", s:"#", c:4},
            {l:"4", s:"$", c:5}, {l:"5", s:"%", c:6}, {l:"6", s:"^", c:7}, {l:"7", s:"&", c:8},
            {l:"8", s:"*", c:9}, {l:"9", s:"(", c:10}, {l:"0", s:")", c:11}, {l:"-", s:"_", c:12},
            {l:"=", s:"+", c:13}, {l:"Backspace", c:14, t:"wide"}
        ],
        [
            {l:"Tab", c:15, t:"tab"}, {l:"q", s:"Q", c:16}, {l:"w", s:"W", c:17}, {l:"e", s:"E", c:18},
            {l:"r", s:"R", c:19}, {l:"t", s:"T", c:20}, {l:"y", s:"Y", c:21}, {l:"u", s:"U", c:22},
            {l:"i", s:"I", c:23}, {l:"o", s:"O", c:24}, {l:"p", s:"P", c:25}, {l:"[", s:"{", c:26},
            {l:"]", s:"}", c:27}, {l:"\\", s:"|", c:43, t:"wide"}
        ],
        [
            {l:"", c:0, t:"spacer"}, {l:"", c:0, t:"spacer"}, {l:"a", s:"A", c:30}, {l:"s", s:"S", c:31},
            {l:"d", s:"D", c:32}, {l:"f", s:"F", c:33}, {l:"g", s:"G", c:34}, {l:"h", s:"H", c:35},
            {l:"j", s:"J", c:36}, {l:"k", s:"K", c:37}, {l:"l", s:"L", c:38}, {l:";", s:":", c:39},
            {l:"'", s:"\"", c:40}, {l:"Enter", c:28, t:"wide"}
        ],
        [
            {l:"Shift", c:42, t:"modwide"}, {l:"z", s:"Z", c:44}, {l:"x", s:"X", c:45}, {l:"c", s:"C", c:46},
            {l:"v", s:"V", c:47}, {l:"b", s:"B", c:48}, {l:"n", s:"N", c:49}, {l:"m", s:"M", c:50},
            {l:",", s:"<", c:51}, {l:".", s:">", c:52}, {l:"/", s:"?", c:53}, {l:"Shift", c:54, t:"modwide"},
            {l:"↑", c:103}
        ],
        [
            {l:"Ctrl", c:29, t:"mod"}, {l:"Super", c:125, t:"mod"}, {l:"Alt", c:56, t:"mod"},
            {l:"Space", c:57, t:"space"}, {l:"AltGr", c:100, t:"mod"}, {l:"Menu", c:139},
            {l:"Ctrl", c:97, t:"mod"}, {l:"←", c:105}, {l:"↓", c:108}, {l:"→", c:106}
        ],
        [
            {l:"Home", c:102}, {l:"End", c:107}, {l:"PgUp", c:104}, {l:"PgDn", c:109},
            {l:"Insert", c:110}, {l:"Pause", c:119}
        ]
    ]

    function isLatched(code) { return !!latched[String(code)]; }

    function send(codes) {
        if (!codes || codes.length === 0) return;
        var args = ["ydotool", "key", "--key-delay", "0"];
        for (var i = 0; i < codes.length; i++) args.push(String(codes[i]) + ":1");
        for (var j = codes.length - 1; j >= 0; j--) args.push(String(codes[j]) + ":0");
        Quickshell.execDetached(args);
    }

    function tap(key) {
        var mods = Object.keys(latched).map(function(k) { return Number(k); });
        send(mods.concat([key.c]));
        latched = {};
    }

    function toggleModifier(key) {
        var next = Object.assign({}, latched);
        var name = String(key.c);
        if (next[name]) delete next[name]; else next[name] = true;
        latched = next;
    }

    function releaseAll() { latched = {}; }

    IpcHandler {
        target: "osk"
        function toggle(): void { root.opened = !root.opened; if (!root.opened) root.releaseAll(); }
        function open(): void { root.opened = true; }
        function close(): void { root.opened = false; root.releaseAll(); }
    }

    GlobalShortcut {
        appid: "quickshell"
        name: "oskToggle"
        description: "Toggle desktop on-screen keyboard"
        onPressed: { root.opened = !root.opened; if (!root.opened) root.releaseAll(); }
    }

    Loader {
        active: root.opened
        sourceComponent: PanelWindow {
            id: window
            visible: root.opened
            anchors { left: true; right: true; bottom: true }
            implicitHeight: card.implicitHeight + 24
            exclusiveZone: 0
            color: "transparent"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "sparrow-osk"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

            Rectangle {
                id: card
                anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; margins: 12 }
                width: 760
                implicitHeight: body.implicitHeight + 24
                radius: 18
                color: Theme.cardBot
                border.width: 1
                border.color: Theme.border

                Column {
                    id: body
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                    spacing: root.gap

                    RowLayout {
                        width: parent.width
                        height: 24
                        Text {
                            text: "Keyboard"
                            color: Theme.subtle
                            font.family: Theme.font
                            font.pixelSize: 12
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            width: 28; height: 24; radius: 12
                            color: closeMouse.pressed ? Theme.verm : Theme.cardTop
                            Text { anchors.centerIn: parent; text: "×"; color: Theme.bright; font.pixelSize: 18 }
                            MouseArea {
                                id: closeMouse
                                anchors.fill: parent
                                onClicked: { root.opened = false; root.releaseAll(); }
                            }
                        }
                    }

                    Repeater {
                        model: root.rows
                        delegate: Row {
                            required property var modelData
                            spacing: root.gap
                            width: implicitWidth
                            height: modelData[0].t === "fn" ? 30 : root.keyH
                            anchors.horizontalCenter: parent.horizontalCenter

                            Repeater {
                                model: parent.modelData
                                delegate: Rectangle {
                                    required property var modelData
                                    readonly property real scale: modelData.t === "wide" ? 1.65 :
                                        modelData.t === "tab" ? 1.65 :
                                        modelData.t === "modwide" ? 2.35 :
                                        modelData.t === "mod" ? 1.35 :
                                        modelData.t === "space" ? 4.8 :
                                        modelData.t === "spacer" ? 0.5 : 1
                                    width: root.keyW * scale
                                    height: modelData.t === "fn" ? 30 : root.keyH
                                    radius: 8
                                    color: modelData.t === "spacer" ? "transparent" :
                                        mouse.pressed || root.isLatched(modelData.c) ? Theme.verm : Theme.cardTop
                                    border.width: modelData.t === "spacer" ? 0 : 1
                                    border.color: Theme.border
                                    Text {
                                        anchors.centerIn: parent
                                        text: root.isLatched(modelData.c) && modelData.s ? modelData.s : modelData.l
                                        color: modelData.t === "spacer" ? "transparent" : Theme.bright
                                        font.family: Theme.font
                                        font.pixelSize: modelData.t === "fn" ? 10 : modelData.l.length > 5 ? 10 : 13
                                    }
                                    MouseArea {
                                        id: mouse
                                        anchors.fill: parent
                                        enabled: modelData.t !== "spacer"
                                        onClicked: modelData.t === "mod" || modelData.t === "modwide"
                                            ? root.toggleModifier(modelData) : root.tap(modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            mask: Region { item: card }
        }
    }
}
