pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import "Singletons"

/**
 * 相 APPEARANCE sub-surface: the clock format and seconds, the Japanese-glyph
 * toggle that gates every surface header, the palette mode (static flame, dynamic
 * per-wallpaper, or a manually chosen hue), the UI scale and a reduce-motion
 * switch. Reached from the settings index and morphs back to it on an empty click
 * or the back chevron.
 *
 * Manual palette mode reveals a rainbow hue strip and a dark/light choice; moving
 * either rebuilds the rice colour set from that hue through wallcolors.py --hue
 * and refreshes the shared Sparrow palette, debounced so a drag does not spawn a
 * build per pixel.
 */
SettingsSurface {
    id: root

    backSurface: "settings"
    implicitHeight: content.implicitHeight

    onActiveChanged: if (active) Cava.probe()

    property string hueArg: String(Math.round(Flags.manualHue))
    property string modeArg: Flags.manualDark ? "dark" : "light"
    property string satArg: String(Flags.manualSat)
    // Capture the selected palette style at the control boundary and pass that
    // exact value to the recolor process when the debounce fires.
    property string pendingScheme: canonicalPaletteStyle(Flags.paletteVariant)

    function canonicalPaletteStyle(value) {
        switch (String(value || "tonal").toLowerCase()) {
        case "scheme-tonal-spot":
        case "scheme-neutral":
        case "scheme-fidelity":
        case "neutral":
        case "fidelity":
        case "tonal":
            return "tonal";
        case "scheme-expressive":
        case "scheme-vibrant":
        case "expressive":
        case "vibrant":
            return "vibrant";
        case "scheme-fruit-salad":
        case "fruit":
        case "alternate":
            return "alternate";
        default:
            return "tonal";
        }
    }

    readonly property color accentColor: Qt.hsla(Flags.manualHue / 360, Flags.manualSat, Flags.manualDark ? 0.5 : 0.62, 1)
    readonly property string currentHex: {
        var c = accentColor;
        function h(x) { return ("0" + Math.round(x * 255).toString(16)).slice(-2); }
        return ("#" + h(c.r) + h(c.g) + h(c.b)).toUpperCase();
    }

    function applyManual() {
        hueArg = String(Math.round(Flags.manualHue));
        modeArg = Flags.manualDark ? "dark" : "light";
        satArg = String(Flags.manualSat);
        applyTimer.restart();
    }

    function applyPaletteStyle(variant) {
        pendingScheme = canonicalPaletteStyle(variant || Flags.paletteVariant);
        Flags.paletteVariant = pendingScheme;
        if (Flags.paletteMode === "dynamic")
            applyTimer.restart();
        else if (Flags.paletteMode === "manual")
            applyManual();
    }

    Component.onCompleted: {
        var normalized = canonicalPaletteStyle(Flags.paletteVariant);
        if (Flags.paletteVariant !== normalized) {
            Flags.paletteVariant = normalized;
            applyPaletteStyle(normalized);
        }
    }

    function applyMode(v) {
        Flags.paletteMode = v;
        if (v === "manual")
            applyManual();
        else if (v === "dynamic")
            applyPaletteStyle(Flags.paletteVariant);
    }

    Timer {
        id: applyTimer
        interval: 260
        repeat: false
        onTriggered: {
            if (Flags.paletteMode === "manual") {
                paletteProc.exec(["bash", Quickshell.shellPath("scripts/wallpaper.sh"), "manual", root.hueArg, root.modeArg, root.satArg, root.pendingScheme]);
            } else if (Flags.paletteMode === "dynamic") {
                dynamicProc.exec(["bash", Quickshell.shellPath("scripts/wallpaper.sh"), "recolor", root.pendingScheme]);
            }
        }
    }

    Process {
        id: paletteProc
        stderr: StdioCollector {
            onStreamFinished: if (this.text.trim().length > 0) console.warn(this.text.trim())
        }
    }

    Process {
        id: dynamicProc
        stderr: StdioCollector {
            onStreamFinished: if (this.text.trim().length > 0) console.warn(this.text.trim())
        }
    }

    Connections {
        target: Flags
        function onManualHueChanged() {
            if (Flags.paletteMode === "manual")
                root.applyManual();
        }
        function onManualSatChanged() {
            if (Flags.paletteMode === "manual")
                root.applyManual();
        }
    }

    Connections {
        target: Dyn
        function onPaletteStyleChanged() {
            // A wallpaper may not contain a genuinely distinct alternate hue.
            // Follow the effective generated style so the persisted selector
            // never claims to use a choice that the image cannot provide.
            if (Dyn.paletteStyle && Flags.paletteVariant !== Dyn.paletteStyle)
                Flags.paletteVariant = Dyn.paletteStyle;
        }
    }

    rows: [
        { item: timeRow, kind: "seg", vals: [false, true], get: function () { return Flags.time12h; }, set: function (v) { Flags.time12h = v; } },
        { item: secRow, kind: "toggle", get: function () { return Flags.clockSeconds; }, set: function (v) { Flags.clockSeconds = v; } },
        { item: glyphRow, kind: "toggle", get: function () { return Flags.showGlyphs; }, set: function (v) { Flags.showGlyphs = v; } },
        { item: vizRow, kind: "toggle", get: function () { return Flags.musicViz; }, set: function (v) { if (v !== Flags.musicViz) Cava.toggle(); } },
        { item: paletteRow, kind: "seg", vals: ["static", "dynamic", "manual"], get: function () { return Flags.paletteMode; }, set: function (v) { root.applyMode(v); } },
        { item: paletteStyleRow, kind: "seg", vals: Dyn.availableStyles, get: function () { return root.canonicalPaletteStyle(Flags.paletteVariant); }, set: function (v) { root.applyPaletteStyle(v); } },
        { item: randomRow, kind: "seg", vals: ["all", "cursor"], get: function () { return Flags.randomScope; }, set: function (v) { Flags.randomScope = v; } },
        { item: scaleRow, kind: "seg", vals: [0.9, 1.0, 1.1, 1.25], get: function () { return Flags.uiScale; }, set: function (v) { Flags.uiScale = v; } },
        { item: motionRow, kind: "toggle", get: function () { return Flags.reduceMotion; }, set: function (v) { Flags.reduceMotion = v; } },
        { item: fontRow, kind: "nav", surface: "fontpicker" }
    ]

    Column {
        id: content
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        SettingsHeader {
            s: root.s
            glyph: "相"
            title: "APPEARANCE"
            showBack: true
        }

        Item { width: 1; height: 12 * root.s }

        SettingsRow {
            id: timeRow
            surface: root
            name: "Time format"
            icon: "clock"

            SettingsSeg {
                s: root.s
                options: [{ label: "24H", value: false }, { label: "12H", value: true }]
                value: Flags.time12h
                onPicked: (v) => Flags.time12h = v
            }
        }

        SettingsRow {
            id: secRow
            surface: root
            name: "Clock seconds"
            icon: "stopwatch"

            LinkToggle {
                s: root.s
                on: Flags.clockSeconds
                onToggled: Flags.clockSeconds = !Flags.clockSeconds
            }
        }

        SettingsRow {
            id: glyphRow
            surface: root
            name: "Japanese glyphs"
            icon: "language"

            LinkToggle {
                s: root.s
                on: Flags.showGlyphs
                onToggled: Flags.showGlyphs = !Flags.showGlyphs
            }
        }

        SettingsRow {
            id: vizRow
            surface: root
            name: "Music visualizer"
            sub: Cava.available ? "Visualizes audio on the resting pill"
                : (Cava.checking ? "Checking for Cava…" : "Unavailable — install Cava to enable")
            icon: "music"

            LinkToggle {
                s: root.s
                on: Flags.musicViz
                onToggled: Cava.toggle()
            }
        }

        SettingsRow {
            id: paletteRow
            surface: root
            name: "Palette"
            icon: "palette"

            SettingsSeg {
                s: root.s
                options: [{ label: "Static", value: "static" }, { label: "Dynamic", value: "dynamic" }, { label: "Manual", value: "manual" }]
                value: Flags.paletteMode
                onPicked: (v) => root.applyMode(v)
            }
        }

        SettingsRow {
            id: paletteStyleRow
            surface: root
            name: "Color style"
            sub: Dyn.availableStyles.indexOf("alternate") < 0
                ? "Alternate unavailable — no distinct second color in this wallpaper"
                : "Uses colors found in the wallpaper"
            icon: "droplet"

            SettingsSeg {
                s: root.s
                options: Dyn.availableStyles.map(function (style) {
                    return { label: style === "tonal" ? "Tonal"
                        : style === "vibrant" ? "Vibrant" : "Alternate", value: style };
                })
                value: root.canonicalPaletteStyle(Flags.paletteVariant)
                onPicked: (v) => {
                    root.applyPaletteStyle(v);
                }
            }
        }

        /**
         * Manual hue editor, folded shut unless the palette is on Manual. Holds a
         * rainbow strip with a draggable thumb, then a single line pairing a live
         * accent swatch and its hex caption with the dark/light choice, and a hex
         * input that drives both hue and saturation. The strip is mouse-driven and
         * stays out of the keyboard row registry.
         */
        Item {
            id: manualSection
            width: parent.width
            height: Flags.paletteMode === "manual" ? manualCol.implicitHeight : 0
            clip: true
            Behavior on height { NumberAnimation { duration: Motion.standard; easing.type: Motion.easeStandard } }

            Column {
                id: manualCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 12 * root.s
                anchors.rightMargin: 12 * root.s
                topPadding: 4 * root.s
                bottomPadding: 16 * root.s
                spacing: 14 * root.s

                Item {
                    width: parent.width
                    height: 14 * root.s

                    Rectangle {
                        id: hueStrip
                        anchors.fill: parent
                        radius: 7 * root.s
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Qt.hsla(0.0, 0.7, 0.5, 1) }
                            GradientStop { position: 1 / 6; color: Qt.hsla(1 / 6, 0.7, 0.5, 1) }
                            GradientStop { position: 2 / 6; color: Qt.hsla(2 / 6, 0.7, 0.5, 1) }
                            GradientStop { position: 3 / 6; color: Qt.hsla(3 / 6, 0.7, 0.5, 1) }
                            GradientStop { position: 4 / 6; color: Qt.hsla(4 / 6, 0.7, 0.5, 1) }
                            GradientStop { position: 5 / 6; color: Qt.hsla(5 / 6, 0.7, 0.5, 1) }
                            GradientStop { position: 1.0; color: Qt.hsla(1.0, 0.7, 0.5, 1) }
                        }

                        Rectangle {
                            id: hueThumb
                            width: 16 * root.s
                            height: 16 * root.s
                            radius: width / 2
                            anchors.verticalCenter: parent.verticalCenter
                            x: (Flags.manualHue / 359) * (hueStrip.width - width)
                            color: root.accentColor
                            border.width: 2.5 * root.s
                            border.color: Theme.cream
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            function setHue(mx) {
                                if (Flags.manualSat < 0.05)
                                    Flags.manualSat = 0.5;
                                Flags.manualHue = Math.round(Math.max(0, Math.min(1, mx / hueStrip.width)) * 359);
                            }
                            onPressed: (mouse) => setHue(mouse.x)
                            onPositionChanged: (mouse) => setHue(mouse.x)
                        }
                    }
                }

                Item {
                    width: parent.width
                    height: Math.max(34 * root.s, toneSeg.implicitHeight)

                    Rectangle {
                        id: accentSwatch
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: 34 * root.s
                        height: 34 * root.s
                        radius: 9 * root.s
                        color: root.accentColor
                        border.width: 1
                        border.color: Theme.border
                    }

                    Column {
                        anchors.left: accentSwatch.right
                        anchors.leftMargin: 12 * root.s
                        anchors.right: toneSeg.left
                        anchors.rightMargin: 12 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 3 * root.s

                        Text {
                            text: "Accent hue"
                            color: Theme.cream
                            font.family: Theme.font
                            font.pixelSize: 12 * root.s
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: root.currentHex + " · " + (Flags.manualDark ? "dark" : "light")
                            color: Theme.faint
                            font.family: Theme.font
                            font.pixelSize: 10.5 * root.s
                            font.features: { "tnum": 1 }
                            elide: Text.ElideRight
                            width: parent.width
                        }
                    }

                    SettingsSeg {
                        id: toneSeg
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        s: root.s
                        options: [{ label: "Dark", value: true }, { label: "Light", value: false }]
                        value: Flags.manualDark
                        onPicked: (v) => { Flags.manualDark = v; root.applyManual(); }
                    }
                }

                Item {
                    width: parent.width
                    height: 30 * root.s

                    Text {
                        id: hexHint
                        anchors.left: parent.left
                        anchors.leftMargin: 12 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        text: "#"
                        color: Theme.faint
                        font.family: Theme.font
                        font.pixelSize: 14 * root.s
                        font.weight: Font.DemiBold
                    }

                    TextField {
                        id: hexField
                        anchors.left: hexHint.right
                        anchors.leftMargin: 6 * root.s
                        anchors.right: parent.right
                        anchors.rightMargin: 12 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        background: null
                        padding: 0
                        color: Theme.cream
                        font.family: Theme.font
                        font.pixelSize: 13 * root.s
                        font.features: { "tnum": 1 }
                        placeholderText: root.currentHex
                        placeholderTextColor: Theme.faint
                        selectByMouse: true
                        selectionColor: Theme.verm
                        maximumLength: 7

                        onActiveFocusChanged: if (!activeFocus) text = "";

                        function commit() {
                            var raw = text.trim();
                            var clean = raw.charAt(0) === "#" ? raw.slice(1) : raw;
                            if (/^[0-9a-fA-F]{6}$/.test(clean)) {
                                var c = Qt.color("#" + clean);
                                if (c.hslHue >= 0) {
                                    Flags.manualHue = Math.round(c.hslHue * 359);
                                    Flags.manualSat = c.hslSaturation;
                                } else {
                                    Flags.manualSat = 0;
                                }
                                root.applyManual();
                            }
                            text = "";
                            focus = false;
                        }

                        onAccepted: commit()
                        onEditingFinished: commit()
                    }

                    Rectangle {
                        anchors.left: hexField.left
                        anchors.right: hexField.right
                        anchors.top: hexField.bottom
                        anchors.topMargin: 3 * root.s
                        height: 1
                        color: Theme.faint
                        opacity: hexField.activeFocus ? 0.7 : 0.18
                        Behavior on opacity { NumberAnimation { duration: Motion.standard; easing.type: Motion.easeStandard } }
                    }
                }
            }
        }

        SettingsRow {
            id: randomRow
            surface: root
            name: "Random wallpaper"
            icon: "monitor"

            SettingsSeg {
                s: root.s
                options: [{ label: "All screens", value: "all" }, { label: "Cursor screen", value: "cursor" }]
                value: Flags.randomScope
                onPicked: (v) => Flags.randomScope = v
            }
        }

        SettingsRow {
            id: scaleRow
            surface: root
            name: "UI scale"
            icon: "scaling"

            SettingsSeg {
                s: root.s
                options: [{ label: "90%", value: 0.9 }, { label: "100%", value: 1.0 }, { label: "110%", value: 1.1 }, { label: "125%", value: 1.25 }]
                value: Flags.uiScale
                onPicked: (v) => Flags.uiScale = v
            }
        }

        SettingsRow {
            id: motionRow
            surface: root
            name: "Reduce motion"
            icon: "waves"

            LinkToggle {
                s: root.s
                on: Flags.reduceMotion
                onToggled: Flags.reduceMotion = !Flags.reduceMotion
            }
        }

        SettingsRow {
            id: fontRow
            surface: root
            name: "Font"
            icon: "type"
            sub: Flags.uiFont.length > 0 ? Flags.uiFont : "Inter"
            last: true

            GlyphIcon {
                width: 16 * root.s
                height: 16 * root.s
                name: "chevron-right"
                color: root.focusRowItem === fontRow ? Theme.cream : Theme.iconDim
                stroke: 1.9
            }
        }
    }
}
