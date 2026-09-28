pragma ComponentBehavior: Bound

import QtQuick
import "Singletons"

/**
 * IDLE / LOCK sub-surface: timeout values are watched by Sparrow's separate
 * Quickshell IdleMonitor service. The service reads the shared flags directly;
 * settings changes therefore apply live without generating a daemon config or
 * restarting the pill. Reached from settings and morphs back on an empty click
 * or the back chevron.
 */
SettingsSurface {
    id: root

    backSurface: "settings"
    implicitHeight: content.implicitHeight

    readonly property var lockOptions: [
        { label: "Off", value: 0 }, { label: "1 min", value: 1 }, { label: "3 min", value: 3 },
        { label: "5 min", value: 5 }, { label: "10 min", value: 10 }, { label: "15 min", value: 15 }
    ]
    readonly property var screenOptions: [
        { label: "Off", value: 0 }, { label: "3 min", value: 3 }, { label: "5 min", value: 5 },
        { label: "10 min", value: 10 }, { label: "15 min", value: 15 }
    ]
    readonly property var suspendOptions: [
        { label: "Off", value: 0 }, { label: "15 min", value: 15 },
        { label: "30 min", value: 30 }, { label: "60 min", value: 60 }
    ]

    rows: [
        { item: lockRow, kind: "seg", vals: root.lockOptions.map(function (o) { return o.value; }), get: function () { return Flags.idleLockMin; }, set: function (v) { Flags.idleLockMin = v; } },
        { item: screenRow, kind: "seg", vals: root.screenOptions.map(function (o) { return o.value; }), get: function () { return Flags.idleScreenOffMin; }, set: function (v) { Flags.idleScreenOffMin = v; } },
        { item: suspendRow, kind: "seg", vals: root.suspendOptions.map(function (o) { return o.value; }), get: function () { return Flags.idleSuspendMin; }, set: function (v) { Flags.idleSuspendMin = v; } }
    ]

    /**
     * One idle row: a name above its segmented control, so a six-option strip
     * keeps its full width. Hover lights the row and feeds the soul seam,
     * matching the rest of the settings rows.
     */
    component IdleRow: Item {
        id: irow
        property string name: ""
        property bool last: false
        default property alias seg: segSlot.data
        readonly property real s: root.s

        width: parent ? parent.width : 0
        height: col.implicitHeight + 22 * irow.s

        HoverHandler {
            id: ih
            onHoveredChanged: root.reportRowHover(irow, hovered)
        }

        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 3 * irow.s
            anchors.bottomMargin: 3 * irow.s
            radius: 9 * irow.s
            color: (ih.hovered || root.focusRowItem === irow) ? Theme.frameBg : "transparent"
            Behavior on color { ColorAnimation { duration: Motion.fast } }
        }

        Column {
            id: col
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 12 * irow.s
            anchors.rightMargin: 12 * irow.s
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3 * irow.s

            Text {
                text: irow.name
                color: Theme.cream
                font.family: Theme.font
                font.pixelSize: 12.5 * irow.s
                font.weight: Font.DemiBold
            }
            Item { width: 1; height: 7 * irow.s }
            Item {
                id: segSlot
                width: childrenRect.width
                height: childrenRect.height
            }
        }

        Rectangle {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 1
            color: Theme.hairSoft
            visible: !irow.last
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
            title: "IDLE / LOCK"
            showBack: true
        }

        Item { width: 1; height: 12 * root.s }

        IdleRow {
            id: lockRow
            name: "Auto-lock"

            SettingsSeg {
                s: root.s
                flushLeft: true
                options: root.lockOptions
                value: Flags.idleLockMin
                onPicked: (v) => { Flags.idleLockMin = v; }
            }
        }

        IdleRow {
            id: screenRow
            name: "Screen off"

            SettingsSeg {
                s: root.s
                flushLeft: true
                options: root.screenOptions
                value: Flags.idleScreenOffMin
                onPicked: (v) => { Flags.idleScreenOffMin = v; }
            }
        }

        IdleRow {
            id: suspendRow
            name: "Suspend"
            last: true

            SettingsSeg {
                s: root.s
                flushLeft: true
                options: root.suspendOptions
                value: Flags.idleSuspendMin
                onPicked: (v) => { Flags.idleSuspendMin = v; }
            }
        }

        Text {
            topPadding: 12 * root.s
            leftPadding: 12 * root.s
            rightPadding: 12 * root.s
            width: parent.width
            text: "Keep-awake (in the mixer) pauses all of this while it is on."
            color: Theme.subtle
            font.family: Theme.font
            font.pixelSize: 9.5 * root.s
            font.weight: Font.Medium
            wrapMode: Text.WordWrap
        }

        Item { width: 1; height: 10 * root.s }
    }
}
