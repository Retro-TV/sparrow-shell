pragma ComponentBehavior: Bound

import QtQuick
import "Singletons"

/**
 * One settings line: an optional leading icon, a name and optional secondary
 * status/context text on the left, and a control slot on the right, capped by a single bottom
 * hairline. `control` is the default slot for the toggle, segmented control or
 * chevron. `surface` wires hover and activation back to the owning settings
 * surface so the soul seam tracks the focused row; scale derives from it.
 */
Item {
    id: srow

    property var surface: null
    property string icon: ""
    property string name: ""
    property string sub: ""
    property bool last: false
    property bool captionOnFocus: false
    default property alias control: controlSlot.data

    readonly property real s: srow.surface ? srow.surface.s : 1
    readonly property bool focused: srow.surface ? srow.surface.focusRowItem === srow : false

    width: parent ? parent.width : 0
    height: Math.max(textCol.implicitHeight, controlSlot.childrenRect.height) + 12 * srow.s

    HoverHandler {
        id: srowHover
        onHoveredChanged: if (srow.surface) srow.surface.reportRowHover(srow, hovered)
    }

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: 3 * srow.s
        anchors.bottomMargin: 3 * srow.s
        radius: 9 * srow.s
        color: (srowHover.hovered || srow.focused) ? Theme.frameBg : "transparent"
        Behavior on color { ColorAnimation { duration: Motion.fast } }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: if (srow.surface) srow.surface.activateRow(srow)
    }

    GlyphIcon {
        id: ri
        anchors.left: parent.left
        anchors.leftMargin: 14 * srow.s
        anchors.verticalCenter: parent.verticalCenter
        visible: srow.icon.length > 0
        width: 17 * srow.s
        height: 17 * srow.s
        name: srow.icon
        color: srow.focused ? Theme.cream : Theme.subtle
        stroke: 1.8
    }

    Column {
        id: textCol
        anchors.left: ri.visible ? ri.right : parent.left
        anchors.leftMargin: ri.visible ? 13 * srow.s : 12 * srow.s
        anchors.right: controlSlot.left
        anchors.rightMargin: 14 * srow.s
        anchors.verticalCenter: parent.verticalCenter
        spacing: subtitle.visible ? 5 * srow.s : 0

        Text {
            text: srow.name
            color: Theme.cream
            font.family: Theme.font
            font.pixelSize: 12.5 * srow.s
            font.weight: Font.DemiBold
        }
        Text {
            id: subtitle
            width: parent.width
            visible: srow.sub.length > 0 && (!srow.captionOnFocus || srow.focused || srowHover.hovered)
            text: srow.sub
            color: Theme.subtle
            font.family: Theme.font
            font.pixelSize: 10.5 * srow.s
            wrapMode: Text.WordWrap
            lineHeight: 1.2
        }
    }

    Item {
        id: controlSlot
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: childrenRect.width
        height: childrenRect.height
    }

    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 1
        color: Theme.hairSoft
        visible: !srow.last
    }
}
