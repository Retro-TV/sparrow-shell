pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pam
import Quickshell.Wayland
import "../Lockscreen"
import "."

/**
 * Sparrow's compositor-enforced lock. WlSessionLock uses ext-session-lock-v1;
 * the compositor keeps the session locked if this shell crashes. PAM is the
 * only path that can release the lock.
 */
Singleton {
    id: root

    property string pendingPassword: ""
    property string prompt: "ENTER ACCESS KEY"
    property bool promptIsError: false
    property string pendingAction: ""
    readonly property string username: Quickshell.env("USER") || "User"

    function initialize(): void {
        // Accessing this method eagerly instantiates the singleton and registers
        // its IPC handler before Niri or the idle monitor requests a lock.
    }

    function requestLock(action: string): void {
        pendingAction = action;
        pendingPassword = "";
        prompt = "ENTER ACCESS KEY";
        promptIsError = false;

        if (sessionLock.locked) {
            if (sessionLock.secure)
                performPendingAction();
            return;
        }

        sessionLock.locked = true;
    }

    function submitPassword(candidate: string): void {
        if (!candidate.length || pam.active)
            return;

        pendingPassword = candidate;
        promptIsError = false;
        prompt = "Checking password…";

        if (!pam.start()) {
            pendingPassword = "";
            prompt = "Authentication could not start";
            promptIsError = true;
            return;
        }

        sendPendingPassword();
    }

    function sendPendingPassword(): void {
        if (!pam.active || !pam.responseRequired || !pendingPassword.length)
            return;

        const response = pendingPassword;
        pendingPassword = "";
        pam.respond(response);
    }

    function performPendingAction(): void {
        const action = pendingAction;
        pendingAction = "";

        if (action === "power-off")
            Quickshell.execDetached(["systemctl", "poweroff"]);
        else if (action === "reboot")
            Quickshell.execDetached(["systemctl", "reboot"]);
        else if (action === "suspend")
            Quickshell.execDetached(["systemctl", "suspend"]);
    }

    PamContext {
        id: pam
        config: "login"

        onResponseRequiredChanged: root.sendPendingPassword()
        onPamMessage: {
            root.prompt = pam.message || "ENTER ACCESS KEY";
            root.promptIsError = pam.messageIsError;
            root.sendPendingPassword();
        }
        onCompleted: (result) => {
            if (result === PamResult.Success) {
                root.pendingPassword = "";
                root.pendingAction = "";
                sessionLock.locked = false;
                return;
            }

            root.pendingPassword = "";
            root.prompt = result === PamResult.Failed
                ? "That password was not accepted" : "Authentication failed; try again";
            root.promptIsError = true;
        }
        onError: (error) => {
            root.pendingPassword = "";
            root.prompt = "Authentication error: " + PamError.toString(error);
            root.promptIsError = true;
        }
    }

    WlSessionLock {
        id: sessionLock

        onSecureChanged: {
            if (!sessionLock.secure)
                return;
            root.performPendingAction();
        }

        WlSessionLockSurface {
            id: lockSurface
            color: "#0a0a09"

            LastOfUs {
                id: lastOfUs
                anchors.fill: parent
                visible: sessionLock.secure
                wallpaperPath: Walls.wallpaperForOutput(lockSurface.screen.name)
                username: root.username
                prompt: root.prompt
                promptIsError: root.promptIsError
                foregroundMode: Flags.lockForegroundMode
                recommendedForeground: Dyn.recommendedLockForeground
                paletteDark: Dyn.surfaceContainerLow
                paletteMuted: Dyn.outlineVariant
                paletteAccent: Dyn.primaryContainer
                paletteError: Dyn.error
                onAuthenticate: candidate => root.submitPassword(candidate)
                onPowerAction: action => root.requestLock(action)
            }

            Connections {
                target: sessionLock
                function onSecureChanged() {
                    if (sessionLock.secure)
                        Qt.callLater(lastOfUs.focusPassword);
                }
            }
        }
    }

    IpcHandler {
        target: "screenlock"

        function lock(): void { root.requestLock(""); }
        function powerOff(): void { root.requestLock("power-off"); }
        function suspend(): void { root.requestLock("suspend"); }
    }
}
