pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import "Singletons"

/** Per-user provider credentials. Secrets stay in private XDG state, not flags.json. */
SettingsSurface {
    id: root

    backSurface: "settings"
    implicitHeight: content.implicitHeight
    readonly property string helper: Quickshell.shellPath("scripts/wallhaven-key.py")

    property string draft: ""
    property string note: ""
    property bool configured: false
    property bool busy: false
    property bool reveal: false

    function refresh() {
        if (statusProc.running)
            return;
        statusProc.running = true;
    }

    function saveKey() {
        if (busy || !draft.length)
            return;
        busy = true;
        note = "Saving…";
        saveProc.running = true;
    }

    function clearKey() {
        if (busy || !configured)
            return;
        busy = true;
        note = "Removing…";
        removeProc.running = true;
    }

    onOpenChanged: if (open) refresh()
    Component.onCompleted: if (open) refresh()

    Process {
        id: statusProc
        command: ["python3", root.helper, "status"]
        stdout: StdioCollector { id: statusOutput }
        onExited: function(exitCode) {
            if (exitCode !== 0) {
                root.note = "Could not read key status";
                return;
            }
            try {
                root.configured = Boolean(JSON.parse(statusOutput.text).configured);
                if (!root.busy)
                    root.note = root.configured ? "Key saved on this device" : "No key saved";
            } catch (error) {
                root.note = "Could not read key status";
            }
        }
    }

    Process {
        id: saveProc
        command: ["python3", root.helper, "set"]
        stdinEnabled: true
        stdout: StdioCollector { id: saveOutput }
        onStarted: {
            write(root.draft + "\n");
            root.draft = "";
            keyField.clear();
        }
        onExited: function(exitCode) {
            root.busy = false;
            if (exitCode !== 0) {
                root.note = "Could not save key";
                return;
            }
            root.configured = true;
            root.draft = "";
            keyField.clear();
            root.note = "Key saved on this device";
        }
    }

    Process {
        id: removeProc
        command: ["python3", root.helper, "remove"]
        stdout: StdioCollector { id: removeOutput }
        onExited: function(exitCode) {
            root.busy = false;
            if (exitCode !== 0) {
                root.note = "Could not remove key";
                return;
            }
            root.configured = false;
            root.draft = "";
            keyField.clear();
            root.note = "Key removed";
        }
    }

    Column {
        id: content
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        SettingsHeader { s: root.s; title: "API KEYS"; showBack: true }
        Item { width: 1; height: 10 * root.s }

        Text {
            width: parent.width - 24 * root.s
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Wallhaven"
            color: Theme.cream
            font.family: Theme.font
            font.pixelSize: 12.5 * root.s
            font.weight: Font.DemiBold
        }

        Item { width: 1; height: 8 * root.s }

        Rectangle {
            width: parent.width - 24 * root.s
            height: 34 * root.s
            anchors.horizontalCenter: parent.horizontalCenter
            radius: 7 * root.s
            color: Theme.frameBg

            TextField {
                id: keyField
                anchors.left: parent.left
                anchors.leftMargin: 9 * root.s
                anchors.right: revealLabel.left
                anchors.rightMargin: 7 * root.s
                anchors.verticalCenter: parent.verticalCenter
                background: null
                padding: 0
                color: Theme.cream
                font.family: Theme.font
                font.pixelSize: 11.5 * root.s
                placeholderText: root.configured ? "Enter a replacement key" : "Paste API key"
                placeholderTextColor: Theme.faint
                selectByMouse: true
                selectionColor: Theme.verm
                maximumLength: 512
                echoMode: root.reveal ? TextInput.Normal : TextInput.Password
                enabled: !root.busy
                onTextEdited: root.draft = text
                onAccepted: root.saveKey()
            }

            Text {
                id: revealLabel
                anchors.right: parent.right
                anchors.rightMargin: 9 * root.s
                anchors.verticalCenter: parent.verticalCenter
                text: root.reveal ? "Hide" : "Show"
                color: Theme.secondaryText
                font.family: Theme.font
                font.pixelSize: 9.5 * root.s
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -5 * root.s
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.reveal = !root.reveal
                }
            }
        }

        Item { width: 1; height: 9 * root.s }

        Row {
            width: parent.width - 24 * root.s
            height: 29 * root.s
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 7 * root.s

            Rectangle {
                width: 78 * root.s
                height: parent.height
                radius: 7 * root.s
                color: root.busy || !root.draft.length ? Theme.frameBg : Theme.verm
                opacity: root.busy || !root.draft.length ? 0.55 : 1
                Text {
                    anchors.centerIn: parent
                    text: "Save key"
                    color: Theme.cream
                    font.family: Theme.font
                    font.pixelSize: 10 * root.s
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: !root.busy && root.draft.length > 0
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.saveKey()
                }
            }

            Rectangle {
                width: 78 * root.s
                height: parent.height
                radius: 7 * root.s
                color: Theme.frameBg
                opacity: root.configured && !root.busy ? 1 : 0.45
                Text {
                    anchors.centerIn: parent
                    text: "Remove"
                    color: Theme.secondaryText
                    font.family: Theme.font
                    font.pixelSize: 10 * root.s
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: root.configured && !root.busy
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.clearKey()
                }
            }

            Text {
                width: parent.width - 163 * root.s
                height: parent.height
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                text: root.note
                color: Theme.subtle
                font.family: Theme.font
                font.pixelSize: 9 * root.s
            }
        }

        Item { width: 1; height: 7 * root.s }
        Text {
            width: parent.width - 24 * root.s
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Stored privately on this device."
            color: Theme.faint
            font.family: Theme.font
            font.pixelSize: 9 * root.s
        }
    }
}
