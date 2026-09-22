pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "Singletons"
import "../Singletons" as SparrowBackend

ShellRoot {
    id: root

    readonly property string currentUser: Quickshell.env("USER") || Quickshell.env("LOGNAME") || ""

    /** Drives the preserved Ricelin reveal animation after the secure lock is granted. */
    property bool revealed: false
    property string pendingSecureAction: ""

    Auth {
        id: pamAuth
        user: root.currentUser
        onSucceeded: {
            root.revealed = false;
            collapse.restart();
        }
    }

    Timer {
        id: collapse
        interval: 640
        onTriggered: {
            sessionLock.locked = false;
            Cava.enabled = false;
            exitAfterUnlock.restart();
        }
    }

    Timer {
        id: exitAfterUnlock
        interval: 300
        onTriggered: Qt.quit()
    }

    /** Fires as soon as the event loop frees after the lock surfaces are built, which is the earliest the grow can start without the fresh output dropping its first frames. */
    Timer {
        id: reveal
        interval: 1
        onTriggered: root.revealed = true
    }

    function requestLock(action: string): void {
        if (sessionLock.locked) {
            if (action.length > 0) {
                root.pendingSecureAction = action;
                if (sessionLock.secure)
                    root.runPendingSecureAction();
            }
            return;
        }

        root.pendingSecureAction = action;
        root.revealed = false;
        sessionLock.locked = true;
        secureDeadline.restart();
        Cava.enabled = true;
        reveal.restart();
    }

    function runPendingSecureAction(): void {
        if (!sessionLock.secure || root.pendingSecureAction.length === 0)
            return;

        var action = root.pendingSecureAction;
        root.pendingSecureAction = "";
        if (action === "power-off")
            SparrowBackend.Niri.powerOffOutputs();
        else if (action === "suspend")
            suspendProc.running = true;
    }

    Connections {
        target: sessionLock
        function onSecureChanged() {
            if (sessionLock.secure) {
                console.info("Sparrow lock: compositor confirmed secure session lock on all outputs");
                root.runPendingSecureAction();
            }
        }
    }

    Timer {
        id: secureDeadline
        interval: 5000
        onTriggered: {
            if (sessionLock.locked && !sessionLock.secure)
                console.error("Sparrow lock: secure session lock was not confirmed; refusing power action");
        }
    }

    Process {
        id: suspendProc
        command: ["systemctl", "suspend"]
        onStarted: console.info("Sparrow lock: suspend started after secure lock confirmation")
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                console.error("Sparrow lock: suspend request failed with exit code", exitCode);
        }
    }

    WlSessionLock {
        id: sessionLock
        locked: false

        WlSessionLockSurface {
            id: lockSurface
            color: "#160f0a"

            LockSurface {
                anchors.fill: parent
                s: lockSurface.screen ? lockSurface.screen.height / 1080 : 1
                screenName: lockSurface.screen ? lockSurface.screen.name : ""
                auth: pamAuth
                active: root.revealed
            }
        }

        onSecureChanged: {
            if (secure)
                secureDeadline.stop();
            else if (locked)
                secureDeadline.restart();
        }
    }

    IpcHandler {
        target: "lock"
        function lock(): void {
            root.requestLock("");
        }
        function powerOff(): void { root.requestLock("power-off"); }
        function suspend(): void { root.requestLock("suspend"); }
    }
}
