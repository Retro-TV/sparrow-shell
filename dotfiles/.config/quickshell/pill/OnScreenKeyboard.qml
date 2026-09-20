import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import "Singletons"

// Tablet keyboard with ANSI 75% geometry. Rows share one exact outer width;
// variable-width keys absorb the natural spacing difference so the frame stays
// rectangular like a physical keyboard rather than becoming a ragged key list.
Scope {
    id: root

    property bool opened: false
    property var latched: ({})

    readonly property real sizeScale: Math.max(0.78, Math.min(1.18, Flags.oskScale))
    readonly property int unit: Math.round(44 * sizeScale)
    readonly property int keyHeight: Math.round(42 * sizeScale)
    readonly property int gap: Math.round(5 * sizeScale)
    readonly property int boardWidth: unit * 16 + gap * 15
    readonly property int pad: Math.round(12 * sizeScale)
    readonly property int toolbarHeight: Math.round(30 * sizeScale)

    readonly property var rows: [
        [
            {l:"Esc",c:1},{l:"F1",c:59},{l:"F2",c:60},{l:"F3",c:61},{l:"F4",c:62},
            {l:"F5",c:63},{l:"F6",c:64},{l:"F7",c:65},{l:"F8",c:66},{l:"F9",c:67},
            {l:"F10",c:68},{l:"F11",c:87},{l:"F12",c:88},{l:"Prt",c:99},{l:"Del",c:111},
            {l:"Ins",c:110}
        ],
        [
            {l:"\u0060",s:"~",c:41},{l:"1",s:"!",c:2},{l:"2",s:"@",c:3},{l:"3",s:"#",c:4},
            {l:"4",s:"$",c:5},{l:"5",s:"%",c:6},{l:"6",s:"^",c:7},{l:"7",s:"&",c:8},
            {l:"8",s:"*",c:9},{l:"9",s:"(",c:10},{l:"0",s:")",c:11},{l:"-",s:"_",c:12},
            {l:"=",s:"+",c:13},{l:"Backspace",c:14,u:2,fill:true},{l:"Home",c:102}
        ],
        [
            {l:"Tab",c:15,u:1.5},{l:"Q",c:16},{l:"W",c:17},{l:"E",c:18},{l:"R",c:19},
            {l:"T",c:20},{l:"Y",c:21},{l:"U",c:22},{l:"I",c:23},{l:"O",c:24},{l:"P",c:25},
            {l:"[",s:"{",c:26},{l:"]",s:"}",c:27},{l:"\\",s:"|",c:43,u:1.5,fill:true},{l:"PgUp",c:104}
        ],
        [
            {l:"Caps",c:58,u:1.75},{l:"A",c:30},{l:"S",c:31},{l:"D",c:32},{l:"F",c:33},
            {l:"G",c:34},{l:"H",c:35},{l:"J",c:36},{l:"K",c:37},{l:"L",c:38},
            {l:";",s:":",c:39},{l:"'",s:"\"",c:40},{l:"Enter",c:28,u:2.25,fill:true},{l:"PgDn",c:109}
        ],
        [
            {l:"Shift",c:42,u:2.25,t:"mod"},{l:"Z",c:44},{l:"X",c:45},{l:"C",c:46},
            {l:"V",c:47},{l:"B",c:48},{l:"N",c:49},{l:"M",c:50},{l:",",s:"<",c:51},
            {l:".",s:">",c:52},{l:"/",s:"?",c:53},{l:"Shift",c:54,u:1.75,t:"mod",fill:true},
            {l:"↑",c:103},{l:"End",c:107}
        ],
        [
            {l:"Ctrl",c:29,u:1.25,t:"mod"},{l:"Super",c:125,u:1.25,t:"mod"},
            {l:"Alt",c:56,u:1.25,t:"mod"},{l:"Space",c:57,u:5.5,fill:true},
            {l:"AltGr",c:100,u:1.25,t:"mod"},{l:"Menu",c:139,u:1.25},
            {l:"Ctrl",c:97,u:1.25,t:"mod"},{l:"←",c:105},{l:"↓",c:108},{l:"→",c:106}
        ]
    ]

    function isLatched(code) {
        return !!latched[String(code)];
    }

    function shifted() {
        return isLatched(42) || isLatched(54);
    }

    function toggleModifier(key) {
        var next = Object.assign({}, latched);
        var name = String(key.c);
        if (next[name])
            delete next[name];
        else
            next[name] = true;
        latched = next;
    }

    function sendKey(key) {
        if (key.t === "close") {
            opened = false;
            latched = {};
            return;
        }

        var mods = Object.keys(latched).map(function(k) { return Number(k); });
        var args = ["ydotool", "key", "--key-delay", "0"];
        for (var i = 0; i < mods.length; i++)
            args.push(String(mods[i]) + ":1");
        args.push(String(key.c) + ":1", String(key.c) + ":0");
        for (var j = mods.length - 1; j >= 0; j--)
            args.push(String(mods[j]) + ":0");
        Quickshell.execDetached(args);

        latched = {};
    }

    function toggle() {
        opened = !opened;
        if (!opened)
            latched = {};
    }

    function setScale(value) {
        Flags.oskScale = value;
    }

    IpcHandler {
        target: "osk"
        function toggle(): void { root.toggle(); }
        function open(): void { root.opened = true; }
        function close(): void { root.opened = false; root.latched = {}; }
    }

    GlobalShortcut {
        appid: "quickshell"
        name: "oskToggle"
        description: "Toggle the on-screen keyboard"
        onPressed: root.toggle()
    }

    Loader {
        active: root.opened

        sourceComponent: PanelWindow {
            id: keyboardWindow
            visible: root.opened
            anchors { left: true; right: true; top: true; bottom: true }
            exclusiveZone: 0
            color: "transparent"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "sparrow-osk"
            // Pointer/touch input still reaches the masked board, while the
            // previously focused app keeps keyboard focus for ydotool input.
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

            Rectangle {
                id: board
                readonly property real edge: 12
                readonly property real travelX: Math.max(0, keyboardWindow.width - width - edge * 2)
                readonly property real travelY: Math.max(0, keyboardWindow.height - height - edge * 2)
                x: edge + travelX * Math.max(0, Math.min(1, Flags.oskX))
                y: edge + travelY * Math.max(0, Math.min(1, Flags.oskY))
                width: root.boardWidth + root.pad * 2
                height: root.toolbarHeight + keys.implicitHeight + root.pad * 2 + root.gap
                radius: Math.round(15 * root.sizeScale)
                color: Theme.cardBot
                border.width: 1
                border.color: Theme.border

                function savePosition() {
                    Flags.oskX = travelX > 0 ? Math.max(0, Math.min(1, (x - edge) / travelX)) : 0.5;
                    Flags.oskY = travelY > 0 ? Math.max(0, Math.min(1, (y - edge) / travelY)) : 1.0;
                }

                Rectangle {
                    id: toolbar
                    anchors { left: parent.left; right: parent.right; top: parent.top }
                    height: root.toolbarHeight + root.pad
                    color: "transparent"

                    Rectangle {
                        id: dragGrip
                        anchors { left: parent.left; right: sizeControls.left; top: parent.top; bottom: parent.bottom }
                        anchors.leftMargin: root.pad
                        anchors.rightMargin: root.gap
                        color: "transparent"

                        Row {
                            anchors.centerIn: parent
                            spacing: 4
                            Repeater {
                                model: 3
                                Rectangle {
                                    width: Math.round(18 * root.sizeScale)
                                    height: Math.max(2, Math.round(3 * root.sizeScale))
                                    radius: height / 2
                                    color: dragger.active ? Theme.onGlow : Theme.dim
                                }
                            }
                        }

                        DragHandler {
                            id: dragger
                            target: board
                            xAxis.minimum: board.edge
                            xAxis.maximum: keyboardWindow.width - board.width - board.edge
                            yAxis.minimum: board.edge
                            yAxis.maximum: keyboardWindow.height - board.height - board.edge
                            onActiveChanged: if (!active) board.savePosition()
                        }
                    }

                    Row {
                        id: sizeControls
                        anchors { right: parent.right; rightMargin: root.pad; verticalCenter: parent.verticalCenter }
                        spacing: root.gap

                        Repeater {
                            model: [
                                { label: "S", value: 0.78 },
                                { label: "M", value: 1.0 },
                                { label: "L", value: 1.18 }
                            ]
                            delegate: Rectangle {
                                required property var modelData
                                width: root.toolbarHeight
                                height: root.toolbarHeight
                                radius: height / 2
                                color: Math.abs(root.sizeScale - modelData.value) < 0.03 ? Theme.vermLit : Theme.cardTop
                                border.width: 1
                                border.color: Theme.border
                                Text {
                                    anchors.centerIn: parent
                                    text: parent.modelData.label
                                    color: Theme.bright
                                    font.family: Theme.font
                                    font.pixelSize: Math.round(11 * root.sizeScale)
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: root.setScale(parent.modelData.value)
                                }
                            }
                        }

                        Rectangle {
                            width: root.toolbarHeight
                            height: root.toolbarHeight
                            radius: height / 2
                            color: closeMouse.pressed ? Theme.vermLit : Theme.cardTop
                            border.width: 1
                            border.color: Theme.border
                            Text {
                                anchors.centerIn: parent
                                text: "×"
                                color: Theme.bright
                                font.family: Theme.font
                                font.pixelSize: Math.round(17 * root.sizeScale)
                            }
                            MouseArea {
                                id: closeMouse
                                anchors.fill: parent
                                onClicked: root.sendKey({t: "close"})
                            }
                        }
                    }
                }

                Column {
                    id: keys
                    anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: root.pad }
                    width: root.boardWidth
                    spacing: root.gap

                    Repeater {
                        model: root.rows

                        delegate: RowLayout {
                            id: keyRow
                            required property var modelData
                            width: root.boardWidth
                            height: root.keyHeight
                            spacing: root.gap

                            Repeater {
                                model: keyRow.modelData

                                delegate: Rectangle {
                                    id: keycap
                                    required property var modelData
                                    Layout.preferredWidth: root.unit * (modelData.u || 1)
                                    Layout.minimumWidth: Layout.preferredWidth
                                    Layout.fillWidth: modelData.fill || false
                                    Layout.fillHeight: true
                                    radius: Math.round(7 * root.sizeScale)
                                    color: keyMouse.pressed || root.isLatched(modelData.c)
                                        ? Theme.vermLit : Theme.cardTop
                                    border.width: 1
                                    border.color: root.isLatched(modelData.c)
                                        ? Theme.onGlow : Theme.border

                                    Text {
                                        anchors.centerIn: parent
                                        text: root.shifted() && keycap.modelData.s
                                            ? keycap.modelData.s : keycap.modelData.l
                                        color: Theme.bright
                                        font.family: Theme.font
                                        font.pixelSize: Math.round((keycap.modelData.l.length > 5 ? 10 : 13) * root.sizeScale)
                                    }

                                    MouseArea {
                                        id: keyMouse
                                        anchors.fill: parent
                                        onClicked: keycap.modelData.t === "mod"
                                            ? root.toggleModifier(keycap.modelData)
                                            : root.sendKey(keycap.modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            mask: Region { item: board }
        }
    }
}
