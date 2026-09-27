pragma ComponentBehavior: Bound

import QtQuick
import Quickshell.Io
import "lib/keybind-catalog.js" as Catalog
import "Singletons"

PillSurface {
    id: root

    mTop: 15
    mLeft: 19
    mRight: 19
    mBottom: 14
    implicitHeight: content.implicitHeight

    signal requestSurface(string name)

    readonly property var effectiveKeys: {
        var result = ({});
        for (var i = 0; i < Catalog.entries.length; i++)
            result[Catalog.entries[i].id] = Catalog.entries[i].key;

        var lines = bindsFile.text().split("\n");
        for (var j = 0; j < lines.length; j++) {
            var match = lines[j].match(/^\s*\/\/ override: ([a-z0-9-]+) = (.+)$/);
            if (match)
                result[match[1]] = match[2];
        }
        return result;
    }

    function shortcut(id) {
        return effectiveKeys[id] || "—";
    }

    function activateAction(name) {
        if (name === "done") {
            requestClose();
            return;
        }
        if (name.length > 0)
            requestSurface(name);
    }

    onActiveChanged: if (active) bindsFile.reload()

    FileView {
        id: bindsFile
        path: Niri.configPath.replace(/\/config\.kdl$/, "/sparrow/user-binds.kdl")
        blockLoading: true
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
    }

    Column {
        id: content
        width: parent.width
        spacing: 0

        SettingsHeader {
            s: root.s
            title: "GETTING STARTED"
            showBack: true
        }

        Item { width: 1; height: 8 * root.s }

        Text {
            width: parent.width
            text: "The Pill is Sparrow’s main control. Hover to expand it, then choose an icon—or use a shortcut."
            color: Theme.subtle
            font.family: Theme.font
            font.pixelSize: 11.5 * root.s
            wrapMode: Text.WordWrap
            lineHeight: 1.2
        }

        Item { width: 1; height: 12 * root.s }

        Text {
            text: "QUICK SHORTCUTS"
            color: Theme.faint
            font.family: Theme.font
            font.pixelSize: 9 * root.s
            font.weight: Font.DemiBold
            font.letterSpacing: 1.1 * root.s
        }

        Column {
            width: parent.width
            spacing: 1 * root.s

            Repeater {
                model: [
                    { id: "launcher", title: "Launcher", detail: "Search installed apps", action: "launcher" },
                    { id: "wallpaper-picker", title: "Wallpaper", detail: "Choose one · next: " + root.shortcut("wallpaper-next"), action: "wallpaper" },
                    { id: "lock", title: "Lock", detail: "Lock the session", action: "" },
                    { id: "recorder", title: "Recorder", detail: "Open screen recording controls", action: "recorder" }
                ]

                delegate: Item {
                    id: shortcutRow
                    required property var modelData
                    width: parent.width
                    height: 39 * root.s

                    readonly property bool actionable: modelData.action.length > 0

                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: 2 * root.s
                        anchors.bottomMargin: 2 * root.s
                        radius: 7 * root.s
                        color: shortcutMouse.containsMouse ? Theme.frameBg : "transparent"
                        Behavior on color { ColorAnimation { duration: Motion.fast } }
                    }

                    Column {
                        anchors.left: parent.left
                        anchors.leftMargin: 8 * root.s
                        anchors.right: keycap.left
                        anchors.rightMargin: 8 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2 * root.s

                        Text {
                            text: shortcutRow.modelData.title
                            color: Theme.cream
                            font.family: Theme.font
                            font.pixelSize: 11.5 * root.s
                            font.weight: Font.DemiBold
                        }
                        Text {
                            width: parent.width
                            text: shortcutRow.modelData.detail
                            color: Theme.subtle
                            font.family: Theme.font
                            font.pixelSize: 9.5 * root.s
                            elide: Text.ElideRight
                        }
                    }

                    Rectangle {
                        id: keycap
                        anchors.right: parent.right
                        anchors.rightMargin: 7 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        width: keyText.implicitWidth + 14 * root.s
                        height: 23 * root.s
                        radius: 6 * root.s
                        color: Theme.frameBg
                        border.width: 1
                        border.color: Theme.hairSoft

                        Text {
                            id: keyText
                            anchors.centerIn: parent
                            text: root.shortcut(shortcutRow.modelData.id)
                            color: Theme.cream
                            font.family: Theme.font
                            font.pixelSize: 9.5 * root.s
                            font.weight: Font.DemiBold
                        }
                    }

                    MouseArea {
                        id: shortcutMouse
                        anchors.fill: parent
                        enabled: shortcutRow.actionable
                        hoverEnabled: true
                        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: root.activateAction(shortcutRow.modelData.action)
                    }
                }
            }
        }

        Item { width: 1; height: 9 * root.s }
        Rectangle { width: parent.width; height: 1; color: Theme.hairSoft }
        Item { width: 1; height: 8 * root.s }

        Text {
            width: parent.width
            text: "Wallpapers use your configured folder; Sparrow Default is always available. Dynamic colors are the default and follow the wallpaper; choose a palette style under Settings → Appearance."
            color: Theme.subtle
            font.family: Theme.font
            font.pixelSize: 10.5 * root.s
            wrapMode: Text.WordWrap
            lineHeight: 1.18
        }

        Item { width: 1; height: 5 * root.s }

        Text {
            width: parent.width
            text: "Click the Pill’s gear for Settings. Keybinds there lists and edits shortcuts."
            color: Theme.subtle
            font.family: Theme.font
            font.pixelSize: 10.5 * root.s
            wrapMode: Text.WordWrap
            lineHeight: 1.18
        }

        Item { width: 1; height: 12 * root.s }

        Row {
            width: parent.width
            spacing: 6 * root.s

            Repeater {
                model: [
                    { label: "Launcher", action: "launcher", done: false },
                    { label: "Wallpaper", action: "wallpaper", done: false },
                    { label: "Keybinds", action: "keybinds", done: false },
                    { label: "Done", action: "done", done: true }
                ]

                delegate: Rectangle {
                    id: actionButton
                    required property var modelData
                    width: actionLabel.implicitWidth + 18 * root.s
                    height: 27 * root.s
                    radius: 7 * root.s
                    color: actionMouse.containsMouse
                        ? (modelData.done ? Theme.vermLit : Theme.frameBg)
                        : (modelData.done ? Qt.alpha(Theme.vermLit, 0.18) : "transparent")
                    border.width: modelData.done ? 1 : 0
                    border.color: Qt.alpha(Theme.vermLit, 0.42)

                    Text {
                        id: actionLabel
                        anchors.centerIn: parent
                        text: actionButton.modelData.label
                        color: actionButton.modelData.done ? Theme.cream : Theme.iconDim
                        font.family: Theme.font
                        font.pixelSize: 9.5 * root.s
                        font.weight: Font.DemiBold
                    }

                    MouseArea {
                        id: actionMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activateAction(actionButton.modelData.action)
                    }
                }
            }
        }
    }
}
