pragma ComponentBehavior: Bound

import QtQuick
import "Singletons"

/** Preset picker with an on-demand custom numeric editor. */
Item {
    id: root

    property real s: 1
    property var value: 1
    property var options: []
    property bool open: false
    property real from: 0
    property real to: 100
    property int decimals: 0
    property string unit: ""
    property real displayFactor: 1
    property bool inherited: false
    property bool customEditing: false
    signal picked(var value)
    signal edited(real value)
    signal requestToggle()

    width: 196 * root.s
    height: picker.implicitHeight

    readonly property var pickerOptions: root.options.concat([{ label: "Custom…", value: "__custom__" }])

    function syncDraft() {
        if (!numberInput.activeFocus)
            numberInput.text = (Number(root.value) * root.displayFactor).toFixed(root.decimals);
    }

    function beginCustomEdit() {
        root.customEditing = true;
        root.requestToggle();
        Qt.callLater(function () {
            numberInput.forceActiveFocus();
            numberInput.selectAll();
        });
    }

    function commitDraft() {
        var parsed = Number(numberInput.text.trim().replace(",", "."));
        var min = root.from * root.displayFactor;
        var max = root.to * root.displayFactor;
        if (!isFinite(parsed) || parsed < min || parsed > max) {
            root.syncDraft();
            root.customEditing = false;
            return;
        }
        root.edited(parsed / root.displayFactor);
        root.customEditing = false;
        Qt.callLater(root.syncDraft);
    }

    onValueChanged: syncDraft()
    onDisplayFactorChanged: syncDraft()
    onDecimalsChanged: syncDraft()
    Component.onCompleted: syncDraft()

    DisplayPicker {
        id: picker
        width: parent.width
        height: implicitHeight
        s: root.s
        labelWidth: 0
        label: ""
        options: root.pickerOptions
        value: root.inherited ? "inherit" : root.value
        open: root.open
        onPicked: value => {
            if (value === "__custom__") {
                root.beginCustomEdit();
                return;
            }
            root.picked(value);
        }
        onRequestToggle: root.requestToggle()
    }

    Rectangle {
        id: editor
        anchors.fill: parent
        visible: root.customEditing
        radius: 8 * root.s
        color: numberInput.activeFocus ? Theme.frameBg : "transparent"
        border.width: 1
        border.color: numberInput.activeFocus ? Qt.alpha(Theme.onGlow, 0.55) : Theme.hairSoft

        Row {
            anchors.fill: parent
            anchors.leftMargin: 8 * root.s
            anchors.rightMargin: 8 * root.s
            spacing: 3 * root.s

            TextInput {
                id: numberInput
                width: parent.width - unitText.implicitWidth - parent.spacing
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: TextInput.AlignHCenter
                verticalAlignment: TextInput.AlignVCenter
                selectByMouse: true
                inputMethodHints: Qt.ImhFormattedNumbersOnly
                color: Theme.cream
                font.family: Theme.font
                font.pixelSize: 11 * root.s
                font.weight: Font.DemiBold
                validator: DoubleValidator {
                    bottom: root.from * root.displayFactor
                    top: root.to * root.displayFactor
                    decimals: root.decimals
                    notation: DoubleValidator.StandardNotation
                }
                onEditingFinished: root.commitDraft()
                Keys.onReturnPressed: event => {
                    root.commitDraft();
                    event.accepted = true;
                }
                Keys.onEnterPressed: event => {
                    root.commitDraft();
                    event.accepted = true;
                }
                Keys.onEscapePressed: event => {
                    root.customEditing = false;
                    root.syncDraft();
                    event.accepted = true;
                }
            }

            Text {
                id: unitText
                anchors.verticalCenter: parent.verticalCenter
                text: root.unit
                color: Theme.faint
                font.family: Theme.font
                font.pixelSize: 9 * root.s
                font.weight: Font.Medium
            }
        }
    }
}
