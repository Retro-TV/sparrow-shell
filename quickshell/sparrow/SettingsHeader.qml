import QtQuick
import "Singletons"

/**
 * Settings surface header: its uppercase title on the left, with a cog at the index or a back chevron on a
 * sub-surface at the right. The header strip is the back target, but the click is
 * handled at the pill level (a press anywhere on the top strip steps the surface
 * back), so this is a pure visual.
 */
Item {
    id: head

    property real s: 1
    property string title: ""
    property bool showBack: false

    width: parent ? parent.width : 0
    height: 22 * head.s

    Row {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: 0

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: head.title
            color: Theme.subtle
            font.family: Theme.font
            font.pixelSize: 10 * head.s
            font.weight: Font.DemiBold
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 1.6 * head.s
        }
    }

    GlyphIcon {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 16 * head.s
        height: 16 * head.s
        name: head.showBack ? "chevron-left" : "cog"
        color: Theme.iconDim
        stroke: head.showBack ? 2.2 : 1.7
    }
}
