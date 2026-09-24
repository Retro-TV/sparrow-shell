pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

/**
 * Niri night-light controller. A managed wlsunset process applies the Wayland
 * gamma-control protocol to every enabled output. The saved mode, temperature,
 * and schedule remain in Flags; probing and startup restoration happen with
 * the main shell, not when the settings surface is opened. Quickshell owns the
 * process, so it is stopped on shell exit/reload and recreated from Flags.
 */
Singleton {
    id: root

    property bool binaryAvailable: false
    property bool backendFailed: false
    property bool restartPending: false
    property string backendError: ""

    readonly property bool available: binaryAvailable && !backendFailed
    readonly property bool enabled: available && runner.running && root.shouldRun()
    readonly property string unavailableReason: !binaryAvailable
        ? "Unavailable — install wlsunset to apply color temperature"
        : (backendFailed ? "Unavailable — wlsunset could not initialize for this session" : "Checking wlsunset")

    function clampTemp(t) {
        return Math.max(2200, Math.min(6000, Math.round(t)));
    }

    function hhmm(min) {
        var h = Math.floor(min / 60);
        var m = min % 60;
        return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
    }

    function shouldRun() {
        return Flags.nightLightMode === "on"
            || (Flags.nightLightMode === "scheduled"
                && Flags.nightLightOnMin !== Flags.nightLightOffMin);
    }

    /**
     * wlsunset interpolates low→high from sunrise to sunset. For a night
     * interval, the warm value is low; for a daytime interval the endpoints
     * are reversed so the same warm window remains exact. Duration zero keeps
     * the previous immediate-on/off behavior.
     */
    function desiredCommand() {
        if (!root.shouldRun())
            return [];

        var temp = root.clampTemp(Flags.nightLightTemp);
        if (Flags.nightLightMode === "on") {
            // Keep low/high distinct (wlsunset divides by their difference).
            // Equal sunrise/sunset makes its calculated position stay at low
            // all day, so the exact selected temperature is held continuously.
            return ["wlsunset", "-t", String(temp), "-T", String(temp + 1),
                    "-S", "00:00", "-s", "00:00", "-d", "0"];
        }

        var on = Flags.nightLightOnMin;
        var off = Flags.nightLightOffMin;
        if (on > off) {
            // Overnight: warm from the configured sunset through sunrise.
            return ["wlsunset", "-t", String(temp), "-T", "6500",
                    "-S", root.hhmm(off), "-s", root.hhmm(on), "-d", "0"];
        }

        // Daytime interval: invert the endpoints so the configured interval is
        // warm, matching the original windowOpen() behavior.
        return ["wlsunset", "-t", "6500", "-T", String(temp),
                "-S", root.hhmm(on), "-s", root.hhmm(off), "-d", "0"];
    }

    function sameCommand(a, b) {
        return a.length === b.length && a.join("\u0000") === b.join("\u0000");
    }

    function probe() {
        if (!binaryAvailable && !probeProcess.running)
            probeProcess.running = true;
    }

    function sync() {
        if (!root.binaryAvailable)
            return;

        var desired = root.desiredCommand();
        if (runner.running) {
            if (desired.length && root.sameCommand(runner.command, desired))
                return;
            root.restartPending = true;
            runner.running = false;
            return;
        }

        if (!desired.length)
            return;

        root.backendFailed = false;
        root.backendError = "";
        runner.command = desired;
        runner.running = true;
    }

    function requestSync() {
        if (Flags.nightLightMode === "off") {
            configTimer.stop();
            root.sync();
        } else {
            configTimer.restart();
        }
    }

    function setMode(mode) {
        Flags.nightLightMode = mode;
        root.requestSync();
    }

    function setTemp(temp) {
        Flags.nightLightTemp = root.clampTemp(temp);
        root.requestSync();
    }

    function setOnMin(value) {
        Flags.nightLightOnMin = value;
        root.requestSync();
    }

    function setOffMin(value) {
        Flags.nightLightOffMin = value;
        root.requestSync();
    }

    Component.onCompleted: root.probe()

    Process {
        id: probeProcess
        command: ["sh", "-c",
            "command -v wlsunset >/dev/null 2>&1 && printf 'available'"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                root.binaryAvailable = this.text.trim() === "available";
                if (root.binaryAvailable)
                    root.sync();
            }
        }
    }

    Process {
        id: runner
        command: []
        running: false
        onExited: {
            if (root.restartPending) {
                root.restartPending = false;
                root.sync();
            } else if (root.shouldRun()) {
                root.backendFailed = true;
                root.backendError = "wlsunset stopped unexpectedly";
                console.warn("Sparrow Night Light: " + root.backendError);
            }
        }
    }

    Timer {
        id: configTimer
        interval: 250
        onTriggered: root.sync()
    }
}
