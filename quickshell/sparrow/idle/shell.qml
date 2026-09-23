pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "../Singletons" as SparrowBackend

ShellRoot {
    id: root

    readonly property string lockTrigger: Quickshell.env("HOME")
        + "/Projects/sparrow-shell/quickshell/sparrow/scripts/sparrow-lock"
    property bool screenOffRequested: false

    function dispatchLock(operation: string): void {
        lockProcess.command = [root.lockTrigger, operation];
        lockProcess.running = true;
    }

    function wakeOutputs(): void {
        SparrowBackend.Niri.powerOnOutputs();
    }

    IdleMonitor {
        id: lockMonitor
        timeout: Math.max(0, SparrowBackend.Flags.idleLockMin * 60)
        enabled: timeout > 0 && !SparrowBackend.Flags.keepAwake
        respectInhibitors: true
        onIsIdleChanged: if (isIdle && enabled)
            root.dispatchLock("lock")
    }

    IdleMonitor {
        id: screenMonitor
        timeout: Math.max(0, SparrowBackend.Flags.idleScreenOffMin * 60)
        enabled: timeout > 0 && !SparrowBackend.Flags.keepAwake
        respectInhibitors: true
        onIsIdleChanged: {
            if (isIdle && enabled) {
                root.screenOffRequested = true;
                root.dispatchLock("power-off");
            } else if (!isIdle && root.screenOffRequested) {
                root.screenOffRequested = false;
                root.wakeOutputs();
            }
        }
    }

    IdleMonitor {
        id: suspendMonitor
        timeout: Math.max(0, SparrowBackend.Flags.idleSuspendMin * 60)
        enabled: timeout > 0 && !SparrowBackend.Flags.keepAwake
        respectInhibitors: true
        onIsIdleChanged: if (isIdle && enabled)
            root.dispatchLock("suspend")
    }

    Process {
        id: lockProcess
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                console.error("Sparrow idle: lock/power action failed", exitCode, exitStatus);
        }
    }
}
