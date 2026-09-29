pragma ComponentBehavior: Bound

import QtQuick
import Quickshell.Io
import "lib/keybind-catalog.js" as Catalog
import "lib/keychord.js" as Chord
import "Singletons"

PillSurface {
    id: root

    mTop: 15
    mLeft: 19
    mRight: 19
    mBottom: 14
    implicitHeight: content.implicitHeight

    property int focusIndex: 0
    property bool listening: false
    property bool formOpen: false
    property bool confirmResetAll: false
    property string captureId: ""
    property string message: ""
    property int pendingRequestId: -1
    property var overrides: ({})
    signal requestSurface(string name)
    readonly property var entries: Catalog.entries
    readonly property string statePath: Niri.configPath.replace(/\/config\.kdl$/, "/sparrow/user-binds.kdl")
    readonly property var displayShortcuts: {
        var source = displayBinds.text();
        var found = [];
        var expression = /^\s*(Super(?:\+Shift)?\+F[0-9]+)\s+hotkey-overlay-title="([^"]+)"/gm;
        var match;
        while ((match = expression.exec(source)) !== null)
            found.push({ chord: match[1], label: match[2] });
        return found;
    }
    readonly property var configuredKeys: {
        var result = ({});
        for (var i = 0; i < entries.length; i++)
            result[entries[i].id] = overrides[entries[i].id] || entries[i].key;
        return result;
    }

    function refresh() {
        var found = ({});
        var lines = stateFile.text().split("\n");
        for (var i = 0; i < lines.length; i++) {
            var match = lines[i].match(/^    \/\/ override: ([a-z0-9-]+) = (.+)$/);
            if (match)
                found[match[1]] = match[2];
        }
        overrides = found;
    }

    function currentRows() {
        var rows = [];
        for (var i = 0; i < entries.length; i++)
            if (entries[i].editable !== false)
                rows.push(entries[i]);
        return rows;
    }

    function move(direction) {
        if (listening || formOpen)
            return;
        var rows = currentRows();
        if (!rows.length)
            return;
        focusIndex = Math.max(0, Math.min(rows.length - 1, focusIndex + direction));
    }

    function activate() {
        var rows = currentRows();
        if (listening || !rows.length)
            return;
        beginCapture(rows[Math.max(0, Math.min(rows.length - 1, focusIndex))].id);
    }

    function beginCapture(id) {
        captureId = id;
        listening = true;
        formOpen = true;
        message = "Press a key combination · Esc cancels";
        catcher.forceActiveFocus();
    }

    function capture(key, modifiers) {
        if (key === Qt.Key_Escape) {
            listening = false;
            formOpen = false;
            captureId = "";
            return;
        }
        // The chord helper also preserves XF86 hardware-key names for capture.
        var chord = Chord.niriChord(key, modifiers);
        if (!chord)
            return;
        var entry = null;
        for (var i = 0; i < entries.length; i++)
            if (entries[i].id === captureId) { entry = entries[i]; break; }
        if (!entry)
            return;
        if (entry.editable === false) {
            message = "This hardware shortcut is fixed";
            return;
        }
        for (var j = 0; j < entries.length; j++) {
            var other = entries[j];
            if (other.id !== entry.id && (configuredKeys[other.id] || other.key) === chord) {
                message = chord + " is already used by " + other.label;
                return;
            }
        }
        if (displayBinds.text().indexOf(chord + " ") >= 0) {
            message = chord + " is reserved for a display shortcut";
            return;
        }
        var next = Object.assign({}, overrides);
        if (chord === entry.key)
            delete next[entry.id];
        else
            next[entry.id] = chord;
        submit(next);
    }

    function resetOne(id) {
        var next = Object.assign({}, overrides);
        delete next[id];
        submit(next);
    }

    function submit(next) {
        overrides = next;
        message = "Applying and validating shortcuts…";
        pendingRequestId = Niri.writeManagedFragment("user-binds", JSON.stringify(next));
    }

    function resetAll() {
        if (!confirmResetAll) {
            confirmResetAll = true;
            return;
        }
        confirmResetAll = false;
        submit(({}));
    }

    function closeForm() {
        listening = false;
        formOpen = false;
        captureId = "";
        confirmResetAll = false;
        catcher.focus = false;
    }

    onActiveChanged: {
        if (active) {
            stateFile.reload();
            displayBinds.reload();
            refresh();
            focusIndex = 0;
            closeForm();
            message = "";
        } else {
            closeForm();
        }
    }

    Connections {
        target: Niri
        function onManagedFragmentWriteFinished(requestId, status, detail) {
            if (requestId !== root.pendingRequestId)
                return;
            root.pendingRequestId = -1;
            if (status === "success") {
                root.message = "Shortcuts saved";
                root.closeForm();
                stateFile.reload();
                root.refresh();
            } else {
                root.message = detail || status;
                stateFile.reload();
                root.refresh();
            }
        }
    }

    FileView {
        id: stateFile
        path: root.statePath
        blockLoading: true
        watchChanges: true
        printErrors: false
        onLoaded: root.refresh()
        onFileChanged: reload()
    }
    FileView {
        id: displayBinds
        path: Niri.configPath.replace(/\/config\.kdl$/, "/sparrow/display-binds.kdl")
        blockLoading: true
        watchChanges: true
        printErrors: false
    }

    Item {
        id: catcher
        width: 1
        height: 1
        focus: root.listening
        Keys.onPressed: (event) => {
            if (!root.listening)
                return;
            event.accepted = true;
            root.capture(event.key, event.modifiers);
        }
    }

    Column {
        id: content
        width: parent.width
        spacing: 0

        Item {
            width: parent.width
            height: 22 * root.s
            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 0
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "KEYBINDS"
                    color: Theme.subtle
                    font.family: Theme.font
                    font.pixelSize: 10 * root.s
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.6 * root.s
                }
            }
            GlyphIcon {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 16 * root.s
                height: 16 * root.s
                name: "chevron-left"
                color: Theme.iconDim
                stroke: 2.2
            }
        }

        Item { width: 1; height: 8 * root.s }

        Item {
            width: parent.width
            height: 30 * root.s
            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "Reset shortcuts"
                color: Theme.subtle
                font.family: Theme.font
                font.pixelSize: 11 * root.s
            }
            Rectangle {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: root.confirmResetAll ? 90 * root.s : 56 * root.s
                height: 25 * root.s
                radius: 7 * root.s
                color: resetAllArea.containsMouse ? Qt.alpha(Theme.verm, 0.22) : Theme.frameBg
                border.width: 1
                border.color: root.confirmResetAll ? Theme.vermLit : Theme.hairSoft
                Text {
                    anchors.centerIn: parent
                    text: root.confirmResetAll ? "Confirm reset" : "Reset all"
                    color: root.confirmResetAll ? Theme.vermLit : Theme.cream
                    font.family: Theme.font
                    font.pixelSize: 9.5 * root.s
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    id: resetAllArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.resetAll()
                }
            }
        }

        Flickable {
            width: parent.width
            height: Math.min(360 * root.s, groups.height)
            clip: true
            contentHeight: groups.height
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: groups
                width: parent.width
                height: (function() {
                    var total = Math.max(0, Catalog.groups.length - 1) * 7;
                    for (var i = 0; i < Catalog.groups.length; i++)
                        total += 21 + Catalog.groups[i].items.length * 35;
                    return total * root.s;
                })()
                spacing: 7 * root.s
                Repeater {
                    model: Catalog.groups
                    delegate: Column {
                        id: categoryDelegate
                        required property var modelData
                        width: groups.width
                        height: (21 + modelData.items.length * 35) * root.s
                        spacing: 1 * root.s
                        Text {
                            width: parent.width
                            height: 20 * root.s
                            verticalAlignment: Text.AlignVCenter
                            text: categoryDelegate.modelData.name.toUpperCase()
                            color: Theme.sectionText
                            font.family: Theme.font
                            font.pixelSize: 8.5 * root.s
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1 * root.s
                        }
                        Repeater {
                            model: categoryDelegate.modelData.items
                            delegate: Item {
                                id: bindDelegate
                                required property var modelData
                                width: parent.width
                                height: 34 * root.s
                                readonly property bool editing: root.captureId === modelData.id && root.listening
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 7 * root.s
                                    color: bindDelegate.editing ? Qt.alpha(Theme.vermLit, 0.1)
                                        : rowArea.containsMouse ? Qt.alpha(Theme.cream, 0.035) : "transparent"
                                    border.width: bindDelegate.editing ? 1 : 0
                                    border.color: Qt.alpha(Theme.vermLit, 0.5)
                                }
                                Text {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8 * root.s
                                    anchors.right: shortcut.left
                                    anchors.rightMargin: 8 * root.s
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: bindDelegate.editing ? "Press shortcut…" : bindDelegate.modelData.label
                                    color: bindDelegate.editing ? Theme.flameGlow : Theme.cream
                                    font.family: Theme.font
                                    font.pixelSize: 10.5 * root.s
                                    elide: Text.ElideRight
                                }
                                Text {
                                    id: shortcut
                                    anchors.right: reset.left
                                    anchors.rightMargin: 7 * root.s
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: bindDelegate.editing ? "Esc cancels" : (root.configuredKeys[bindDelegate.modelData.id] || bindDelegate.modelData.key)
                                    color: bindDelegate.editing ? Theme.flameGlow : Theme.subtle
                                    font.family: Theme.font
                                    font.pixelSize: 9.5 * root.s
                                }
                                Rectangle {
                                    id: reset
                                    anchors.right: parent.right
                                    anchors.rightMargin: 4 * root.s
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 22 * root.s
                                    height: 22 * root.s
                                    radius: 6 * root.s
                                    visible: root.overrides[bindDelegate.modelData.id] !== undefined
                                    color: resetArea.containsMouse ? Qt.alpha(Theme.verm, 0.2) : "transparent"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "↺"
                                        color: Theme.iconDim
                                        font.pixelSize: 13 * root.s
                                    }
                                    MouseArea {
                                        id: resetArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.resetOne(bindDelegate.modelData.id)
                                    }
                                }
                                MouseArea {
                                    id: rowArea
                                    anchors.fill: parent
                                    anchors.rightMargin: reset.visible ? 30 * root.s : 0
                                    hoverEnabled: true
                                    cursorShape: bindDelegate.modelData.editable === false ? Qt.ArrowCursor : Qt.PointingHandCursor
                                    onClicked: if (bindDelegate.modelData.editable !== false) root.beginCapture(bindDelegate.modelData.id)
                                }
                            }
                        }
                    }
                }
            }
        }

        Item { width: 1; height: 5 * root.s }
        Rectangle { width: parent.width; height: 1; color: Theme.hairSoft }
        Item { width: 1; height: 6 * root.s }
        Column {
            width: parent.width
            spacing: 3 * root.s
            Text {
                text: "DISPLAY · MANAGED IN DISPLAY SETTINGS"
                color: Theme.sectionText
                font.family: Theme.font
                font.pixelSize: 8 * root.s
                font.weight: Font.DemiBold
                font.letterSpacing: 0.7 * root.s
            }
            Repeater {
                model: root.displayShortcuts
                delegate: Row {
                    id: displayDelegate
                    required property var modelData
                    width: parent.width
                    spacing: 8 * root.s
                    Text {
                        text: displayDelegate.modelData.chord
                        color: Theme.subtle
                        font.family: Theme.font
                        font.pixelSize: 9 * root.s
                    }
                    Text {
                        text: displayDelegate.modelData.label
                        color: Theme.secondaryText
                        font.family: Theme.font
                        font.pixelSize: 9 * root.s
                    }
                }
            }
            Text {
                visible: root.displayShortcuts.length === 0
                text: "No numbered display shortcuts assigned"
                color: Theme.mutedText
                font.family: Theme.font
                font.pixelSize: 9 * root.s
            }
        }
        Text {
            width: parent.width
            visible: root.message.length > 0
            topPadding: 4 * root.s
            text: root.message
            color: root.message.indexOf("saved") >= 0 ? Theme.subtle : Theme.vermLit
            font.family: Theme.font
            font.pixelSize: 9 * root.s
            wrapMode: Text.WordWrap
        }
    }
}
