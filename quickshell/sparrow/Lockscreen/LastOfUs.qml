pragma ComponentBehavior: Bound

import QtQuick
import Qt5Compat.GraphicalEffects
import QtMultimedia

/*
 * Adapted from the “Last of Us” theme by Darkkal44 in qylock.
 * Original: https://github.com/Darkkal44/qylock/tree/main/themes/last-of-us
 * The original screen composition is retained; only its SDDM-specific account,
 * session and authentication integration is replaced with Sparrow signals.
 */
Item {
    id: root

    property string wallpaperPath: ""
    property string username: ""
    property string prompt: "ENTER ACCESS KEY"
    property bool promptIsError: false
    property string foregroundMode: "auto"
    property string recommendedForeground: "light"
    property color paletteDark: "#191c1d"
    property color paletteMuted: "#505354"
    property color paletteAccent: "#444748"
    property color paletteError: "#ffb4ab"
    signal authenticate(string password)
    signal powerAction(string action)

    readonly property real s: height / 1080
    readonly property bool darkForegroundSelected: foregroundMode === "dark"
        || (foregroundMode === "auto" && recommendedForeground === "dark")
    readonly property color textPrimary: darkForegroundSelected ? paletteDark : "#fffdf5"
    readonly property color textSecondary: darkForegroundSelected ? paletteMuted : "#a89e8d"
    readonly property color accent: darkForegroundSelected ? paletteAccent : "#f7c594"
    readonly property color errorColor: darkForegroundSelected ? Qt.darker(paletteError, 1.8) : "#f06060"
    readonly property bool videoWallpaper: /\.(mp4|webm|mkv|mov)$/i.test(wallpaperPath)
    readonly property bool gifWallpaper: /\.gif$/i.test(wallpaperPath)

    FontLoader {
        id: mainFont
        source: Qt.resolvedUrl("font/Outfit-Black.ttf")
    }

    MediaPlayer {
        id: wallpaperPlayer
        source: root.videoWallpaper ? "file://" + root.wallpaperPath : ""
        loops: MediaPlayer.Infinite
        videoOutput: wallpaperVideo
        audioOutput: AudioOutput { volume: 0 }
        onMediaStatusChanged: if (mediaStatus === MediaPlayer.LoadedMedia) play()
    }

    VideoOutput {
        id: wallpaperVideo
        anchors.fill: parent
        fillMode: VideoOutput.PreserveAspectCrop
        visible: root.videoWallpaper
    }

    Image {
        anchors.fill: parent
        source: root.videoWallpaper || root.gifWallpaper ? "" : "file://" + root.wallpaperPath
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        visible: !root.videoWallpaper && !root.gifWallpaper
    }

    AnimatedImage {
        anchors.fill: parent
        source: root.gifWallpaper ? "file://" + root.wallpaperPath : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        playing: root.gifWallpaper
        visible: root.gifWallpaper
    }

    Rectangle {
        anchors.fill: parent
        z: 1
        color: "#0a0a09"
        visible: root.wallpaperPath.length === 0
    }

    Rectangle {
        anchors.fill: parent
        z: 2
        opacity: 0.18
        gradient: Gradient {
            GradientStop { position: 0; color: "transparent" }
            GradientStop { position: 1; color: "#33f7c594" }
        }
    }

    Repeater {
        model: 24
        delegate: Item {
            id: mote
            property real sx: Math.random() * root.width * 0.7 + root.width * 0.1
            property real sy: Math.random() * root.height
            property real drift: (Math.random() - 0.5) * 40 * root.s
            property real duration: 14000 + Math.random() * 16000
            property real size: (1.5 + Math.random() * 2.5) * root.s
            x: sx
            y: sy
            width: size
            height: size
            opacity: 0
            z: 3
            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: "#fff0d4"
                opacity: 0.12
            }
            SequentialAnimation {
                running: true
                loops: Animation.Infinite
                ParallelAnimation {
                    NumberAnimation { target: mote; property: "y"; to: mote.sy - 100 * root.s; duration: mote.duration; easing.type: Easing.InOutSine }
                    NumberAnimation { target: mote; property: "x"; to: mote.sx + mote.drift; duration: mote.duration; easing.type: Easing.InOutSine }
                    SequentialAnimation {
                        NumberAnimation { target: mote; property: "opacity"; to: 0.4; duration: mote.duration * 0.4 }
                        NumberAnimation { target: mote; property: "opacity"; to: 0; duration: mote.duration * 0.6 }
                    }
                }
            }
        }
    }

    Item {
        id: ui
        anchors.fill: parent
        z: 4
        readonly property real leftPadding: 160 * root.s

        Column {
            anchors.left: parent.left
            anchors.leftMargin: ui.leftPadding
            anchors.top: parent.top
            anchors.topMargin: 150 * root.s
            spacing: 2 * root.s

            Text {
                id: clockText
                text: Qt.formatTime(new Date(), "HH:mm")
                font.family: mainFont.name
                font.pixelSize: 104 * root.s
                font.weight: Font.DemiBold
                color: root.textPrimary
                opacity: 0.95
                layer.enabled: true
                layer.effect: DropShadow {
                    color: "#aa000000"
                    radius: 10
                    samples: 24
                    verticalOffset: 6
                }
                Timer {
                    interval: 1000
                    running: true
                    repeat: true
                    onTriggered: clockText.text = Qt.formatTime(new Date(), "HH:mm")
                }
                SequentialAnimation {
                    running: true
                    loops: Animation.Infinite
                    NumberAnimation { target: clockText; property: "opacity"; from: 0.95; to: 0.88; duration: 5000; easing.type: Easing.InOutSine }
                    NumberAnimation { target: clockText; property: "opacity"; from: 0.88; to: 0.95; duration: 5000; easing.type: Easing.InOutSine }
                }
            }
            Text {
                text: Qt.formatDate(new Date(), "dddd / MMMM d").toUpperCase()
                font.family: mainFont.name
                font.pixelSize: 14 * root.s
                font.letterSpacing: 8 * root.s
                color: root.textSecondary
                anchors.left: parent.left
                anchors.leftMargin: 6 * root.s
                Timer {
                    interval: 60000
                    running: true
                    repeat: true
                    onTriggered: parent.text = Qt.formatDate(new Date(), "dddd / MMMM d").toUpperCase()
                }
            }
        }

        Item {
            id: login
            anchors.left: parent.left
            anchors.leftMargin: ui.leftPadding
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: 120 * root.s
            width: 380 * root.s
            height: loginContent.implicitHeight

            Column {
                id: loginContent
                anchors.fill: parent
                spacing: 40 * root.s
                Column {
                    spacing: 4 * root.s
                    width: parent.width
                    Text {
                        text: "CURRENT OPERATIVE"
                        font.family: mainFont.name
                        font.pixelSize: 10 * root.s
                        font.letterSpacing: 2 * root.s
                        color: root.textSecondary
                        opacity: root.darkForegroundSelected ? 0.82 : 0.55
                    }
                    Text {
                        text: root.username.toUpperCase()
                        font.family: mainFont.name
                        font.pixelSize: 40 * root.s
                        font.weight: Font.Bold
                        font.letterSpacing: 1 * root.s
                        color: userMouse.containsMouse ? root.accent : root.textPrimary
                        Behavior on color { ColorAnimation { duration: 300 } }
                        MouseArea {
                            id: userMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                        }
                    }
                }

                Item {
                    width: parent.width
                    height: 50 * root.s
                    Rectangle {
                        anchors.fill: parent
                        color: Qt.rgba(1, 1, 1, 0.03)
                        radius: 4 * root.s
                        border.color: password.activeFocus
                            ? (root.darkForegroundSelected ? Qt.alpha(root.accent, 0.42) : Qt.rgba(0.97, 0.77, 0.58, 0.25))
                            : (root.darkForegroundSelected ? Qt.alpha(root.textPrimary, 0.14) : Qt.rgba(1, 1, 1, 0.05))
                        border.width: 1
                    }
                    TextInput {
                        id: password
                        anchors.fill: parent
                        anchors.leftMargin: 15 * root.s
                        anchors.rightMargin: 80 * root.s
                        verticalAlignment: TextInput.AlignVCenter
                        echoMode: TextInput.Password
                        passwordCharacter: "·"
                        font.family: mainFont.name
                        font.pixelSize: 22 * root.s
                        font.letterSpacing: 10 * root.s
                        color: root.textPrimary
                        clip: true
                        focus: true
                        cursorVisible: false
                        cursorDelegate: Item { width: 0; height: 0 }
                        onAccepted: submit()
                        onTextEdited: root.promptIsError = false
                        function submit() {
                            if (text.length === 0)
                                return;
                            const candidate = text;
                            clear();
                            root.authenticate(candidate);
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.prompt
                            font.family: mainFont.name
                            font.pixelSize: 12 * root.s
                            font.letterSpacing: 4 * root.s
                            color: root.promptIsError ? root.errorColor : root.textSecondary
                            opacity: password.text.length === 0
                                ? (root.darkForegroundSelected ? 0.9 : 0.55) : 0
                            Behavior on opacity { NumberAnimation { duration: 300 } }
                        }
                        Rectangle {
                            id: cursorDot
                            width: 8 * root.s
                            height: width
                            radius: width / 2
                            color: root.accent
                            anchors.verticalCenter: parent.verticalCenter
                            x: Math.max(0, password.cursorRectangle.x)
                            visible: password.activeFocus && password.text.length > 0
                            layer.enabled: true
                            layer.effect: DropShadow {
                                color: root.accent
                                radius: 8
                                samples: 16
                            }
                            SequentialAnimation on opacity {
                                running: cursorDot.visible
                                loops: Animation.Infinite
                                NumberAnimation { from: 1; to: 0.15; duration: 700; easing.type: Easing.InOutSine }
                                NumberAnimation { from: 0.15; to: 1; duration: 700; easing.type: Easing.InOutSine }
                            }
                        }
                    }
                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 15 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        text: "GO"
                        font.family: mainFont.name
                        font.pixelSize: 11 * root.s
                        font.letterSpacing: 3 * root.s
                        font.weight: Font.Bold
                        color: goMouse.containsMouse ? root.accent : root.textPrimary
                        opacity: password.text.length > 0 ? 0.8 : 0
                        MouseArea {
                            id: goMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: password.submit()
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: password.text.length === 0
                        onClicked: password.forceActiveFocus()
                    }
                }

                Text {
                    width: parent.width
                    height: 15 * root.s
                    verticalAlignment: Text.AlignBottom
                    text: root.promptIsError ? root.prompt.toUpperCase() : ""
                    color: root.errorColor
                    font.family: mainFont.name
                    font.pixelSize: 12 * root.s
                    font.letterSpacing: 2 * root.s
                }
            }
            SequentialAnimation {
                id: errorShake
                running: root.promptIsError
                NumberAnimation { target: login; property: "x"; to: ui.leftPadding + 15 * root.s; duration: 45 }
                NumberAnimation { target: login; property: "x"; to: ui.leftPadding - 15 * root.s; duration: 45 }
                NumberAnimation { target: login; property: "x"; to: ui.leftPadding + 10 * root.s; duration: 45 }
                NumberAnimation { target: login; property: "x"; to: ui.leftPadding - 10 * root.s; duration: 45 }
                NumberAnimation { target: login; property: "x"; to: ui.leftPadding; duration: 45 }
            }
        }

        Row {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 140 * root.s
            anchors.left: parent.left
            anchors.leftMargin: ui.leftPadding
            spacing: 60 * root.s
            Repeater {
                model: [ { label: "SHUTDOWN", action: "power-off" }, { label: "REBOOT", action: "reboot" } ]
                delegate: Text {
                    id: powerDelegate
                    required property var modelData
                    text: powerDelegate.modelData.label
                    font.family: mainFont.name
                    font.pixelSize: 14 * root.s
                    font.letterSpacing: 2 * root.s
                    color: powerMouse.containsMouse ? root.accent : root.textSecondary
                    Behavior on color { ColorAnimation { duration: 250 } }
                    MouseArea {
                        id: powerMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.powerAction(powerDelegate.modelData.action)
                    }
                }
            }
        }
    }

    Timer {
        interval: 300
        running: true
        onTriggered: root.focusPassword()
    }

    function focusPassword() { password.forceActiveFocus(); }
}
