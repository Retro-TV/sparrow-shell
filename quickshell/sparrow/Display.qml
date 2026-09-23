pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import "lib/monitors.js" as Mon
import "Singletons"

/**
 * Niri-native display controls in Sparrow's existing settings surface. Output
 * discovery and display numbers come from Niri IPC; arrangement is represented
 * in logical pixels. Changes use validated Sparrow-owned config fragments and
 * a detached rollback watchdog for display confirmation.
 */
SettingsSurface {
    id: root

    backSurface: "settings"
    implicitHeight: content.implicitHeight

    readonly property var monitors: Niri.outputs || []
    readonly property string outputFragmentPath: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/niri/sparrow/display-outputs.kdl"

    property string pendingToken: ""
    property int pendingRequestId: -1
    property int pendingNumberRequestId: -1
    property int pendingDisplayNumber: 0
    property string openPicker: ""
    property int countdown: 0
    property string note: ""
    property string selName: ""
    property var pendingPositions: ({})
    property var editsByName: ({})
    property string outputFragmentText: ""

    readonly property var selMon: monitorByName(selName)
    readonly property var orderedMonitors: Niri.numberedOutputs || []
    readonly property var displayList: {
        var active = orderedMonitors;
        var inactive = (monitors || []).filter(function (o) { return !o.enabled; }).slice();
        inactive.sort(function (a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); });
        return active.concat(inactive);
    }

    readonly property var scaleOptions: [
        { label: "0.75", value: 0.75 },
        { label: "1.0", value: 1 },
        { label: "1.25", value: 1.25 },
        { label: "1.5", value: 1.5 },
        { label: "1.75", value: 1.75 },
        { label: "2.0", value: 2 },
        { label: "2.5", value: 2.5 },
        { label: "3.0", value: 3 }
    ]

    onActiveChanged: {
        if (active) {
            Niri.refreshOutputs();
            outputFile.reload();
            root.outputFragmentText = outputFile.text();
            var ordered = root.orderedMonitors || [];
            if (!root.selMon && ordered.length > 0)
                root.selName = ordered[0].name;
            if (root.selMon) {
                Qt.callLater(function () {
                    if (root.active && root.selMon)
                        card.syncToCurrent();
                });
            }
        } else {
            if (root.pendingToken.length > 0)
                Niri.rollbackManagedFragment(root.pendingToken);
            openPicker = "";
            focusRowItem = null;
            kbIndex = -1;
        }
    }

    onSelMonChanged: if (selMon) card.syncToCurrent()
    onMonitorsChanged: {
        if (!active)
            return;
        if (!selMon) {
            var ordered = root.orderedMonitors || [];
            if (ordered.length > 0)
                root.selName = ordered[0].name;
        } else if (!card.pending) {
            card.syncToCurrent();
        }
    }

    rows: {
        void root.selMon;
        void root.monitors;
        var e = [
            { item: resRow, kind: "scrub", bump: function (d) { card.bumpRes(d); } },
            { item: rateRow, kind: "scrub", bump: function (d) { card.bumpRate(d); } },
            { item: scaleRow, kind: "seg", vals: root.scaleOptions.map(function (o) { return o.value; }), get: function () { return card.pickScale; }, set: function (v) { card.pickScale = v; card.saveCardEdit(); } },
            { item: transformRow, kind: "scrub", bump: function (d) { card.bumpTransform(d); } },
            { item: numberRow, kind: "seg", vals: root.numberOptions(), get: function () { return root.displayNumber(root.selName); }, set: function (v) { root.assignDisplayNumber(v); } },
            { item: startupFocusRow, kind: "toggle", get: function () { return card.pickFocusAtStartup; }, set: function (v) { card.setFocusAtStartup(v); } }
        ];
        return e;
    }

    /** Group Niri's exact milli-Hz modes without rounding away near-duplicates. */
    function resolutionsFor(mon) {
        var byRes = {};
        for (var i = 0; i < mon.modes.length; i++) {
            var m = mon.modes[i];
            var key = m.w + "x" + m.h;
            if (!byRes[key])
                byRes[key] = { w: m.w, h: m.h, key: key, rates: [] };
            if (!byRes[key].rates.some(function (rate) { return rate.refreshMilliHz === m.refreshMilliHz; }))
                byRes[key].rates.push(m);
        }
        var list = [];
        for (var k in byRes) {
            byRes[k].rates.sort(function (a, b) { return b.refreshMilliHz - a.refreshMilliHz; });
            list.push(byRes[k]);
        }
        list.sort(function (a, b) {
            if (mon.currentMode && a.w === mon.currentMode.w && a.h === mon.currentMode.h) return -1;
            if (mon.currentMode && b.w === mon.currentMode.w && b.h === mon.currentMode.h) return 1;
            return (b.w * b.h) - (a.w * a.h);
        });
        return list;
    }

    function monitorByName(name) {
        for (var i = 0; i < monitors.length; i++)
            if (monitors[i].name === name)
                return monitors[i];
        return null;
    }

    function storedSettings(mon) {
        return Mon.parseManagedOutputBlocks(outputFragmentText)[mon.identity] || null;
    }

    function editsDifferFromOtherLiveOutputs() {
        var names = Object.keys(editsByName);
        for (var i = 0; i < names.length; i++) {
            var name = names[i];
            if (name === selName)
                continue;
            var mon = monitorByName(name);
            if (!mon)
                return true;
            var edit = editsByName[name];
            var saved = storedSettings(mon);
            var baselineMode = mon.currentMode;
            if (!baselineMode && saved) {
                for (var j = 0; j < mon.modes.length; j++)
                    if (Mon.modeString(mon.modes[j]) === saved.mode) { baselineMode = mon.modes[j]; break; }
            }
            var baselineScale = mon.enabled ? mon.scale : (saved ? saved.scale : 1);
            var baselineTransform = mon.enabled ? mon.transform : (saved ? saved.transform : "normal");
            if ((edit.enabled !== undefined && edit.enabled !== mon.enabled)
                    || (edit.scale !== undefined && edit.scale !== baselineScale)
                    || (edit.transform !== undefined && edit.transform !== baselineTransform)
                    || (edit.focusAtStartup !== undefined
                        && edit.focusAtStartup !== !!(saved && saved.focusAtStartup))
                    || (edit.mode !== undefined && (!baselineMode
                        || Mon.modeString(edit.mode) !== Mon.modeString(baselineMode))))
                return true;
        }
        return false;
    }

    function displayNumber(name) {
        return Niri.monitorNumberForOutput(name);
    }

    function numberOptions() {
        var count = root.monitors.filter(function (output) { return output.enabled; }).length;
        count = Math.max(count, root.selMon ? root.displayNumber(root.selMon.name) : 0);
        var options = [];
        for (var i = 1; i <= count; i++)
            options.push({ label: String(i), value: i });
        return options;
    }

    function assignDisplayNumber(number) {
        if (!root.selMon)
            return;
        var requestId = Niri.setMonitorNumber(root.selMon.name, number);
        if (requestId < 0) {
            root.note = "Could not save that display number; finish or revert the active display preview first.";
        } else if (requestId === 0) {
            root.note = "This display already has number " + number + ".";
        } else {
            root.pendingNumberRequestId = requestId;
            root.pendingDisplayNumber = Number(number);
            root.note = "Saving this as display " + number + "; the matching F-key shortcuts will follow.";
        }
    }

    function outputSettings(mon) {
        var old = storedSettings(mon);
        var oldMode = null;
        if (old) {
            for (var i = 0; i < mon.modes.length; i++)
                if (Mon.modeString(mon.modes[i]) === old.mode) { oldMode = mon.modes[i]; break; }
        }
        var settings = {
            mode: mon.currentMode || oldMode || (mon.modes.find(function (m) { return m.preferred; }) || mon.modes[0] || null),
            scale: mon.enabled ? mon.scale : (old ? old.scale : mon.scale),
            transform: mon.enabled ? mon.transform : (old ? old.transform : mon.transform),
            enabled: mon.enabled || (old ? old.enabled : false),
            focusAtStartup: !!(old && old.focusAtStartup)
        };
        Object.assign(settings, root.editsByName[mon.name] || {});
        if (mon.name === root.selName && card.ready) {
            var res = card.resolutions[Math.min(card.resIndex, Math.max(0, card.resolutions.length - 1))];
            var mode = res && res.rates.length > 0
                ? res.rates[Math.min(card.rateIndex, res.rates.length - 1)] : mon.currentMode;
            settings.mode = mode || settings.mode;
            settings.scale = card.pickScale;
            settings.transform = card.pickTransform;
            settings.focusAtStartup = card.pickFocusAtStartup;
        }
        var position = root.pendingPositions[mon.name];
        settings.position = position || (mon.enabled || !old
            ? { x: mon.x, y: mon.y } : { x: old.x, y: old.y });
        return settings;
    }

    function outputRect(mon) {
        var settings = outputSettings(mon);
        var mode = settings.mode || mon.currentMode;
        if (!mode)
            return null;
        var size = Mon.logicalSize(mode, Number(settings.scale || mon.scale), settings.transform || mon.transform);
        return {
            name: mon.name,
            label: mon.label,
            x: Number(settings.position.x),
            y: Number(settings.position.y),
            width: size.width,
            height: size.height,
            mode: mode,
            scale: Number(settings.scale || mon.scale),
            transform: settings.transform || mon.transform,
            enabled: settings.enabled !== false
        };
    }

    function dropTile(name, cx, cy) {
        if (!monitorByName(name) || mapLayout.factor <= 0)
            return;
        var current = monitorByName(name);
        var movingRect = root.outputRect(current);
        var proposed = {
            x: (cx - mapLayout.offsetX) / mapLayout.factor + mapLayout.minX - movingRect.width / 2,
            y: (cy - mapLayout.offsetY) / mapLayout.factor + mapLayout.minY - movingRect.height / 2
        };
        var rectangles = [];
        for (var i = 0; i < root.monitors.length; i++) {
            var rect = root.outputRect(root.monitors[i]);
            if (rect && rect.enabled)
                rectangles.push(rect);
        }
        var snapped = Mon.snapOutputPosition(rectangles, name, proposed);
        if (!snapped.ok) {
            root.note = snapped.error;
            return;
        }
        var positions = Object.assign({}, root.pendingPositions);
        positions[name] = snapped.position;
        var saved = root.storedSettings(current);
        var baseline = current.enabled || !saved
            ? { x: current.x, y: current.y } : { x: saved.x, y: saved.y };
        if (positions[name].x === baseline.x && positions[name].y === baseline.y)
            delete positions[name];
        root.pendingPositions = positions;
        if (snapped.target)
            root.note = "Snapped " + current.label + " to the " + snapped.side + " edge of "
                + monitorByName(snapped.target).label + ".";
    }

    /**
     * Scaled tile geometry for the mini-map: logical rects (mode over scale,
     * pending move substituted for its monitor) fitted into the map width and a
     * capped height, centred horizontally. Selection and main state stay out of
     * the entries on purpose — they are read per-tile from root, so clicking a
     * tile never rebuilds the Repeater under an active press.
     */
    readonly property var mapLayout: {
        var mons = root.displayList;
        if (mons.length === 0 || mapBox.width <= 0)
            return { h: 0, tiles: [], factor: 0, minX: 0, minY: 0, offsetX: 0, offsetY: 0 };
        var inactive = mons.filter(function (m) { return !m.enabled; });
        var rects = [];
        var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (var i = 0; i < mons.length; i++) {
            var m = mons[i];
            var r = root.outputRect(m);
            if (!r || !r.enabled)
                continue;
            r.w = r.width;
            r.h = r.height;
            rects.push(r);
            minX = Math.min(minX, r.x);
            minY = Math.min(minY, r.y);
            maxX = Math.max(maxX, r.x + r.w);
            maxY = Math.max(maxY, r.y + r.h);
        }
        var k = rects.length > 0
            ? Math.min(mapBox.width / Math.max(1, maxX - minX), (112 * root.s) / Math.max(1, maxY - minY)) : 0;
        var ox = rects.length > 0 ? (mapBox.width - (maxX - minX) * k) / 2 : 0;
        var tiles = rects.map(function (t) {
            return { name: t.name, label: t.label, number: root.displayNumber(t.name), enabled: t.enabled,
                mode: t.mode, refreshMilliHz: t.mode.refreshMilliHz,
                x: ox + (t.x - minX) * k, y: (t.y - minY) * k,
                w: t.w * k, h: t.h * k };
        });
        var layoutHeight = rects.length > 0 ? Math.max(38 * root.s, (maxY - minY) * k) : 0;
        if (inactive.length > 0) {
            var gap = 6 * root.s;
            var chipW = Math.max(58 * root.s, (mapBox.width - gap * (inactive.length - 1)) / inactive.length);
            for (var j = 0; j < inactive.length; j++) {
                var offRect = root.outputRect(inactive[j]);
                if (!offRect)
                    continue;
                tiles.push({ name: offRect.name, label: offRect.label, number: 0, enabled: false,
                    mode: offRect.mode, refreshMilliHz: offRect.mode.refreshMilliHz,
                    x: j * (chipW + gap), y: layoutHeight + (layoutHeight > 0 ? 8 * root.s : 0),
                    w: chipW, h: 42 * root.s });
            }
        }
        return { h: layoutHeight + (inactive.length > 0 ? 50 * root.s : 0), tiles: tiles,
            factor: k, minX: minX, minY: minY, offsetX: ox, offsetY: 0 };
    }

    // Output monitor numbers are determined by Mon.numberedOutputs, shared with the bind generator.

    FileView {
        id: outputFile
        path: root.outputFragmentPath
        blockLoading: true
        printErrors: false
    }

    function apply() {
        if (!root.selMon || root.pendingRequestId >= 0 || root.pendingToken.length > 0 || !card.applyReady)
            return;
        var settings = {};
        for (var i = 0; i < monitors.length; i++)
            settings[monitors[i].name] = outputSettings(monitors[i]);
        var candidate = Mon.buildOutputFragment(monitors, settings, outputFragmentText);
        if (!candidate.ok) {
            note = candidate.error;
            return;
        }
        pendingRequestId = Niri.writeManagedFragment("display-outputs", candidate.text, true);
        note = "Applying a temporary layout…";
    }

    function keep() {
        if (pendingToken.length === 0)
            return;
        countTimer.stop();
        pendingResolveRequestId = Niri.confirmManagedFragment(pendingToken);
        note = "Saving the confirmed Niri display configuration…";
    }

    function revert() {
        if (pendingToken.length === 0)
            return;
        pendingResolveRequestId = Niri.rollbackManagedFragment(pendingToken);
        countTimer.stop();
        note = "Reverting to the previous display configuration…";
    }

    property int pendingResolveRequestId: -1

    Connections {
        target: Niri
        function onManagedFragmentWriteFinished(requestId, status, message, token, timeoutSeconds) {
            if (requestId === root.pendingRequestId) {
                root.pendingRequestId = -1;
                if (status === "confirmation_pending") {
                    root.pendingToken = token;
                    root.countdown = timeoutSeconds;
                    countTimer.start();
                    root.note = "Test the displays now. Keep this layout within " + timeoutSeconds + " seconds; otherwise it rolls back.";
                } else if (status === "success") {
                    root.note = "Display configuration already matches; nothing needed changing.";
                } else {
                    root.note = "Display change was not applied: " + message;
                }
            } else if (requestId === root.pendingNumberRequestId) {
                root.pendingNumberRequestId = -1;
                root.note = status === "success"
                    ? "Saved as display " + root.pendingDisplayNumber + "; matching F-key shortcuts are updated."
                    : "Could not save the display number: " + message;
            } else if (requestId === root.pendingResolveRequestId) {
                root.pendingResolveRequestId = -1;
                if (status === "confirmed") {
                    countTimer.stop();
                    root.pendingToken = "";
                    root.countdown = 0;
                    root.pendingPositions = ({});
                    root.editsByName = ({});
                    outputFile.reload();
                    root.outputFragmentText = outputFile.text();
                    Niri.refreshOutputs();
                    root.note = "Kept. Niri's output settings and display-number bindings are saved.";
                } else if (status === "rolled_back" || status === "already_resolved") {
                    root.pendingToken = "";
                    root.countdown = 0;
                    root.pendingPositions = ({});
                    root.editsByName = ({});
                    outputFile.reload();
                    root.outputFragmentText = outputFile.text();
                    Niri.refreshOutputs();
                    root.note = "Reverted to the previous display configuration.";
                } else {
                    if (root.pendingToken.length > 0 && root.countdown > 0)
                        countTimer.start();
                    root.note = "Could not finish the display transaction: " + message;
                    Niri.refreshOutputs();
                }
            }
        }
    }

    Timer {
        id: countTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.countdown -= 1;
            if (root.countdown <= 0) {
                stop();
                root.revert();
            }
        }
    }

    /**
     * One registry row inside the monitor card: a leading line icon (or a text
     * glyph for the star), the shared hover/focus treatment, and hover and
     * clicks routed through reportRowHover/activateRow so the soul seam and
     * keyboard focus track these rows like SettingsRow lines. The highlight
     * hugs only the head line, so an open dropdown grows past it.
     */
    component CardRow: Item {
        id: crow

        property string icon: ""
        property string glyphText: ""
        default property alias content: crowInner.data

        readonly property bool focused: root.focusRowItem === crow

        width: parent ? parent.width : 0
        implicitHeight: crowInner.childrenRect.height

        HoverHandler {
            id: crowHover
            onHoveredChanged: root.reportRowHover(crow, hovered)
        }

        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.topMargin: -3 * root.s
            anchors.leftMargin: -7 * root.s
            anchors.rightMargin: -7 * root.s
            height: 32 * root.s
            radius: 8 * root.s
            color: (crowHover.hovered || crow.focused) ? Theme.frameBg : "transparent"
            Behavior on color { ColorAnimation { duration: Motion.fast } }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.activateRow(crow)
        }

        GlyphIcon {
            id: crowIcon
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.topMargin: 5 * root.s
            width: 16 * root.s
            height: 16 * root.s
            name: crow.icon
            visible: crow.icon.length > 0
            color: crow.focused ? Theme.cream : Theme.subtle
            stroke: 1.8
        }

        Text {
            anchors.centerIn: crowIcon
            visible: crow.glyphText.length > 0
            text: crow.glyphText
            color: crow.focused ? Theme.cream : Theme.subtle
            font.family: Theme.fontJp
            font.pixelSize: 13 * root.s
        }

        Item {
            id: crowInner
            anchors.left: crowIcon.right
            anchors.leftMargin: 9 * root.s
            anchors.right: parent.right
            anchors.top: parent.top
            height: childrenRect.height
        }
    }

    Column {
        id: content
        z: 100
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0
        height: root.height + root.mBottom * root.s
        clip: true

        SettingsHeader {
            s: root.s
            glyph: "画"
            title: "DISPLAY"
            showBack: true
        }

        Item { width: 1; height: 12 * root.s }

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 12 * root.s
            anchors.rightMargin: 12 * root.s
            spacing: 12 * root.s

            Item {
                id: mapBox
                width: parent.width
                height: root.mapLayout.h
                Behavior on height { NumberAnimation { duration: Motion.standard; easing.type: Motion.easeStandard } }

                Repeater {
                    model: root.mapLayout.tiles

                    Rectangle {
                        id: tile
                        required property var modelData

                        readonly property bool sel: tile.modelData.name === root.selName
                        readonly property bool moved: !!root.pendingPositions[tile.modelData.name]
                        property real dx: 0
                        property real dy: 0

                        x: tile.modelData.x + 1.5 * root.s + dx
                        y: tile.modelData.y + 1.5 * root.s + dy
                        width: Math.max(2, tile.modelData.w - 3 * root.s)
                        height: Math.max(2, tile.modelData.h - 3 * root.s)
                        z: tileDrag.active ? 10 : (tile.sel ? 5 : 0)
                        radius: 7 * root.s
                        color: !tile.modelData.enabled ? Qt.alpha(Theme.cardTop, 0.52)
                            : (tile.sel ? Qt.alpha(Theme.onGlow, 0.13) : Theme.cardTop)
                        border.width: 1
                        border.color: tile.moved ? Qt.alpha(Theme.vermLit, 0.7) : (tile.sel ? Theme.cream : Theme.hairSoft)

                        Behavior on x { enabled: !tileDrag.active; NumberAnimation { duration: Motion.standard; easing.type: Motion.easeStandard } }
                        Behavior on y { enabled: !tileDrag.active; NumberAnimation { duration: Motion.standard; easing.type: Motion.easeStandard } }
                        Behavior on color { ColorAnimation { duration: Motion.fast } }
                        Behavior on border.color { ColorAnimation { duration: Motion.fast } }

                        Column {
                            anchors.centerIn: parent
                            spacing: 2 * root.s

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: Math.max(0, tile.width - 10 * root.s)
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                text: tile.modelData.enabled
                                    ? (tile.modelData.number > 0 ? String(tile.modelData.number) : "…") : "Off"
                                color: tile.sel ? Theme.cream : Theme.subtle
                                font.family: Theme.font
                                font.pixelSize: 12 * root.s
                                font.weight: Font.DemiBold
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: Math.max(0, tile.width - 10 * root.s)
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                text: tile.modelData.mode.w + "×" + tile.modelData.mode.h + " · "
                                    + (tile.modelData.refreshMilliHz / 1000).toFixed(3) + " Hz"
                                color: Theme.faint
                                font.family: Theme.font
                                font.pixelSize: 7.5 * root.s
                                font.weight: Font.Medium
                                font.features: { "tnum": 1 }
                            }
                        }

                        TapHandler {
                            onTapped: {
                                if (root.pendingRequestId < 0 && root.pendingToken.length === 0)
                                    root.selName = tile.modelData.name;
                            }
                        }

                        DragHandler {
                            id: tileDrag
                            target: null
                            acceptedButtons: Qt.LeftButton
                            enabled: tile.modelData.enabled && root.monitors.length >= 2
                                && root.pendingRequestId < 0 && root.pendingToken.length === 0
                            cursorShape: active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                            onActiveChanged: {
                                if (active) {
                                    root.selName = tile.modelData.name;
                                } else if (tile.dx !== 0 || tile.dy !== 0) {
                                    root.dropTile(tile.modelData.name,
                                        tile.modelData.x + tile.modelData.w / 2 + tile.dx,
                                        tile.modelData.y + tile.modelData.h / 2 + tile.dy);
                                    tile.dx = 0;
                                    tile.dy = 0;
                                }
                            }
                            onActiveTranslationChanged: {
                                if (active) {
                                    tile.dx = activeTranslation.x;
                                    tile.dy = activeTranslation.y;
                                }
                            }
                        }
                    }
                }
            }

            Text {
                width: parent.width
                text: Object.keys(root.pendingPositions).length > 0
                    ? "Drag to snap displays edge-to-edge · Apply and Keep to save position"
                    : "Drag to arrange · set each display number below"
                color: Theme.faint
                font.family: Theme.font
                font.pixelSize: 9.5 * root.s
                font.weight: Font.Medium
                wrapMode: Text.WordWrap
            }

            Rectangle {
                id: card
                visible: root.selMon !== null
                width: parent.width
                radius: Motion.rTile * root.s
                color: Theme.cardTop
                border.width: 1
                border.color: card.pending ? Qt.alpha(Theme.vermLit, 0.55) : Theme.hairSoft
                implicitHeight: cardCol.implicitHeight + 22 * root.s
                Behavior on border.color { ColorAnimation { duration: Motion.fast } }

                property int resIndex: 0
                property int rateIndex: 0
                property real pickScale: 1
                property string pickTransform: "normal"
                property bool pickFocusAtStartup: false
                property bool ready: false

                readonly property var resolutions: root.selMon ? root.resolutionsFor(root.selMon) : []
                readonly property var rates: resolutions.length > 0 ? resolutions[Math.min(resIndex, resolutions.length - 1)].rates : []
                readonly property var transforms: ["normal", "90", "180", "270", "flipped", "flipped-90", "flipped-180", "flipped-270"]
                readonly property bool pending: root.pendingToken.length > 0 || root.pendingRequestId >= 0

                /** Any mode, position, scale or transform difference is a config change. */
                readonly property bool dirty: {
                    if (!root.selMon || !card.ready || card.rates.length === 0)
                        return false;
                    var mode = card.rates[Math.min(card.rateIndex, card.rates.length - 1)];
                    var mon = root.selMon;
                    var saved = root.storedSettings(mon);
                    var oldPosition = root.pendingPositions[mon.name]
                        || (mon.enabled || !saved ? { x: mon.x, y: mon.y } : { x: saved.x, y: saved.y });
                    var liveMode = mon.currentMode;
                    var baselineMode = liveMode;
                    if (!baselineMode && saved) {
                        for (var i = 0; i < mon.modes.length; i++)
                            if (Mon.modeString(mon.modes[i]) === saved.mode) { baselineMode = mon.modes[i]; break; }
                    }
                    var modeChanged = baselineMode
                        ? Mon.modeString(mode) !== Mon.modeString(baselineMode) : !!mode;
                    var baseScale = mon.enabled ? mon.scale : (saved ? saved.scale : 1);
                    var baseTransform = mon.enabled ? mon.transform : (saved ? saved.transform : "normal");
                    var anyOtherEdit = root.editsDifferFromOtherLiveOutputs();
                    return modeChanged || card.pickScale !== baseScale
                        || card.pickTransform !== baseTransform
                        || card.pickFocusAtStartup !== !!(saved && saved.focusAtStartup)
                        || (mon.enabled && (oldPosition.x !== mon.x || oldPosition.y !== mon.y)) || anyOtherEdit
                        || Object.keys(root.pendingPositions).length > 0;
                }
                readonly property string arrangementError: {
                    var rects = [];
                    for (var i = 0; i < root.displayList.length; i++) {
                        var rect = root.outputRect(root.displayList[i]);
                        if (rect && rect.enabled)
                            rects.push({ label: rect.label, x: rect.x, y: rect.y,
                                width: rect.width, height: rect.height });
                    }
                    return Mon.overlapError(rects);
                }
                readonly property bool applyReady: dirty && arrangementError.length === 0 && !pending

                function syncToCurrent() {
                    var mon = root.selMon;
                    if (!mon)
                        return;
                    var resos = root.resolutionsFor(mon);
                    var stored = root.storedSettings(mon);
                    var edit = root.editsByName[mon.name] || null;
                    var selectedMode = edit && edit.mode ? edit.mode : mon.currentMode;
                    if (!selectedMode && stored) {
                        for (var m = 0; m < mon.modes.length; m++)
                            if (Mon.modeString(mon.modes[m]) === stored.mode) { selectedMode = mon.modes[m]; break; }
                    }
                    if (!selectedMode)
                        selectedMode = mon.modes.find(function (mode) { return mode.preferred; }) || mon.modes[0] || null;
                    var ri = 0;
                    for (var i = 0; i < resos.length; i++) {
                        if (selectedMode && resos[i].w === selectedMode.w && resos[i].h === selectedMode.h) {
                            ri = i;
                            break;
                        }
                    }
                    card.resIndex = ri;
                    card.rateIndex = card.nearestIn(resos.length > 0 ? resos[ri].rates : [], selectedMode ? selectedMode.refreshMilliHz : 0);
                    card.pickScale = edit && edit.scale !== undefined
                        ? edit.scale : (mon.enabled ? mon.scale : (stored ? stored.scale : 1));
                    card.pickTransform = edit && edit.transform !== undefined
                        ? edit.transform : (mon.enabled ? mon.transform : (stored ? stored.transform : "normal"));
                    card.pickFocusAtStartup = edit && edit.focusAtStartup !== undefined
                        ? edit.focusAtStartup : !!(stored && stored.focusAtStartup);
                    card.ready = true;
                    root.openPicker = "";
                }

                function nearestIn(rates, refreshMilliHz) {
                    var best = 0;
                    var bestDiff = 1e9;
                    for (var i = 0; i < rates.length; i++) {
                        var d = Math.abs(rates[i].refreshMilliHz - refreshMilliHz);
                        if (d < bestDiff) { bestDiff = d; best = i; }
                    }
                    return best;
                }

                function nearestRateIndex(refreshMilliHz) {
                    return nearestIn(card.rates, refreshMilliHz);
                }

                function bumpRes(d) {
                    var i = Math.max(0, Math.min(card.resolutions.length - 1, card.resIndex + d));
                    if (i === card.resIndex)
                        return;
                    card.resIndex = i;
                    card.rateIndex = card.nearestRateIndex(card.rates.length > 0 ? card.rates[0].refreshMilliHz : 0);
                    card.saveCardEdit();
                }

                function bumpRate(d) {
                    var cur = Math.min(card.rateIndex, Math.max(0, card.rates.length - 1));
                    card.rateIndex = Math.max(0, Math.min(card.rates.length - 1, cur + d));
                    card.saveCardEdit();
                }

                function bumpTransform(d) {
                    var index = transforms.indexOf(card.pickTransform);
                    card.pickTransform = transforms[(index + d + transforms.length) % transforms.length];
                    card.saveCardEdit();
                }

                function setFocusAtStartup(value) {
                    if (value && (!root.selMon || !root.selMon.enabled)) {
                        root.note = "An inactive display cannot be selected for startup focus.";
                        return;
                    }
                    var edits = Object.assign({}, root.editsByName);
                    for (var i = 0; i < root.monitors.length; i++) {
                        var output = root.monitors[i];
                        var edit = Object.assign({}, edits[output.name] || {});
                        edit.focusAtStartup = value && output.name === root.selName;
                        edits[output.name] = edit;
                    }
                    root.editsByName = edits;
                    card.pickFocusAtStartup = value;
                    card.saveCardEdit();
                }

                function saveCardEdit() {
                    var mon = root.selMon;
                    if (!mon || !card.ready || card.rates.length === 0)
                        return;
                    var edits = Object.assign({}, root.editsByName);
                    edits[mon.name] = {
                        mode: card.rates[Math.min(card.rateIndex, card.rates.length - 1)],
                        scale: card.pickScale,
                        transform: card.pickTransform,
                        focusAtStartup: card.pickFocusAtStartup
                    };
                    root.editsByName = edits;
                }

                Column {
                    id: cardCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 13 * root.s
                    anchors.rightMargin: 13 * root.s
                    anchors.topMargin: 11 * root.s
                    spacing: 9 * root.s

                    Text {
                        width: parent.width
                        text: root.selMon ? "DISPLAY " + root.displayNumber(root.selMon.name)
                            + "  ·  " + root.selMon.label + "  ·  " + root.selMon.name : ""
                        color: Theme.cream
                        font.family: Theme.font
                        font.pixelSize: 12.5 * root.s
                        font.weight: Font.Bold
                        font.letterSpacing: 0.3 * root.s
                        elide: Text.ElideRight
                    }

                    CardRow {
                        id: resRow
                        icon: "monitor"

                        DisplayPicker {
                            width: parent.width
                            s: root.s
                            label: "Resolution"
                            options: card.resolutions.map(function (r, i) { return { label: r.w + "×" + r.h, value: i }; })
                            value: card.resIndex
                            open: root.openPicker === root.selName + ":res"
                            onRequestToggle: root.openPicker = (root.openPicker === root.selName + ":res" ? "" : root.selName + ":res")
                            onPicked: (v) => {
                                card.resIndex = v;
                                card.rateIndex = card.nearestRateIndex(card.rates.length > 0 ? card.rates[0].refreshMilliHz : 0);
                                card.saveCardEdit();
                                root.openPicker = "";
                            }
                        }
                    }

                    CardRow {
                        id: rateRow
                        icon: "reboot"

                        DisplayPicker {
                            width: parent.width
                            s: root.s
                            label: "Refresh"
                            options: card.rates.map(function (mode, i) { return { label: (mode.refreshMilliHz / 1000).toFixed(3) + " Hz", value: i }; })
                            value: Math.min(card.rateIndex, Math.max(0, card.rates.length - 1))
                            open: root.openPicker === root.selName + ":rate"
                            onRequestToggle: root.openPicker = (root.openPicker === root.selName + ":rate" ? "" : root.selName + ":rate")
                            onPicked: (v) => {
                                card.rateIndex = v;
                                card.saveCardEdit();
                                root.openPicker = "";
                            }
                        }
                    }

                    CardRow {
                        id: scaleRow
                        icon: "scaling"

                        DisplayPicker {
                            width: parent.width
                            s: root.s
                            label: "Scale"
                            options: root.scaleOptions
                            value: card.pickScale
                            open: root.openPicker === root.selName + ":scale"
                            onRequestToggle: root.openPicker = (root.openPicker === root.selName + ":scale" ? "" : root.selName + ":scale")
                            onPicked: (v) => {
                                card.pickScale = v;
                                card.saveCardEdit();
                                root.openPicker = "";
                            }
                        }
                    }

                    CardRow {
                        id: transformRow
                        icon: "rotate-cw"

                        DisplayPicker {
                            width: parent.width
                            s: root.s
                            label: "Orientation"
                            options: card.transforms.map(function (value) {
                                var names = { "normal": "0°", "90": "90°", "180": "180°", "270": "270°",
                                    "flipped": "Flipped", "flipped-90": "Flipped 90°", "flipped-180": "Flipped 180°", "flipped-270": "Flipped 270°" };
                                return { label: names[value], value: value };
                            })
                            value: card.pickTransform
                            open: root.openPicker === root.selName + ":transform"
                            onRequestToggle: root.openPicker = (root.openPicker === root.selName + ":transform" ? "" : root.selName + ":transform")
                            onPicked: (v) => {
                                card.pickTransform = v;
                                card.saveCardEdit();
                                root.openPicker = "";
                            }
                        }
                    }

                    CardRow {
                        id: numberRow
                        icon: "monitor"

                        DisplayPicker {
                            width: parent.width
                            s: root.s
                            label: "Number"
                            options: root.numberOptions()
                            value: root.selMon ? root.displayNumber(root.selMon.name) : 0
                            open: root.openPicker === root.selName + ":number"
                            onRequestToggle: root.openPicker = (root.openPicker === root.selName + ":number" ? "" : root.selName + ":number")
                            onPicked: (v) => {
                                root.assignDisplayNumber(v);
                                root.openPicker = "";
                            }
                        }
                    }

                    CardRow {
                        id: startupFocusRow
                        icon: "monitor"

                        Item {
                            width: parent.width
                            height: 26 * root.s

                            Text {
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Focus at Niri startup"
                                color: Theme.cream
                                font.family: Theme.font
                                font.pixelSize: 11 * root.s
                                font.weight: Font.DemiBold
                            }

                            LinkToggle {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                s: root.s
                                on: card.pickFocusAtStartup
                                onToggled: card.setFocusAtStartup(!card.pickFocusAtStartup)
                            }
                        }
                    }

                    Item {
                        width: parent.width
                        height: 30 * root.s

                        Rectangle {
                            id: applyBtn
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            visible: !card.pending
                            width: applyLabel.implicitWidth + 28 * root.s
                            height: 28 * root.s
                            radius: 9 * root.s
                            color: !card.applyReady ? Qt.alpha(Theme.onGlow, 0.10)
                                : (applyArea.containsMouse ? Qt.alpha(Theme.onGlow, 0.34) : Qt.alpha(Theme.onGlow, 0.20))
                            border.width: 1
                            border.color: Qt.alpha(Theme.onGlow, !card.applyReady ? 0.22 : (applyArea.containsMouse ? 0.6 : 0.4))
                            Behavior on color { ColorAnimation { duration: Motion.fast } }
                            Behavior on border.color { ColorAnimation { duration: Motion.fast } }

                            Text {
                                id: applyLabel
                                anchors.centerIn: parent
                                text: "Apply"
                                color: card.applyReady ? Theme.cream : Theme.faint
                                font.family: Theme.font
                                font.pixelSize: 9.5 * root.s
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.3 * root.s
                            }

                            MouseArea {
                                id: applyArea
                                anchors.fill: parent
                                hoverEnabled: true
                                enabled: card.applyReady
                                cursorShape: card.applyReady ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    root.apply();
                                }
                            }
                        }

                        Row {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            visible: root.pendingToken.length > 0
                            spacing: 9 * root.s

                            Rectangle {
                                id: keepBtn
                                anchors.verticalCenter: parent.verticalCenter
                                width: keepLabel.implicitWidth + 28 * root.s
                                height: 28 * root.s
                                radius: 9 * root.s
                                color: keepArea.containsMouse ? Theme.vermLit : Theme.verm
                                Behavior on color { ColorAnimation { duration: Motion.fast } }

                                Text {
                                    id: keepLabel
                                    anchors.centerIn: parent
                                    text: "Keep (" + root.countdown + ")"
                                    color: Theme.cream
                                    font.family: Theme.font
                                    font.pixelSize: 10.5 * root.s
                                    font.weight: Font.Bold
                                    font.letterSpacing: 0.3 * root.s
                                }

                                MouseArea {
                                    id: keepArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.keep()
                                }
                            }

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: revertLabel.implicitWidth + 24 * root.s
                                height: 28 * root.s
                                radius: 9 * root.s
                                color: revertArea.containsMouse ? Theme.frameBg : "transparent"
                                border.width: 1
                                border.color: Theme.hairSoft

                                Text {
                                    id: revertLabel
                                    anchors.centerIn: parent
                                    text: "Revert"
                                    color: Theme.subtle
                                    font.family: Theme.font
                                    font.pixelSize: 10.5 * root.s
                                    font.weight: Font.DemiBold
                                }

                                MouseArea {
                                    id: revertArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.revert()
                                }
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "reverts automatically if not kept"
                                color: Theme.faint
                                font.family: Theme.font
                                font.pixelSize: 9.5 * root.s
                                font.weight: Font.Medium
                            }
                        }
                    }
                }
            }

            Text {
                width: parent.width
                visible: card.arrangementError.length > 0
                text: card.arrangementError
                color: Theme.vermLit
                font.family: Theme.font
                font.pixelSize: 10 * root.s
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
                lineHeight: 1.25
            }

            Text {
                width: parent.width
                visible: root.note.length > 0
                text: root.note
                color: Theme.subtle
                font.family: Theme.font
                font.pixelSize: 10 * root.s
                font.weight: Font.Medium
                wrapMode: Text.WordWrap
                lineHeight: 1.25
            }
        }

        Item { width: 1; height: 4 * root.s }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.pendingToken.length > 0 || root.pendingRequestId >= 0
        z: 50
        onClicked: {}
    }
}
