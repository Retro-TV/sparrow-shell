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

        Item { width: 1; height: 9 * root.s }

        Text {
            text: "Welcome to Sparrow"
            color: Theme.primaryText
            font.family: Theme.font
            font.pixelSize: 17 * root.s
            font.weight: Font.DemiBold
        }

        Item { width: 1; height: 3 * root.s }

        Text {
            width: parent.width
            text: "Your desktop, gathered in one small Pill."
            color: Theme.secondaryText
            font.family: Theme.font
            font.pixelSize: 10.5 * root.s
        }

        Item { width: 1; height: 15 * root.s }

        Text {
            text: "START HERE"
            color: Theme.sectionText
            font.family: Theme.font
            font.pixelSize: 8.5 * root.s
            font.weight: Font.DemiBold
            font.letterSpacing: 1.1 * root.s
        }

        Item { width: 1; height: 6 * root.s }

        Grid {
            id: actions
            width: parent.width
            columns: 2
            rowSpacing: 6 * root.s
            columnSpacing: 6 * root.s

            Repeater {
                model: [
                    { id: "launcher", title: "Launcher", detail: "Find and open apps", icon: "app-window", action: "launcher" },
                    { id: "wallpaper-picker", title: "Wallpaper", detail: "Choose your scene", icon: "monitor", action: "wallpaper" },
                    { id: "keybinds", title: "Keybinds", detail: "See or edit shortcuts", icon: "keyboard", action: "keybinds" },
                    { id: "recorder", title: "Recorder", detail: "Capture your screen", icon: "video", action: "recorder" }
                ]

                delegate: Rectangle {
                    id: actionCard
                    required property var modelData
                    width: (actions.width - actions.columnSpacing) / 2
                    height: 62 * root.s
                    readonly property string shortcutLabel: root.shortcut(modelData.id)
                    radius: 10 * root.s
                    color: cardMouse.containsMouse ? Theme.frameBg : Theme.tileBg
                    border.width: 1
                    border.color: cardMouse.containsMouse ? Qt.alpha(Theme.vermLit, 0.4) : Theme.hairSoft
                    Behavior on color { ColorAnimation { duration: Motion.fast } }
                    Behavior on border.color { ColorAnimation { duration: Motion.fast } }

                    GlyphIcon {
                        anchors.left: parent.left
                        anchors.leftMargin: 10 * root.s
                        anchors.top: parent.top
                        anchors.topMargin: 11 * root.s
                        width: 16 * root.s
                        height: 16 * root.s
                        name: actionCard.modelData.icon
                        color: Theme.accentText
                        stroke: 1.8
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 10 * root.s
                        anchors.right: keycap.left
                        anchors.rightMargin: 5 * root.s
                        anchors.top: parent.top
                        anchors.topMargin: 31 * root.s
                        text: actionCard.modelData.title
                        color: Theme.primaryText
                        font.family: Theme.font
                        font.pixelSize: 10 * root.s
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 10 * root.s
                        anchors.right: keycap.left
                        anchors.rightMargin: 5 * root.s
                        anchors.top: parent.top
                        anchors.topMargin: 45 * root.s
                        text: actionCard.modelData.detail
                        color: Theme.secondaryText
                        font.family: Theme.font
                        font.pixelSize: 8 * root.s
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        id: keycap
                        anchors.right: parent.right
                        anchors.rightMargin: 8 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        visible: actionCard.shortcutLabel !== "—"
                        width: visible ? keyText.implicitWidth + 10 * root.s : 0
                        height: 19 * root.s
                        radius: 5 * root.s
                        color: Theme.frameBg
                        border.width: 1
                        border.color: Theme.hairSoft

                        Text {
                            id: keyText
                            anchors.centerIn: parent
                            text: actionCard.shortcutLabel
                            color: Theme.secondaryText
                            font.family: Theme.font
                            font.pixelSize: 8 * root.s
                            font.weight: Font.DemiBold
                        }
                    }

                    MouseArea {
                        id: cardMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activateAction(actionCard.modelData.action)
                    }
                }
            }
        }

        Item { width: 1; height: 12 * root.s }
        Rectangle { width: parent.width; height: 1; color: Theme.hairSoft }
        Item { width: 1; height: 9 * root.s }

        Item {
            width: parent.width
            height: 18 * root.s

            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8 * root.s

                GlyphIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 15 * root.s
                    height: 15 * root.s
                    name: "lock"
                    color: Theme.iconDim
                    stroke: 1.8
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Lock your session"
                    color: Theme.secondaryText
                    font.family: Theme.font
                    font.pixelSize: 9.5 * root.s
                }
            }

            Text {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: root.shortcut("lock")
                color: Theme.primaryText
                font.family: Theme.font
                font.pixelSize: 9 * root.s
                font.weight: Font.DemiBold
            }
        }

        Item { width: 1; height: 9 * root.s }

        Text {
            width: parent.width
            text: "Open the gear for settings. Wallpaper colors adapt automatically."
            color: Theme.mutedText
            font.family: Theme.font
            font.pixelSize: 9 * root.s
            wrapMode: Text.WordWrap
        }
    }
}
