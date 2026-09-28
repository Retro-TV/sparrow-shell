pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import "Singletons"

/** Sparrow's clock, palette source, dynamic palette and UI preferences. */
SettingsSurface {
    id: root

    backSurface: "settings"
    implicitHeight: content.implicitHeight

    onActiveChanged: if (active) Cava.probe()

    function canonicalPaletteStyle(value) {
        switch (String(value || "auto").toLowerCase()) {
        case "auto":
        case "scheme-smart":
            return "auto";
        case "content":
        case "scheme-content":
        case "source":
        case "vibrant":
            return "content";
        case "monochrome":
        case "scheme-monochrome":
        case "mono":
            return "monochrome";
        case "scheme-tonal-spot":
        case "scheme-neutral":
        case "scheme-fidelity":
        case "neutral":
        case "fidelity":
        case "tonal":
            return "tonal";
        case "scheme-expressive":
        case "expressive":
        case "scheme-fruit-salad":
        case "fruit":
        case "alternate":
            return "auto";
        default:
            return "auto";
        }
    }

    function applyPaletteStyle(variant) {
        Flags.paletteVariant = canonicalPaletteStyle(variant || Flags.paletteVariant);
        if (Flags.paletteMode === "dynamic")
            applyTimer.restart();
    }

    function buildRows() {
        var result = [
            { item: timeRow, kind: "seg", vals: [false, true], get: function () { return Flags.time12h; }, set: function (v) { Flags.time12h = v; } },
            { item: secRow, kind: "toggle", get: function () { return Flags.clockSeconds; }, set: function (v) { Flags.clockSeconds = v; } },
            { item: vizRow, kind: "toggle", get: function () { return Flags.musicViz; }, set: function (v) { if (v !== Flags.musicViz) Cava.toggle(); } },
            { item: paletteRow, kind: "seg", vals: ["static", "dynamic"], get: function () { return Flags.paletteMode; }, set: function (v) { root.applyPaletteSource(v); } }
        ];
        if (Flags.paletteMode === "dynamic") {
            result.push(
                { item: paletteStyleRow, kind: "seg", vals: ["auto", "tonal", "content", "monochrome"], get: function () { return root.canonicalPaletteStyle(Flags.paletteVariant); }, set: function (v) { root.applyPaletteStyle(v); } },
                { item: colorModeRow, kind: "seg", vals: ["auto", "dark", "light"], get: function () { return Flags.appearanceMode; }, set: function (v) { root.applyAppearanceMode(v); } }
            );
        }
        result.push(
            { item: lockTextRow, kind: "seg", vals: ["auto", "light", "dark"], get: function () { return Flags.lockForegroundMode; }, set: function (v) { Flags.lockForegroundMode = v; } },
            { item: randomRow, kind: "seg", vals: ["all", "cursor"], get: function () { return Flags.randomScope; }, set: function (v) { Flags.randomScope = v; } },
            { item: scaleRow, kind: "seg", vals: [0.9, 1.0, 1.1, 1.25], get: function () { return Flags.uiScale; }, set: function (v) { Flags.uiScale = v; } },
            { item: motionRow, kind: "toggle", get: function () { return Flags.reduceMotion; }, set: function (v) { Flags.reduceMotion = v; } },
            { item: fontRow, kind: "nav", surface: "fontpicker" }
        );
        return result;
    }

    function applyPaletteSource(v) {
        Flags.paletteMode = v;
        applyTimer.restart();
    }

    function applyAppearanceMode(v) {
        Flags.appearanceMode = v;
        applyTimer.restart();
    }

    rows: buildRows()

    Timer {
        id: applyTimer
        interval: 260
        repeat: false
        onTriggered: {
            dynamicProc.exec(["bash", Quickshell.shellPath("scripts/wallpaper.sh"), "recolor"]);
        }
    }

    Process {
        id: dynamicProc
        stderr: StdioCollector {
            onStreamFinished: if (this.text.trim().length > 0) console.warn(this.text.trim())
        }
    }

    Column {
        id: content
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        SettingsHeader {
            s: root.s
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
            id: vizRow
            surface: root
            name: "Music visualizer"
            sub: Cava.available || Cava.checking ? "" : "Cava unavailable"
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
            name: "Colors"
            icon: "palette"

            SettingsSeg {
                s: root.s
                options: [{ label: "Static", value: "static" }, { label: "Dynamic", value: "dynamic" }]
                value: Flags.paletteMode
                onPicked: (v) => root.applyPaletteSource(v)
            }
        }

        SettingsRow {
            id: paletteStyleRow
            surface: root
            visible: Flags.paletteMode === "dynamic"
            name: "Palette"
            icon: "droplet"

            SettingsSeg {
                s: root.s
                options: [
                    { label: "Auto", value: "auto" }, { label: "Tonal", value: "tonal" },
                    { label: "Source", value: "content" }, { label: "Mono", value: "monochrome" }
                ]
                value: root.canonicalPaletteStyle(Flags.paletteVariant)
                onPicked: (v) => root.applyPaletteStyle(v)
            }
        }

        SettingsRow {
            id: colorModeRow
            surface: root
            visible: Flags.paletteMode === "dynamic"
            name: "Mode"
            icon: "sun"

            SettingsSeg {
                s: root.s
                options: [{ label: "Auto", value: "auto" }, { label: "Dark", value: "dark" }, { label: "Light", value: "light" }]
                value: Flags.appearanceMode
                onPicked: (v) => root.applyAppearanceMode(v)
            }
        }

        SettingsRow {
            id: lockTextRow
            surface: root
            name: "Lockscreen text"
            icon: "type"

            SettingsSeg {
                s: root.s
                options: [{ label: "Auto", value: "auto" }, { label: "Light", value: "light" }, { label: "Dark", value: "dark" }]
                value: Flags.lockForegroundMode
                onPicked: (v) => Flags.lockForegroundMode = v
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
