pragma ComponentBehavior: Bound

import QtQuick
import "Singletons"

/** Sparrow Pill visibility and appearance preferences. */
SettingsSurface {
    id: root

    backSurface: "settings"
    property string openPicker: ""
    property bool outputsExpanded: false
    /** Empty selects the global defaults; otherwise this is a Niri output identity. */
    property string selectedOutputIdentity: ""

    readonly property var outputs: (Niri.numberedOutputs || []).filter(function (output) {
        return output && output.enabled;
    })
    readonly property var selectedOutput: root.outputByIdentity(selectedOutputIdentity)
    readonly property var outputOptions: {
        var options = [{ label: "All displays · Default", value: "" }];
        for (var i = 0; i < outputs.length; i++)
            options.push({ label: root.outputLabel(outputs[i]),
                value: String(outputs[i].identity || outputs[i].name) });
        return options;
    }
    readonly property var scalePresets: [
        { label: "90%", value: 0.9 }, { label: "100%", value: 1.0 },
        { label: "110%", value: 1.1 }, { label: "125%", value: 1.25 }
    ]
    readonly property var gapPresets: {
        var result = [];
        for (var i = 0; i <= 20; i++) {
            var value = i / 10;
            result.push({ label: value.toFixed(1) + "×", value: value });
        }
        return result;
    }
    readonly property var gapOffsetPresets: {
        var result = [{ label: "0 px", value: 0 }];
        for (var i = 4; i <= 40; i += 4)
            result.push({ label: (i > 0 ? "+" : "") + i + " px", value: i });
        return result;
    }

    implicitHeight: Math.min(content.implicitHeight + 18 * root.s, 510 * root.s)

    function outputLabel(output) {
        var number = Niri.monitorNumberForOutput(output.name);
        var label = output.label || output.name;
        return (number > 0 ? "Display " + number + " · " : "") + label;
    }

    function outputByIdentity(identity) {
        var key = String(identity || "");
        for (var i = 0; i < outputs.length; i++)
            if (String(outputs[i].identity || outputs[i].name) === key)
                return outputs[i];
        return null;
    }

    function chooseInitialOutput() {
        var requested = Flags.pillSettingsOutputIdentity;
        if (root.outputByIdentity(requested))
            root.selectedOutputIdentity = requested;
        else if (!root.outputByIdentity(root.selectedOutputIdentity))
            root.selectedOutputIdentity = "";
        Flags.pillSettingsOutputIdentity = "";
    }

    function formatSetting(key, value) {
        var n = Number(value);
        if (key === "uiScale") return Math.round(n * 100) + "%";
        if (key === "topGap") return n.toFixed(1) + "×";
        if (key === "pillGap") return (n > 0 ? "+" : "") + n.toFixed(0) + " px";
        return String(value);
    }

    function defaultValue(key) {
        return Number(Flags[key]);
    }

    function storedOutputValue(key) {
        if (!root.selectedOutput)
            return null;
        var value = Flags.pillOutputValue(root.selectedOutputIdentity, key, null);
        return value === null || value === undefined ? null : Number(value);
    }

    function settingValue(key) {
        var value = root.storedOutputValue(key);
        var resolved = value === null ? root.defaultValue(key) : value;
        if (key === "pillGap")
            return Math.max(-Flags.niriLayoutGaps, Math.min(40, resolved));
        return resolved;
    }

    function settingChoice(key) {
        return root.selectedOutput && root.storedOutputValue(key) === null
            ? "inherit" : root.settingValue(key);
    }

    function setSettingValue(key, value) {
        if (root.selectedOutput) {
            Flags.setPillOutputValue(root.selectedOutputIdentity, key,
                value === "inherit" ? null : Number(value));
            return;
        }
        if (value !== "inherit")
            Flags[key] = Number(value);
    }

    function settingOptions(key) {
        var source = key === "uiScale" ? scalePresets
            : (key === "topGap" ? gapPresets : gapOffsetPresets);
        var options = source.slice();
        if (root.selectedOutput) {
            options.unshift({ label: "Default · " + root.formatSetting(key, root.defaultValue(key)),
                value: "inherit" });
        }
        var selected = root.settingChoice(key);
        if (selected !== "inherit" && !options.some(function (option) { return option.value === selected; }))
            options.push({ label: root.formatSetting(key, selected), value: selected });
        return options;
    }

    function numericBounds(key) {
        if (key === "uiScale") return { from: 0.5, to: 2.0, decimals: 0, factor: 100, unit: "%" };
        if (key === "topGap") return { from: 0, to: 2, decimals: 1, factor: 1, unit: "×" };
        return { from: -Math.max(0, Flags.niriLayoutGaps), to: 40, decimals: 0, factor: 1, unit: " px" };
    }

    function buildRows() {
        var result = [
            { item: modeRow, kind: "seg", vals: ["all", "selected"],
                get: function () { return Flags.pillDisplayMode; },
                set: function (value) { Flags.pillDisplayMode = value; } }
        ];
        if (Flags.pillDisplayMode === "selected") {
            result.push({ item: outputSummaryRow, kind: "toggle",
                get: function () { return root.outputsExpanded; },
                set: function (value) { root.outputsExpanded = value; } });
            if (root.outputsExpanded) for (var i = 0; i < outputRepeater.count; i++) {
                let entry = outputRepeater.itemAt(i);
                if (entry && entry.rowItem)
                    result.push({ item: entry.rowItem, kind: "toggle",
                        get: function () { return entry.outputEnabled; },
                        set: function (value) { entry.setOutputEnabled(value); } });
            }
        }
        if (root.outputs.length > 0)
            result.push({ item: outputRow, kind: "seg", vals: root.outputOptions.map(function (o) { return o.value; }),
                get: function () { return root.selectedOutputIdentity; },
                set: function (v) { root.selectedOutputIdentity = v; } });
        result.push(
            { item: scaleRow, kind: "seg", vals: root.settingOptions("uiScale").map(function (o) { return o.value; }),
                get: function () { return root.settingChoice("uiScale"); },
                set: function (v) { root.setSettingValue("uiScale", v); } },
            { item: gapRow, kind: "seg", vals: root.settingOptions("topGap").map(function (o) { return o.value; }),
                get: function () { return root.settingChoice("topGap"); },
                set: function (v) { root.setSettingValue("topGap", v); } },
            { item: pillGapRow, kind: "seg", vals: root.settingOptions("pillGap").map(function (o) { return o.value; }),
                get: function () { return root.settingChoice("pillGap"); },
                set: function (v) { root.setSettingValue("pillGap", v); } }
        );
        return result;
    }

    onActiveChanged: if (active) chooseInitialOutput()
    onOutputsChanged: if (active) chooseInitialOutput()
    rows: buildRows()

    Column {
        id: content
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        SettingsHeader {
            s: root.s
            title: "PILL"
            showBack: true
        }

        Flickable {
            id: settingsFlick
            width: parent.width
            height: Math.min(body.implicitHeight, 430 * root.s)
            implicitHeight: height
            contentWidth: width
            contentHeight: body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: body
                width: parent.width
                spacing: 0

                SettingsRow {
                    id: modeRow
                    surface: root
                    icon: "monitor"
                    name: "Show on"
                    SettingsSeg {
                        s: root.s
                        options: [{ label: "All", value: "all" }, { label: "Selected", value: "selected" }]
                        value: Flags.pillDisplayMode
                        onPicked: value => Flags.pillDisplayMode = value
                    }
                }

                SettingsRow {
                    id: outputSummaryRow
                    surface: root
                    visible: Flags.pillDisplayMode === "selected"
                    icon: "monitor"
                    name: "Displays"
                    sub: root.outputs.filter(function (output) {
                        return Flags.pillOutputValue(String(output.identity || output.name), "enabled", false) === true;
                    }).length + " of " + root.outputs.length + " selected"
                    GlyphIcon {
                        width: 14 * root.s
                        height: 14 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        name: root.outputsExpanded ? "chevron-up" : "chevron-down"
                        color: Theme.iconDim
                        stroke: 2
                    }
                }

                Repeater {
                    id: outputRepeater
                    model: root.outputs

                    delegate: Item {
                        id: displayEntry
                        required property var modelData
                        property var rowItem: null
                        readonly property string outputIdentity: String(modelData.identity || modelData.name)
                        readonly property bool outputEnabled: Flags.pillOutputValue(outputIdentity, "enabled", false) === true

                        function setOutputEnabled(value) {
                            Flags.setPillOutputEnabled(outputIdentity, value);
                        }

                        width: parent.width
                        height: screenRow.visible ? screenRow.height : 0

                        SettingsRow {
                            id: screenRow
                            surface: root
                            visible: Flags.pillDisplayMode === "selected" && root.outputsExpanded
                            icon: "monitor"
                            name: root.outputLabel(displayEntry.modelData)
                            sub: displayEntry.modelData.name

                            LinkToggle {
                                s: root.s
                                on: displayEntry.outputEnabled
                                onToggled: displayEntry.setOutputEnabled(!displayEntry.outputEnabled)
                            }
                        }

                        Component.onCompleted: rowItem = screenRow
                    }
                }

                SettingsRow {
                    id: outputRow
                    surface: root
                    visible: root.outputs.length > 0
                    name: "Settings for"
                    icon: "monitor"
                    DisplayPicker {
                        width: 225 * root.s
                        s: root.s
                        label: ""
                        labelWidth: 0
                        options: root.outputOptions
                        value: root.selectedOutputIdentity
                        open: root.openPicker === "output"
                        onRequestToggle: root.openPicker = root.openPicker === "output" ? "" : "output"
                        onPicked: value => {
                            root.selectedOutputIdentity = value;
                            root.openPicker = "";
                        }
                    }
                }

                SettingsRow {
                    id: scaleRow
                    surface: root
                    name: "Pill size"
                    icon: "scaling"
                    PillValueControl {
                        id: scaleControl
                        s: root.s
                        value: root.settingValue("uiScale")
                        inherited: !!root.selectedOutput && root.storedOutputValue("uiScale") === null
                        options: root.settingOptions("uiScale")
                        open: root.openPicker === "uiScale"
                        from: root.numericBounds("uiScale").from
                        to: root.numericBounds("uiScale").to
                        decimals: root.numericBounds("uiScale").decimals
                        displayFactor: root.numericBounds("uiScale").factor
                        unit: root.numericBounds("uiScale").unit
                        onRequestToggle: root.openPicker = root.openPicker === "uiScale" ? "" : "uiScale"
                        onPicked: value => root.setSettingValue("uiScale", value)
                        onEdited: value => root.setSettingValue("uiScale", value)
                    }
                }

                SettingsRow {
                    id: gapRow
                    surface: root
                    name: "Top spacing"
                    icon: "arrow-up"
                    PillValueControl {
                        id: gapControl
                        s: root.s
                        value: root.settingValue("topGap")
                        inherited: !!root.selectedOutput && root.storedOutputValue("topGap") === null
                        options: root.settingOptions("topGap")
                        open: root.openPicker === "topGap"
                        from: root.numericBounds("topGap").from
                        to: root.numericBounds("topGap").to
                        decimals: root.numericBounds("topGap").decimals
                        displayFactor: root.numericBounds("topGap").factor
                        unit: root.numericBounds("topGap").unit
                        onRequestToggle: root.openPicker = root.openPicker === "topGap" ? "" : "topGap"
                        onPicked: value => root.setSettingValue("topGap", value)
                        onEdited: value => root.setSettingValue("topGap", value)
                    }
                }

                SettingsRow {
                    id: pillGapRow
                    surface: root
                    name: "Pill gap"
                    icon: "arrow-up"
                    PillValueControl {
                        id: pillGapControl
                        s: root.s
                        value: root.settingValue("pillGap")
                        inherited: !!root.selectedOutput && root.storedOutputValue("pillGap") === null
                        options: root.settingOptions("pillGap")
                        open: root.openPicker === "pillGap"
                        from: root.numericBounds("pillGap").from
                        to: root.numericBounds("pillGap").to
                        decimals: root.numericBounds("pillGap").decimals
                        displayFactor: root.numericBounds("pillGap").factor
                        unit: root.numericBounds("pillGap").unit
                        onRequestToggle: root.openPicker = root.openPicker === "pillGap" ? "" : "pillGap"
                        onPicked: value => root.setSettingValue("pillGap", value)
                        onEdited: value => root.setSettingValue("pillGap", value)
                    }
                }

                Text {
                    visible: root.outputs.length === 0
                    width: parent.width - 24 * root.s
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Connect a display to set per-display Pill options."
                    color: Theme.faint
                    font.family: Theme.font
                    font.pixelSize: 10.5 * root.s
                    wrapMode: Text.WordWrap
                    topPadding: 8 * root.s
                }

                Item { width: 1; height: 12 * root.s }
            }
        }
    }
}
