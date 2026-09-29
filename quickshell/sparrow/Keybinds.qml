pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
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
    property bool pickerOpen: false
    property bool customEditorOpen: false
    property string captureId: ""
    property string captureKind: ""
    property string pickerTarget: ""
    property string pickerQuery: ""
    property string editingCustomId: ""
    property string deleteCustomId: ""
    property string message: ""
    property int pendingRequestId: -1
    property var overrides: ({})
    property var apps: ({})
    property var customShortcuts: []
    property var customDraft: ({})
    property string pendingSystemBrowser: ""
    signal requestSurface(string name)
    readonly property var entries: Catalog.entries
    readonly property string statePath: Niri.configPath.replace(/\/config\.kdl$/, "/sparrow/user-binds.kdl")
    readonly property var appRoles: [
        { id: "browser", label: "Browser", chord: "Super+F", fallback: "firefox" },
        { id: "terminal", label: "Terminal", chord: "Super+T", fallback: "kitty" },
        { id: "file-manager", label: "File manager", chord: "Super+E", fallback: "sparrow-files" }
    ]
    readonly property var installedApps: {
        var source = DesktopEntries.applications.values;
        var found = [];
        var hasFiles = false;
        for (var i = 0; i < source.length; i++) {
            var entry = source[i];
            if (!entry || entry.noDisplay || !entry.id || !entry.name)
                continue;
            found.push(entry);
            if (entry.id === "sparrow-files") hasFiles = true;
        }
        if (!hasFiles)
            found.push({ id: "sparrow-files", name: "Sparrow Files", icon: "system-file-manager", categories: ["FileManager"] });
        found.sort(function(a, b) { return String(a.name).localeCompare(String(b.name)); });
        return found;
    }
    readonly property var appResults: {
        var q = pickerQuery.trim().toLowerCase();
        var role = pickerTarget.indexOf("role:") === 0 ? pickerTarget.substring(5) : "";
        return installedApps.filter(function(entry) {
            if (role.length > 0) {
                var categories = entry.categories || [];
                if (!Array.isArray(categories)) categories = String(categories).split(/[;,]/);
                if (role === "browser" && categories.indexOf("WebBrowser") < 0
                        && entry.id !== "firefox" && entry.id !== "org.mozilla.firefox") return false;
                if (role === "terminal" && categories.indexOf("TerminalEmulator") < 0
                        && entry.id !== "kitty") return false;
                if (role === "file-manager" && categories.indexOf("FileManager") < 0
                        && categories.indexOf("FileTools") < 0 && entry.id !== "sparrow-files") return false;
            }
            if (!q) return true;
            return String(entry.name).toLowerCase().indexOf(q) >= 0
                || String(entry.genericName || "").toLowerCase().indexOf(q) >= 0
                || String(entry.id).toLowerCase().indexOf(q) >= 0;
        });
    }
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
        for (var j = 0; j < appRoles.length; j++)
            result[appRoles[j].id] = overrides[appRoles[j].id] || appRoles[j].chord;
        return result;
    }

    function refresh() {
        var found = ({});
        var foundApps = ({});
        var foundCustom = [];
        var lines = stateFile.text().split("\n");
        for (var i = 0; i < lines.length; i++) {
            var match = lines[i].match(/^    \/\/ override: ([a-z0-9-]+) = (.+)$/);
            if (match) {
                var aliases = { kitty: "terminal", thunar: "file-manager", firefox: "browser" };
                found[aliases[match[1]] || match[1]] = match[2];
                continue;
            }
            match = lines[i].match(/^\/\/ app: ([a-z-]+) = ([A-Za-z0-9_.@+-]+)$/);
            if (match) foundApps[match[1]] = match[2];
            match = lines[i].match(/^\/\/ custom: (.+)$/);
            if (match) {
                try { foundCustom.push(JSON.parse(match[1])); }
                catch (e) { console.warn("Sparrow Keybinds: ignoring malformed shortcut metadata"); }
            }
        }
        overrides = found;
        apps = foundApps;
        customShortcuts = foundCustom;
    }

    function currentRows() {
        var rows = appRoles.slice();
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
        var row = rows[Math.max(0, Math.min(rows.length - 1, focusIndex))];
        if (row.chord)
            beginRoleCapture(row.id);
        else
            beginCapture(row.id);
    }

    function beginCapture(id) {
        captureKind = "default";
        captureId = id;
        listening = true;
        formOpen = true;
        message = "Press a key combination · Esc cancels";
        catcher.forceActiveFocus();
    }

    function beginRoleCapture(role) {
        captureKind = "role";
        captureId = role;
        listening = true;
        message = "Press a key combination · Esc cancels";
        catcher.forceActiveFocus();
    }

    function beginCustomCapture() {
        captureKind = "custom";
        listening = true;
        message = "Press a key combination · Esc cancels";
        catcher.forceActiveFocus();
    }

    function capture(key, modifiers) {
        if (key === Qt.Key_Escape) {
            listening = false;
            if (captureKind === "default") formOpen = false;
            captureId = "";
            captureKind = "";
            return;
        }
        // The chord helper also preserves XF86 hardware-key names for capture.
        var chord = Chord.niriChord(key, modifiers);
        if (!chord)
            return;
        var conflict = conflictForChord(chord,
            captureKind === "role" || captureKind === "default" ? captureId : "",
            captureKind === "custom" ? (editingCustomId || "new") : "");
        if (conflict) { message = chord + " is already used by " + conflict; return; }
        if (displayBinds.text().indexOf(chord + " ") >= 0) {
            message = chord + " is reserved for a display shortcut";
            return;
        }
        if (captureKind === "custom") {
            customDraft = Object.assign({}, customDraft, { chord: chord });
            listening = false;
            captureKind = "";
            message = "Shortcut captured";
            return;
        }
        var rows = captureKind === "role" ? appRoles : entries;
        var entry = null;
        for (var j = 0; j < rows.length; j++)
            if (rows[j].id === captureId) { entry = rows[j]; break; }
        if (!entry || (captureKind === "default" && entry.editable === false)) return;
        var next = Object.assign({}, overrides);
        if (chord === entry.key || chord === entry.chord)
            delete next[entry.id];
        else
            next[entry.id] = chord;
        listening = false;
        captureKind = "";
        submit(next, apps, customShortcuts);
    }

    function conflictForChord(chord, excludedDefault, excludedCustom) {
        for (var i = 0; i < appRoles.length; i++)
            if (appRoles[i].id !== excludedDefault && configuredKeys[appRoles[i].id] === chord)
                return appRoles[i].label;
        for (var j = 0; j < entries.length; j++)
            if (entries[j].id !== excludedDefault && (configuredKeys[entries[j].id] || entries[j].key) === chord)
                return entries[j].label;
        for (var k = 0; k < customShortcuts.length; k++)
            if (customShortcuts[k].id !== excludedCustom && customShortcuts[k].chord === chord)
                return customShortcuts[k].label;
        return "";
    }

    function resetOne(id) {
        var next = Object.assign({}, overrides);
        delete next[id];
        submit(next, apps, customShortcuts);
    }

    function submit(nextOverrides, nextApps, nextCustom) {
        if (pendingRequestId >= 0) {
            pendingSystemBrowser = "";
            message = "A shortcut change is still being validated";
            return;
        }
        var payload = { schemaVersion: 2, overrides: nextOverrides, apps: nextApps, custom: nextCustom };
        message = "Applying and validating shortcuts…";
        pendingRequestId = Niri.writeManagedFragment("user-binds", JSON.stringify(payload));
    }

    function syncSystemBrowser(desktopId) {
        var desktopFile = desktopId.endsWith(".desktop") ? desktopId : desktopId + ".desktop";
        Quickshell.execDetached(["xdg-settings", "set", "default-web-browser", desktopFile]);
    }

    function resetAll() {
        if (!confirmResetAll) {
            confirmResetAll = true;
            return;
        }
        confirmResetAll = false;
        pendingSystemBrowser = "firefox";
        // Reset Sparrow defaults without deleting the user's independent shortcuts.
        submit(({}), ({}), customShortcuts);
    }

    function appForId(id) {
        for (var i = 0; i < installedApps.length; i++)
            if (installedApps[i].id === id) return installedApps[i];
        return { id: id, name: id, icon: "application-x-executable" };
    }

    function openPicker(target) {
        pickerTarget = target;
        pickerQuery = "";
        pickerOpen = true;
        Qt.callLater(function() { appSearch.forceActiveFocus(); });
    }

    function chooseApp(entry) {
        if (!entry || !entry.id) return;
        if (pickerTarget.indexOf("role:") === 0) {
            var role = pickerTarget.substring(5);
            var nextApps = Object.assign({}, apps);
            nextApps[role] = entry.id;
            pendingSystemBrowser = role === "browser" ? entry.id : "";
            pickerOpen = false;
            submit(overrides, nextApps, customShortcuts);
        } else if (pickerTarget === "custom") {
            customDraft = Object.assign({}, customDraft, { kind: "application", desktopId: entry.id, label: entry.name });
            pickerOpen = false;
            customEditorOpen = true;
        }
    }

    function addShortcut() {
        editingCustomId = "";
        customDraft = { id: "custom-" + Date.now().toString(36), chord: "", kind: "application", desktopId: "", label: "" };
        customEditorOpen = true;
        formOpen = true;
    }

    function editShortcut(item) {
        editingCustomId = item.id;
        customDraft = Object.assign({}, item);
        customEditorOpen = true;
        formOpen = true;
    }

    function saveCustom() {
        if (!customDraft.chord) { message = "Capture a shortcut first"; return; }
        var conflict = conflictForChord(customDraft.chord, "", editingCustomId || "new");
        if (conflict) { message = customDraft.chord + " is already used by " + conflict; return; }
        var next = customShortcuts.slice();
        var saved = Object.assign({}, customDraft);
        if (saved.kind === "application") {
            if (!saved.desktopId) { message = "Choose an installed application"; return; }
            delete saved.command;
        } else {
            if (!String(saved.command || "").trim()) { message = "Enter a command and its arguments"; return; }
            saved.label = String(saved.command).trim().split(/\s+/)[0];
            delete saved.desktopId;
        }
        var replaced = false;
        for (var i = 0; i < next.length; i++)
            if (next[i].id === saved.id) { next[i] = saved; replaced = true; break; }
        if (!replaced) next.push(saved);
        customEditorOpen = false;
        formOpen = false;
        submit(overrides, apps, next);
    }

    function removeShortcut(id) {
        var next = customShortcuts.filter(function(item) { return item.id !== id; });
        submit(overrides, apps, next);
        deleteCustomId = "";
    }

    function closeForm() {
        listening = false;
        formOpen = false;
        customEditorOpen = false;
        pickerOpen = false;
        captureId = "";
        captureKind = "";
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
                if (root.pendingSystemBrowser.length > 0) {
                    root.syncSystemBrowser(root.pendingSystemBrowser);
                    root.pendingSystemBrowser = "";
                }
            } else {
                root.message = detail || status;
                root.pendingSystemBrowser = "";
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
                anchors.right: resetAll.left
                anchors.rightMargin: 8 * root.s
                anchors.verticalCenter: parent.verticalCenter
                text: "Reset Sparrow defaults · keep custom"
                color: Theme.subtle
                font.family: Theme.font
                font.pixelSize: 11 * root.s
            }
            Rectangle {
                id: resetAll
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: root.confirmResetAll ? 90 * root.s : 62 * root.s
                height: 25 * root.s
                radius: 7 * root.s
                color: resetAllArea.containsMouse ? Qt.alpha(Theme.verm, 0.22) : Theme.frameBg
                border.width: 1
                border.color: root.confirmResetAll ? Theme.vermLit : Theme.hairSoft
                Text {
                    anchors.centerIn: parent
                    text: root.confirmResetAll ? "Confirm reset" : "Reset defaults"
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
                height: implicitHeight
                spacing: 7 * root.s

                Column {
                    width: parent.width
                    visible: root.customEditorOpen
                    spacing: 6 * root.s
                    Text {
                        text: root.editingCustomId.length ? "EDIT SHORTCUT" : "NEW SHORTCUT"
                        color: Theme.sectionText
                        font.family: Theme.font
                        font.pixelSize: 8.5 * root.s
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1 * root.s
                    }
                    Row {
                        width: parent.width
                        height: 30 * root.s
                        spacing: 7 * root.s
                        Rectangle {
                            width: 132 * root.s
                            height: parent.height
                            radius: 7 * root.s
                            color: root.customDraft.chord ? Theme.frameBg : Qt.alpha(Theme.vermLit, 0.12)
                            border.width: 1
                            border.color: Theme.hairSoft
                            Text { anchors.centerIn: parent; text: root.listening && root.captureKind === "custom" ? "Press shortcut…" : (root.customDraft.chord || "Capture shortcut"); color: Theme.cream; font.family: Theme.font; font.pixelSize: 9 * root.s }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.beginCustomCapture() }
                        }
                        Rectangle {
                            width: 78 * root.s
                            height: parent.height
                            radius: 7 * root.s
                            color: root.customDraft.kind === "application" ? Qt.alpha(Theme.vermLit, 0.18) : "transparent"
                            border.width: 1
                            border.color: Theme.hairSoft
                            Text { anchors.centerIn: parent; text: "Application"; color: Theme.cream; font.family: Theme.font; font.pixelSize: 8 * root.s }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.customDraft = Object.assign({}, root.customDraft, { kind: "application" }) }
                        }
                        Rectangle {
                            width: 64 * root.s
                            height: parent.height
                            radius: 7 * root.s
                            color: root.customDraft.kind === "command" ? Qt.alpha(Theme.vermLit, 0.18) : "transparent"
                            border.width: 1
                            border.color: Theme.hairSoft
                            Text { anchors.centerIn: parent; text: "Command"; color: Theme.cream; font.family: Theme.font; font.pixelSize: 8 * root.s }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.customDraft = Object.assign({}, root.customDraft, { kind: "command" }) }
                        }
                    }
                    Row {
                        width: parent.width
                        height: 31 * root.s
                        visible: root.customDraft.kind === "application"
                        spacing: 7 * root.s
                        Text {
                            width: 220 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.customDraft.label || "Choose an installed application"
                            color: root.customDraft.label ? Theme.secondaryText : Theme.mutedText
                            font.family: Theme.font
                            font.pixelSize: 9 * root.s
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            width: 90 * root.s
                            height: 25 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            radius: 7 * root.s
                            color: pickerButtonArea.containsMouse ? Qt.alpha(Theme.vermLit, 0.14) : Theme.frameBg
                            border.width: 1
                            border.color: Theme.hairSoft
                            Text { anchors.centerIn: parent; text: "Choose app"; color: Theme.cream; font.family: Theme.font; font.pixelSize: 8.5 * root.s }
                            MouseArea { id: pickerButtonArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.openPicker("custom") }
                        }
                    }
                    Rectangle {
                        width: parent.width
                        height: 31 * root.s
                        visible: root.customDraft.kind === "command"
                        radius: 7 * root.s
                        color: Theme.frameBg
                        border.width: 1
                        border.color: Theme.hairSoft
                        TextInput {
                            anchors.fill: parent
                            anchors.leftMargin: 9 * root.s
                            anchors.rightMargin: 9 * root.s
                            verticalAlignment: TextInput.AlignVCenter
                            text: root.customDraft.command || ""
                            color: Theme.cream
                            selectionColor: Theme.verm
                            selectedTextColor: Theme.cream
                            font.family: Theme.font
                            font.pixelSize: 9 * root.s
                            clip: true
                            onTextChanged: root.customDraft = Object.assign({}, root.customDraft, { command: text })
                            Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Command with arguments · no shell expansion"; color: Theme.mutedText; font: parent.font; visible: parent.text.length === 0 }
                        }
                    }
                    Row {
                        width: parent.width
                        height: 28 * root.s
                        spacing: 7 * root.s
                        Rectangle {
                            width: 70 * root.s
                            height: parent.height
                            radius: 7 * root.s
                            color: saveCustomArea.containsMouse ? Qt.alpha(Theme.vermLit, 0.2) : Theme.frameBg
                            border.width: 1
                            border.color: Theme.hairSoft
                            Text { anchors.centerIn: parent; text: "Save"; color: Theme.cream; font.family: Theme.font; font.pixelSize: 9 * root.s; font.weight: Font.DemiBold }
                            MouseArea { id: saveCustomArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.saveCustom() }
                        }
                        Rectangle {
                            width: 70 * root.s
                            height: parent.height
                            radius: 7 * root.s
                            color: cancelCustomArea.containsMouse ? Theme.frameBg : "transparent"
                            Text { anchors.centerIn: parent; text: "Cancel"; color: Theme.secondaryText; font.family: Theme.font; font.pixelSize: 9 * root.s }
                            MouseArea { id: cancelCustomArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { root.customEditorOpen = false; root.formOpen = false; root.listening = false; root.message = "" } }
                        }
                    }
                    Rectangle { width: parent.width; height: 1; color: Theme.hairSoft }
                }

                Text {
                    width: parent.width
                    height: 18 * root.s
                    verticalAlignment: Text.AlignVCenter
                    text: "APPLICATIONS"
                    color: Theme.sectionText
                    font.family: Theme.font
                    font.pixelSize: 8.5 * root.s
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1 * root.s
                }
                Text {
                    width: parent.width
                    text: "Browser changes also update the desktop default · other roles stay Sparrow-only"
                    color: Theme.mutedText
                    font.family: Theme.font
                    font.pixelSize: 8 * root.s
                    wrapMode: Text.WordWrap
                }
                Repeater {
                    model: root.appRoles
                    delegate: Item {
                        id: appRoleRow
                        required property var modelData
                        width: groups.width
                        height: 42 * root.s
                        readonly property string selectedId: root.apps[modelData.id] || modelData.fallback
                        readonly property var selectedApp: root.appForId(selectedId)
                        Rectangle {
                            anchors.fill: parent
                            radius: 8 * root.s
                            color: roleHover.containsMouse ? Qt.alpha(Theme.cream, 0.035) : "transparent"
                        }
                        Image {
                            id: roleIcon
                            anchors.left: parent.left
                            anchors.leftMargin: 8 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: 21 * root.s
                            height: 21 * root.s
                            source: appRoleRow.selectedApp.icon ? Quickshell.iconPath(appRoleRow.selectedApp.icon, true) : ""
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                        Column {
                            anchors.left: roleIcon.right
                            anchors.leftMargin: 9 * root.s
                            anchors.right: chordChip.left
                            anchors.rightMargin: 9 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 1 * root.s
                            Text {
                                width: parent.width
                                text: appRoleRow.modelData.label
                                color: Theme.cream
                                font.family: Theme.font
                                font.pixelSize: 10.5 * root.s
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                text: appRoleRow.selectedApp.name
                                color: Theme.secondaryText
                                font.family: Theme.font
                                font.pixelSize: 9 * root.s
                                elide: Text.ElideRight
                            }
                        }
                        Rectangle {
                            id: chordChip
                            anchors.right: changeApp.left
                            anchors.rightMargin: 6 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(54 * root.s, roleChord.implicitWidth + 14 * root.s)
                            height: 23 * root.s
                            radius: 6 * root.s
                            color: Theme.frameBg
                            border.width: 1
                            border.color: Theme.hairSoft
                            Text {
                                id: roleChord
                                anchors.centerIn: parent
                                text: root.listening && root.captureKind === "role" && root.captureId === appRoleRow.modelData.id
                                    ? "Press key…" : root.configuredKeys[appRoleRow.modelData.id]
                                color: root.listening && root.captureId === appRoleRow.modelData.id ? Theme.flameGlow : Theme.secondaryText
                                font.family: Theme.font
                                font.pixelSize: 8.5 * root.s
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.beginRoleCapture(appRoleRow.modelData.id)
                            }
                        }
                        Rectangle {
                            id: changeApp
                            anchors.right: parent.right
                            anchors.rightMargin: 4 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: 48 * root.s
                            height: 23 * root.s
                            radius: 6 * root.s
                            color: changeArea.containsMouse ? Qt.alpha(Theme.vermLit, 0.14) : "transparent"
                            border.width: 1
                            border.color: Theme.hairSoft
                            Text {
                                anchors.centerIn: parent
                                text: "Change"
                                color: Theme.cream
                                font.family: Theme.font
                                font.pixelSize: 8.5 * root.s
                            }
                            MouseArea {
                                id: changeArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.openPicker("role:" + appRoleRow.modelData.id)
                            }
                        }
                        MouseArea {
                            id: roleHover
                            anchors.fill: parent
                            anchors.rightMargin: 55 * root.s
                            hoverEnabled: true
                            z: -1
                        }
                    }
                }

                Item { width: 1; height: 1 * root.s }
                Text {
                    width: parent.width
                    height: 18 * root.s
                    verticalAlignment: Text.AlignVCenter
                    text: "CUSTOM"
                    color: Theme.sectionText
                    font.family: Theme.font
                    font.pixelSize: 8.5 * root.s
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1 * root.s
                }
                Repeater {
                    model: root.customShortcuts
                    delegate: Item {
                        id: customRow
                        required property var modelData
                        width: groups.width
                        height: 34 * root.s
                        Rectangle {
                            anchors.fill: parent
                            radius: 7 * root.s
                            color: customHover.containsMouse ? Qt.alpha(Theme.cream, 0.035) : "transparent"
                        }
                        Image {
                            id: customIcon
                            anchors.left: parent.left
                            anchors.leftMargin: 7 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: 17 * root.s
                            height: 17 * root.s
                            visible: customRow.modelData.kind === "application"
                            source: visible ? Quickshell.iconPath(root.appForId(customRow.modelData.desktopId).icon, true) : ""
                            fillMode: Image.PreserveAspectFit
                        }
                        Text {
                            anchors.left: customRow.modelData.kind === "application" ? customIcon.right : parent.left
                            anchors.leftMargin: customRow.modelData.kind === "application" ? 7 * root.s : 8 * root.s
                            anchors.right: customKey.left
                            anchors.rightMargin: 8 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            text: customRow.modelData.label
                            color: Theme.cream
                            font.family: Theme.font
                            font.pixelSize: 10 * root.s
                            elide: Text.ElideRight
                        }
                        Text {
                            id: customKey
                            anchors.right: editCustom.left
                            anchors.rightMargin: 6 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            text: customRow.modelData.chord
                            color: Theme.secondaryText
                            font.family: Theme.font
                            font.pixelSize: 8.5 * root.s
                        }
                        Rectangle {
                            id: editCustom
                            anchors.right: deleteCustom.left
                            anchors.rightMargin: 3 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: 34 * root.s
                            height: 22 * root.s
                            radius: 6 * root.s
                            color: editArea.containsMouse ? Theme.frameBg : "transparent"
                            Text { anchors.centerIn: parent; text: "Edit"; color: Theme.cream; font.family: Theme.font; font.pixelSize: 8 * root.s }
                            MouseArea { id: editArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.editShortcut(customRow.modelData) }
                        }
                        Rectangle {
                            id: deleteCustom
                            anchors.right: parent.right
                            anchors.rightMargin: 3 * root.s
                            anchors.verticalCenter: parent.verticalCenter
                            width: 28 * root.s
                            height: 22 * root.s
                            radius: 6 * root.s
                            color: deleteArea.containsMouse || root.deleteCustomId === customRow.modelData.id ? Qt.alpha(Theme.verm, 0.2) : "transparent"
                            Text { anchors.centerIn: parent; text: root.deleteCustomId === customRow.modelData.id ? "Sure?" : "×"; color: Theme.vermLit; font.family: Theme.font; font.pixelSize: 9 * root.s }
                            MouseArea {
                                id: deleteArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (root.deleteCustomId === customRow.modelData.id) root.removeShortcut(customRow.modelData.id);
                                    else root.deleteCustomId = customRow.modelData.id;
                                }
                            }
                        }
                        MouseArea { id: customHover; anchors.fill: parent; anchors.rightMargin: 70 * root.s; hoverEnabled: true; z: -1 }
                    }
                }
                Rectangle {
                    width: parent.width
                    height: 29 * root.s
                    radius: 8 * root.s
                    color: addArea.containsMouse ? Qt.alpha(Theme.vermLit, 0.13) : Theme.frameBg
                    border.width: 1
                    border.color: Theme.hairSoft
                    Text {
                        anchors.centerIn: parent
                        text: "+ Add shortcut"
                        color: Theme.cream
                        font.family: Theme.font
                        font.pixelSize: 9.5 * root.s
                        font.weight: Font.DemiBold
                    }
                    MouseArea { id: addArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.addShortcut() }
                }

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

    Rectangle {
        id: pickerOverlay
        anchors.fill: parent
        visible: root.pickerOpen
        z: 20
        radius: 13 * root.s
        color: Qt.alpha(Theme.tileBg, 0.96)
        border.width: 1
        border.color: Theme.hairSoft

        Column {
            anchors.fill: parent
            anchors.margins: 12 * root.s
            spacing: 8 * root.s
            Text {
                width: parent.width
                text: root.pickerTarget.indexOf("role:") === 0
                    ? "CHOOSE " + root.pickerTarget.substring(5).toUpperCase()
                    : "CHOOSE APPLICATION"
                color: Theme.sectionText
                font.family: Theme.font
                font.pixelSize: 9 * root.s
                font.weight: Font.DemiBold
                font.letterSpacing: 1 * root.s
            }
            Rectangle {
                width: parent.width
                height: 31 * root.s
                radius: 8 * root.s
                color: Theme.frameBg
                border.width: 1
                border.color: Theme.hairSoft
                TextInput {
                    id: appSearch
                    anchors.fill: parent
                    anchors.leftMargin: 10 * root.s
                    anchors.rightMargin: 10 * root.s
                    verticalAlignment: TextInput.AlignVCenter
                    text: root.pickerQuery
                    color: Theme.cream
                    selectionColor: Theme.verm
                    selectedTextColor: Theme.cream
                    font.family: Theme.font
                    font.pixelSize: 9.5 * root.s
                    onTextChanged: root.pickerQuery = text
                    Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; text: "Search installed applications"; color: Theme.mutedText; font: parent.font; visible: parent.text.length === 0 }
                }
            }
            ListView {
                width: parent.width
                height: Math.max(60 * root.s, parent.height - 78 * root.s)
                clip: true
                model: root.appResults
                spacing: 2 * root.s
                boundsBehavior: Flickable.StopAtBounds
                delegate: Item {
                    id: appChoice
                    required property var modelData
                    width: ListView.view.width
                    height: 37 * root.s
                    Rectangle {
                        anchors.fill: parent
                        radius: 7 * root.s
                        color: appChoiceArea.containsMouse ? Qt.alpha(Theme.vermLit, 0.15) : "transparent"
                    }
                    Image {
                        id: choiceIcon
                        anchors.left: parent.left
                        anchors.leftMargin: 8 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        width: 22 * root.s
                        height: 22 * root.s
                        source: appChoice.modelData.icon ? Quickshell.iconPath(appChoice.modelData.icon, true) : ""
                        fillMode: Image.PreserveAspectFit
                    }
                    Text {
                        anchors.left: choiceIcon.right
                        anchors.leftMargin: 10 * root.s
                        anchors.right: parent.right
                        anchors.rightMargin: 8 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        text: appChoice.modelData.name
                        color: Theme.cream
                        font.family: Theme.font
                        font.pixelSize: 10 * root.s
                        elide: Text.ElideRight
                    }
                    MouseArea {
                        id: appChoiceArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.chooseApp(appChoice.modelData)
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: root.appResults.length === 0
                    text: "No installed applications found"
                    color: Theme.mutedText
                    font.family: Theme.font
                    font.pixelSize: 9 * root.s
                }
            }
            Rectangle {
                width: 64 * root.s
                height: 25 * root.s
                radius: 7 * root.s
                color: closePickerArea.containsMouse ? Theme.frameBg : "transparent"
                Text { anchors.centerIn: parent; text: "Cancel"; color: Theme.secondaryText; font.family: Theme.font; font.pixelSize: 9 * root.s }
                MouseArea { id: closePickerArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.pickerOpen = false }
            }
        }
    }
}
