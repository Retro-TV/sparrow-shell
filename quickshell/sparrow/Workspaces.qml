pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "Singletons"

/**
 * Workspace dots for one Niri output.
 *
 * Keeps Ricelin's original workspace visuals and animations while sourcing
 * workspace state from Sparrow's Niri singleton.
 *
 * Niri workspace IDs are stable identities. Workspace idx values are only
 * their current positions on an output and may change as dynamic workspaces
 * are created and removed.
 */
Item {
    id: workspaces

    property string screenName: ""
    property real s: 1
    property real stickW: 17 * s
    property real dotW: 5 * s
    property real gap: 4 * s

    /*
     * Force reevaluation when Niri replaces its workspace array.
     *
     * We keep the complete workspace objects here rather than just idx values,
     * because actions should use the workspace's current idx while identity
     * remains tied to its stable id.
     */
    readonly property var range: {
        void Niri.workspaces;
        return Niri.workspacesForOutput(screenName);
    }

    readonly property int activeWorkspaceId: {
        void Niri.workspaces;

        var ws = Niri.activeWorkspaceForOutput(screenName);
        return ws ? ws.id : -1;
    }

    property int hoverIndex: -1

    readonly property int activeIndex: {
        for (var i = 0; i < range.length; i++) {
            if (range[i].id === activeWorkspaceId)
                return i;
        }

        return -1;
    }

    /**
     * Centre x of a dot slot from target layout widths.
     * This is unchanged in spirit from Ricelin: the active workspace becomes
     * the wider stick while inactive workspaces remain dots.
     */
    function slotCenterX(idx) {
        let x = 0;

        for (let i = 0; i < idx; i++)
            x += (i === activeIndex ? stickW : dotW) + gap;

        return x + (idx === activeIndex ? stickW : dotW) / 2;
    }

    readonly property point activeDotPoint: {
        void workspaces.activeWorkspaceId;
        void workspaces.width;

        return Qt.point(
            slotCenterX(Math.max(0, activeIndex)),
            height / 2
        );
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight

    RowLayout {
        id: row

        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: workspaces.gap

        Repeater {
            model: workspaces.range

            delegate: Item {
                id: slot

                required property var modelData
                required property int index

                readonly property int wsId: modelData.id
                readonly property int wsIdx: modelData.idx
                readonly property bool isActive:
                    workspaces.activeWorkspaceId === wsId

                Layout.preferredWidth:
                    slot.isActive ? workspaces.stickW : workspaces.dotW

                Layout.preferredHeight: 22 * workspaces.s

                Behavior on Layout.preferredWidth {
                    NumberAnimation {
                        duration: Motion.fast
                        easing.type: Motion.easeStandard
                    }
                }

                Rectangle {
                    anchors.centerIn: parent

                    width: parent.width
                    height: workspaces.dotW
                    radius: height / 2

                    color:
                        slot.isActive ? Theme.vermLit : Theme.cream

                    opacity:
                        slot.isActive
                            ? 1.0
                            : (area.containsMouse ? 0.7 : 0.3)

                    Behavior on opacity {
                        NumberAnimation {
                            duration: Motion.fast
                        }
                    }
                }

                MouseArea {
                    id: area

                    anchors.fill: parent
                    anchors.leftMargin: -workspaces.gap / 2
                    anchors.rightMargin: -workspaces.gap / 2
                    anchors.topMargin: -8 * workspaces.s
                    anchors.bottomMargin: -8 * workspaces.s

                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor

                    onClicked:
                        Niri.focusWorkspace(slot.wsId)

                    onContainsMouseChanged: {
                        if (containsMouse)
                            workspaces.hoverIndex = slot.index;
                        else if (workspaces.hoverIndex === slot.index)
                            workspaces.hoverIndex = -1;
                    }
                }
            }
        }
    }
}
