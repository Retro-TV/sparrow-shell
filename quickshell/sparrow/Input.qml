pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import "Singletons"

/** Sparrow's compact, Niri-native input preferences. */
SettingsSurface {
    id: root

    backSurface: "settings"
    implicitHeight: content.implicitHeight

    readonly property string inputPath: Niri.configPath.substring(0, Niri.configPath.lastIndexOf("/")) + "/sparrow/user-input.kdl"
    readonly property string infoHelper: Quickshell.shellPath("scripts/input-system-info.py")

    property string note: ""
    property string layoutSearch: ""
    property string activeLayoutName: ""
    property bool layoutOpen: false
    property bool touchMapOpen: false
    property bool tabletMapOpen: false
    property bool deviceQueryDone: false
    property var devices: ({ keyboard: true, touchpad: false, mouse: false, touchscreen: false, tablet: false })
    property var layouts: []
    property var prefs: ({
        layout: "", numlock: false, repeatRate: 25, repeatDelay: 600,
        touchpadTap: false, touchpadNatural: false, touchpadDwt: false,
        touchpadSpeed: 0, touchpadProfile: "adaptive",
        mouseNatural: false, mouseLeftHanded: false, mouseSpeed: 0, mouseProfile: "adaptive",
        touchOutput: "", tabletOutput: "", focusFollowsMouse: false
    })

    readonly property var matchingLayouts: {
        var needle = layoutSearch.trim().toLowerCase();
        var result = [{ code: "", label: "System default" }];
        for (var i = 0; i < layouts.length; i++) {
            var item = layouts[i];
            if (!needle || (item.label + " " + item.code).toLowerCase().indexOf(needle) >= 0)
                result.push(item);
        }
        return result;
    }

    function sectionRows() {
        var list = [
            { item: layoutRow, kind: "toggle", get: function() { return root.layoutOpen; }, set: function(v) { root.layoutOpen = v; } },
            { item: rateRow, kind: "scrub", bump: function(d) { rateScrub.bump(d); } },
            { item: delayRow, kind: "scrub", bump: function(d) { delayScrub.bump(d); } },
            { item: numlockRow, kind: "toggle", get: function() { return root.prefs.numlock; }, set: function(v) { root.change("numlock", v); } }
        ];
        if (root.devices.touchpad) {
            list = list.concat([
                { item: tapRow, kind: "toggle", get: function() { return root.prefs.touchpadTap; }, set: function(v) { root.change("touchpadTap", v); } },
                { item: naturalTouchRow, kind: "toggle", get: function() { return root.prefs.touchpadNatural; }, set: function(v) { root.change("touchpadNatural", v); } },
                { item: dwtRow, kind: "toggle", get: function() { return root.prefs.touchpadDwt; }, set: function(v) { root.change("touchpadDwt", v); } },
                { item: touchSpeedRow, kind: "scrub", bump: function(d) { touchSpeedScrub.bump(d); } },
                { item: touchAccelRow, kind: "seg", vals: ["adaptive", "flat"], get: function() { return root.prefs.touchpadProfile; }, set: function(v) { root.change("touchpadProfile", v); } }
            ]);
        }
        if (root.devices.mouse) {
            list = list.concat([
                { item: mouseSpeedRow, kind: "scrub", bump: function(d) { mouseSpeedScrub.bump(d); } },
                { item: mouseAccelRow, kind: "seg", vals: ["adaptive", "flat"], get: function() { return root.prefs.mouseProfile; }, set: function(v) { root.change("mouseProfile", v); } },
                { item: naturalMouseRow, kind: "toggle", get: function() { return root.prefs.mouseNatural; }, set: function(v) { root.change("mouseNatural", v); } },
                { item: leftHandedRow, kind: "toggle", get: function() { return root.prefs.mouseLeftHanded; }, set: function(v) { root.change("mouseLeftHanded", v); } }
            ]);
        }
        if (root.devices.touchscreen)
            list.push({ item: touchMapRow, kind: "toggle", get: function() { return root.touchMapOpen; }, set: function(v) { root.touchMapOpen = v; } });
        if (root.devices.tablet)
            list.push({ item: tabletMapRow, kind: "toggle", get: function() { return root.tabletMapOpen; }, set: function(v) { root.tabletMapOpen = v; } });
        list.push({ item: focusRow, kind: "toggle", get: function() { return root.prefs.focusFollowsMouse; }, set: function(v) { root.change("focusFollowsMouse", v); } });
        return list;
    }
    rows: sectionRows()

    property string blockText: ""

    function readClass(text, className) {
        var rx = new RegExp("^    " + className + " \\{([\\s\\S]*?)^    \\}", "m");
        var match = rx.exec(text);
        return match ? match[1] : "";
    }

    function parseFragment(text) {
        var next = Object.assign({}, prefs);
        var keyboard = readClass(text, "keyboard");
        var xkb = /xkb\s*\{\s*layout\s+"([A-Za-z0-9_,+-]+)"/m.exec(keyboard);
        next.layout = xkb ? xkb[1] : "";
        next.numlock = /(?:^|\n)\s*numlock\s*(?:\n|$)/.test(keyboard);
        var number = function(block, key, fallback) {
            var match = new RegExp("(?:^|\\n)\\s*" + key + "\\s+(-?[0-9]+(?:\\.[0-9]+)?)", "m").exec(block);
            return match ? Number(match[1]) : fallback;
        };
        next.repeatRate = number(keyboard, "repeat-rate", 25);
        next.repeatDelay = number(keyboard, "repeat-delay", 600);
        var pad = readClass(text, "touchpad");
        next.touchpadTap = /(?:^|\n)\s*tap\s*(?:\n|$)/.test(pad);
        next.touchpadNatural = /(?:^|\n)\s*natural-scroll\s*(?:\n|$)/.test(pad);
        next.touchpadDwt = /(?:^|\n)\s*dwt\s*(?:\n|$)/.test(pad);
        next.touchpadSpeed = number(pad, "accel-speed", 0);
        next.touchpadProfile = /accel-profile\s+"flat"/.test(pad) ? "flat" : "adaptive";
        var mouse = readClass(text, "mouse");
        next.mouseNatural = /(?:^|\n)\s*natural-scroll\s*(?:\n|$)/.test(mouse);
        next.mouseLeftHanded = /(?:^|\n)\s*left-handed\s*(?:\n|$)/.test(mouse);
        next.mouseSpeed = number(mouse, "accel-speed", 0);
        next.mouseProfile = /accel-profile\s+"flat"/.test(mouse) ? "flat" : "adaptive";
        var touch = readClass(text, "touch");
        var tablet = readClass(text, "tablet");
        next.touchOutput = (/map-to-output\s+"([^"]+)"/.exec(touch) || ["", ""])[1];
        next.tabletOutput = /map-to-focused-output/.test(tablet)
            ? "@focused" : ((/map-to-output\s+"([^"]+)"/.exec(tablet) || ["", ""])[1]);
        next.focusFollowsMouse = /(?:^|\n)\s*focus-follows-mouse(?:\s|$)/.test(text);
        prefs = next;
    }

    function change(name, value) {
        var next = Object.assign({}, prefs);
        next[name] = value;
        prefs = next;
        save();
    }

    function kdlString(value) {
        return JSON.stringify(String(value));
    }

    function buildFragment() {
        var lines = ["// Generated by Sparrow Input; do not edit.", "input {", "    keyboard {"];
        if (prefs.layout)
            lines.push("        xkb {", "            layout " + kdlString(prefs.layout), "        }");
        if (prefs.numlock) lines.push("        numlock");
        lines.push("        repeat-rate " + Math.round(prefs.repeatRate));
        lines.push("        repeat-delay " + Math.round(prefs.repeatDelay));
        lines.push("    }");
        if (root.devices.touchpad || readClass(blockText, "touchpad")) {
            lines.push("    touchpad {");
            if (prefs.touchpadTap) lines.push("        tap");
            if (prefs.touchpadNatural) lines.push("        natural-scroll");
            if (prefs.touchpadDwt) lines.push("        dwt");
            lines.push("        accel-speed " + Number(prefs.touchpadSpeed).toFixed(2));
            lines.push("        accel-profile " + kdlString(prefs.touchpadProfile), "    }");
        }
        if (root.devices.mouse || readClass(blockText, "mouse")) {
            lines.push("    mouse {");
            if (prefs.mouseNatural) lines.push("        natural-scroll");
            if (prefs.mouseLeftHanded) lines.push("        left-handed");
            lines.push("        accel-speed " + Number(prefs.mouseSpeed).toFixed(2));
            lines.push("        accel-profile " + kdlString(prefs.mouseProfile), "    }");
        }
        if (root.devices.touchscreen || readClass(blockText, "touch")) {
            lines.push("    touch {");
            if (prefs.touchOutput) lines.push("        map-to-output " + kdlString(prefs.touchOutput));
            lines.push("    }");
        }
        if (root.devices.tablet || readClass(blockText, "tablet")) {
            lines.push("    tablet {");
            if (prefs.tabletOutput === "@focused") lines.push("        map-to-focused-output");
            else if (prefs.tabletOutput) lines.push("        map-to-output " + kdlString(prefs.tabletOutput));
            lines.push("    }");
        }
        if (prefs.focusFollowsMouse) lines.push("    focus-follows-mouse");
        lines.push("}", "");
        return lines.join("\n");
    }

    function save() {
        saveTimer.restart();
        note = "Changes will apply after Niri validates the settings."
    }

    function submit() {
        note = "Validating input settings…";
        Niri.writeManagedFragment("user-input", buildFragment());
    }

    Timer {
        id: saveTimer
        interval: 350
        repeat: false
        onTriggered: root.submit()
    }

    function seed() {
        blockText = inputFile.text();
        parseFragment(blockText);
        Niri.refreshOutputs();
        hardwareQuery.running = true;
        layoutQuery.running = true;
    }

    onActiveChanged: {
        if (active) {
            inputFile.reload();
            Qt.callLater(seed);
        } else {
            layoutOpen = false;
            layoutSearch = "";
            focusRowItem = null;
            kbIndex = -1;
        }
    }

    FileView {
        id: inputFile
        path: root.inputPath
        blockLoading: true
        printErrors: false
    }

    Process {
        id: hardwareQuery
        command: ["python3", root.infoHelper]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var result = JSON.parse(this.text);
                    root.devices = result.devices || root.devices;
                    root.layouts = result.layouts || [];
                    root.deviceQueryDone = true;
                    root.rows = root.sectionRows();
                } catch (error) {
                    root.note = "Could not inspect input devices or installed layouts.";
                }
            }
        }
    }

    Process {
        id: layoutQuery
        command: ["niri", "msg", "keyboard-layouts"]
        stdout: StdioCollector {
            onStreamFinished: {
                var lines = this.text.split("\n");
                for (var i = 0; i < lines.length; i++) {
                    var match = /^\s*\*\s*\d+\s+(.+?)\s*$/.exec(lines[i]);
                    if (match) { root.activeLayoutName = match[1]; break; }
                }
            }
        }
    }

    Connections {
        target: Niri
        function onManagedFragmentWriteFinished(requestId, status, message) {
            if (status === "success") {
                root.note = "";
                inputFile.reload();
                root.blockText = root.buildFragment();
            } else {
                root.note = message || "Niri rejected the input settings.";
            }
        }
    }

    component GroupLabel: Text {
        topPadding: 12 * root.s
        bottomPadding: 4 * root.s
        color: Theme.faint
        font.family: Theme.font
        font.pixelSize: 8.5 * root.s
        font.weight: Font.Bold
        font.capitalization: Font.AllUppercase
        font.letterSpacing: 1.2 * root.s
    }

    component FieldRow: Item {
        id: field
        property string label: ""
        property string caption: ""
        property string icon: ""
        default property alias control: controls.data
        readonly property bool focused: root.focusRowItem === field
        width: parent ? parent.width : 0
        height: 30 * root.s + ((focusHover.hovered || focused) && caption.length ? 14 * root.s : 0)
        clip: true
        Behavior on height { NumberAnimation { duration: Motion.fast; easing.type: Easing.OutCubic } }

        HoverHandler { id: focusHover; onHoveredChanged: root.reportRowHover(field, hovered) }
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 3 * root.s
            anchors.bottomMargin: 3 * root.s
            radius: 9 * root.s
            color: (focusHover.hovered || field.focused) ? Theme.frameBg : "transparent"
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.activateRow(field) }
        GlyphIcon {
            id: iconItem
            anchors.left: parent.left; anchors.leftMargin: 9 * root.s; anchors.verticalCenter: parent.verticalCenter
            visible: field.icon.length > 0; width: 15 * root.s; height: 15 * root.s
            name: field.icon; color: field.focused ? Theme.cream : Theme.subtle; stroke: 1.8
        }
        Column {
            anchors.left: iconItem.visible ? iconItem.right : parent.left; anchors.leftMargin: 9 * root.s
            anchors.verticalCenter: parent.verticalCenter; spacing: 2 * root.s
            Text { text: field.label; color: Theme.cream; font.family: Theme.font; font.pixelSize: 11.5 * root.s; font.weight: Font.Medium }
            Text { visible: (focusHover.hovered || field.focused) && field.caption.length > 0; text: field.caption; color: Theme.faint; font.family: Theme.font; font.pixelSize: 8.5 * root.s }
        }
        Item {
            id: controls
            anchors.right: parent.right; anchors.rightMargin: 8 * root.s; anchors.verticalCenter: parent.verticalCenter
            width: childrenRect.width; height: childrenRect.height
        }
    }

    Column {
        id: content
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        spacing: 0; clip: true

        SettingsHeader { s: root.s; title: "INPUT"; showBack: true }
        Column {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: 12 * root.s; anchors.rightMargin: 12 * root.s
            spacing: 0

            GroupLabel { text: "Keyboard" }
            FieldRow {
                id: layoutRow; label: "Layout"; icon: "language"
                Item {
                    width: 112 * root.s; height: layoutButton.height + (root.layoutOpen ? layoutList.height + 4 * root.s : 0)
                    Rectangle {
                        id: layoutButton
                        width: parent.width; height: 24 * root.s; radius: 8 * root.s
                        color: root.layoutOpen ? Qt.alpha(Theme.onGlow, 0.14) : "transparent"
                        border.width: 1; border.color: Theme.hairSoft
                        DisplayLabel {
                            anchors.left: parent.left; anchors.leftMargin: 8 * root.s; anchors.right: arrow.left
                            anchors.verticalCenter: parent.verticalCenter; s: root.s
                            text: root.prefs.layout ? root.layoutLabel(root.prefs.layout) : ("System · " + (root.activeLayoutName || "locale"))
                            color: Theme.cream
                        }
                        GlyphIcon { id: arrow; anchors.right: parent.right; anchors.rightMargin: 6 * root.s; anchors.verticalCenter: parent.verticalCenter; width: 12 * root.s; height: 12 * root.s; name: root.layoutOpen ? "chevron-up" : "chevron-down"; color: Theme.iconDim }
                        MouseArea { anchors.fill: parent; onClicked: { root.layoutOpen = !root.layoutOpen; root.layoutSearch = ""; } }
                    }
                    Column {
                        id: layoutList
                        anchors.top: layoutButton.bottom; anchors.topMargin: 4 * root.s; width: parent.width
                        visible: root.layoutOpen; height: visible ? Math.min(148 * root.s, 39 * root.s + Math.min(root.matchingLayouts.length, 4) * 24 * root.s) : 0
                        spacing: 2 * root.s
                        Rectangle {
                            width: parent.width; height: 31 * root.s; radius: 7 * root.s
                            color: Theme.cardTop; border.width: 1; border.color: Theme.frameBorder
                            TextInput {
                                id: layoutSearchInput
                                anchors.fill: parent; anchors.leftMargin: 8 * root.s; anchors.rightMargin: 8 * root.s
                                verticalAlignment: TextInput.AlignVCenter; color: Theme.cream
                                font.family: Theme.font; font.pixelSize: 10 * root.s
                                text: root.layoutSearch; onTextChanged: root.layoutSearch = text
                            }
                            Text {
                                anchors.left: parent.left; anchors.leftMargin: 8 * root.s; anchors.verticalCenter: parent.verticalCenter
                                visible: layoutSearchInput.text.length === 0; text: "Search layouts"; color: Theme.faint
                                font.family: Theme.font; font.pixelSize: 10 * root.s
                            }
                        }
                        ListView {
                            width: parent.width; height: parent.height - 33 * root.s; clip: true
                            model: root.matchingLayouts
                            delegate: Rectangle {
                                id: layoutOption
                                required property var modelData
                                width: ListView.view.width; height: 24 * root.s; radius: 6 * root.s
                                color: layoutHover.hovered ? Theme.frameBg : "transparent"
                                HoverHandler { id: layoutHover }
                                Text {
                                    anchors.left: parent.left; anchors.leftMargin: 8 * root.s; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                    text: layoutOption.modelData.code ? layoutOption.modelData.label + " · " + layoutOption.modelData.code : layoutOption.modelData.label
                                    color: Theme.subtle; elide: Text.ElideRight
                                    font.family: Theme.font; font.pixelSize: 10 * root.s
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                var next = Object.assign({}, root.prefs); next.layout = layoutOption.modelData.code;
                root.prefs = next; root.layoutOpen = false; root.save();
                                    }
                                }
                            }
                        }
                    }
                }
            }
            FieldRow {
                id: rateRow; label: "Repeat rate"; caption: "Key repeats per second"; icon: "keyboard"
                ScrubValue { id: rateScrub; s: root.s; value: root.prefs.repeatRate; from: 10; to: 80; step: 1; unit: "Hz"; onEdited: v => root.change("repeatRate", v) }
            }
            FieldRow {
                id: delayRow; label: "Repeat delay"; caption: "Hold time before repeating"; icon: "stopwatch"
                ScrubValue { id: delayScrub; s: root.s; value: root.prefs.repeatDelay; from: 150; to: 1000; step: 25; unit: "ms"; onEdited: v => root.change("repeatDelay", v) }
            }
            FieldRow {
                id: numlockRow; label: "Num Lock"; caption: "Turn on at startup"; icon: "lock"
                LinkToggle { s: root.s; on: root.prefs.numlock; onToggled: root.change("numlock", !root.prefs.numlock) }
            }

            GroupLabel { visible: root.deviceQueryDone && root.devices.touchpad; text: "Touchpad" }
            FieldRow { id: tapRow; visible: root.deviceQueryDone && root.devices.touchpad; label: "Tap to click"; icon: "mouse"; LinkToggle { s: root.s; on: root.prefs.touchpadTap; onToggled: root.change("touchpadTap", !root.prefs.touchpadTap) } }
            FieldRow { id: naturalTouchRow; visible: root.deviceQueryDone && root.devices.touchpad; label: "Natural scrolling"; icon: "arrow-down-up"; LinkToggle { s: root.s; on: root.prefs.touchpadNatural; onToggled: root.change("touchpadNatural", !root.prefs.touchpadNatural) } }
            FieldRow { id: dwtRow; visible: root.deviceQueryDone && root.devices.touchpad; label: "Disable while typing"; icon: "keyboard"; LinkToggle { s: root.s; on: root.prefs.touchpadDwt; onToggled: root.change("touchpadDwt", !root.prefs.touchpadDwt) } }
            FieldRow {
                id: touchSpeedRow; visible: root.deviceQueryDone && root.devices.touchpad; label: "Pointer speed"; icon: "mouse"
                ScrubValue { id: touchSpeedScrub; s: root.s; value: root.prefs.touchpadSpeed; from: -1; to: 1; step: 0.1; decimals: 1; onEdited: v => root.change("touchpadSpeed", v) }
            }
            FieldRow {
                id: touchAccelRow; visible: root.deviceQueryDone && root.devices.touchpad; label: "Acceleration"; icon: "bolt"
                SettingsSeg { s: root.s; options: [{label:"Adaptive",value:"adaptive"},{label:"Flat",value:"flat"}]; value: root.prefs.touchpadProfile; onPicked: v => root.change("touchpadProfile", v) }
            }

            GroupLabel { visible: root.deviceQueryDone && root.devices.mouse; text: "Mouse" }
            FieldRow { id: mouseSpeedRow; visible: root.deviceQueryDone && root.devices.mouse; label: "Pointer speed"; icon: "mouse"; ScrubValue { id: mouseSpeedScrub; s: root.s; value: root.prefs.mouseSpeed; from: -1; to: 1; step: 0.1; decimals: 1; onEdited: v => root.change("mouseSpeed", v) } }
            FieldRow { id: mouseAccelRow; visible: root.deviceQueryDone && root.devices.mouse; label: "Acceleration"; icon: "bolt"; SettingsSeg { s: root.s; options: [{label:"Adaptive",value:"adaptive"},{label:"Flat",value:"flat"}]; value: root.prefs.mouseProfile; onPicked: v => root.change("mouseProfile", v) } }
            FieldRow { id: naturalMouseRow; visible: root.deviceQueryDone && root.devices.mouse; label: "Natural scrolling"; icon: "arrow-down-up"; LinkToggle { s: root.s; on: root.prefs.mouseNatural; onToggled: root.change("mouseNatural", !root.prefs.mouseNatural) } }
            FieldRow { id: leftHandedRow; visible: root.deviceQueryDone && root.devices.mouse; label: "Left handed"; icon: "mouse"; LinkToggle { s: root.s; on: root.prefs.mouseLeftHanded; onToggled: root.change("mouseLeftHanded", !root.prefs.mouseLeftHanded) } }

            GroupLabel { visible: root.deviceQueryDone && root.devices.touchscreen; text: "Touchscreen" }
            FieldRow {
                id: touchMapRow; visible: root.deviceQueryDone && root.devices.touchscreen; label: "Map to output"; icon: "monitor"
                Item {
                    width: 142 * root.s; height: touchPicker.implicitHeight
                    DisplayPicker { id: touchPicker; anchors.fill: parent; s: root.s; label: ""; options: root.outputOptions(false); value: root.prefs.touchOutput; open: root.touchMapOpen; onRequestToggle: root.touchMapOpen = !root.touchMapOpen; onPicked: v => { root.change("touchOutput", v); root.touchMapOpen = false; } }
                }
            }
            GroupLabel { visible: root.deviceQueryDone && root.devices.tablet; text: "Pen / Tablet" }
            FieldRow {
                id: tabletMapRow; visible: root.deviceQueryDone && root.devices.tablet; label: "Map to output"; icon: "pen-tool"
                Item {
                    width: 142 * root.s; height: tabletPicker.implicitHeight
                    DisplayPicker { id: tabletPicker; anchors.fill: parent; s: root.s; label: ""; options: root.outputOptions(true); value: root.prefs.tabletOutput; open: root.tabletMapOpen; onRequestToggle: root.tabletMapOpen = !root.tabletMapOpen; onPicked: v => { root.change("tabletOutput", v); root.tabletMapOpen = false; } }
                }
            }

            GroupLabel { text: "Focus" }
            FieldRow {
                id: focusRow; label: "Focus follows mouse"; caption: "Focus a window when the pointer enters it"; icon: "mouse-pointer-2"
                LinkToggle { s: root.s; on: root.prefs.focusFollowsMouse; onToggled: root.change("focusFollowsMouse", !root.prefs.focusFollowsMouse) }
            }
            Text { width: parent.width; topPadding: 6 * root.s; visible: root.note.length > 0; text: root.note; color: Theme.subtle; wrapMode: Text.WordWrap; font.family: Theme.font; font.pixelSize: 9 * root.s }
            Item { width: 1; height: 10 * root.s }
        }
    }

    function layoutLabel(code) {
        for (var i = 0; i < layouts.length; i++)
            if (layouts[i].code === code) return layouts[i].label + " · " + code;
        return code;
    }

    function outputOptions(tablet) {
        var options = tablet ? [{ label: "Follow focused output", value: "@focused" }, { label: "All outputs", value: "" }]
                             : [{ label: "All outputs", value: "" }];
        for (var i = 0; i < Niri.outputs.length; i++)
            options.push({ label: Niri.outputs[i].name, value: Niri.outputs[i].name });
        return options;
    }
}
