pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import "../lib/monitors.js" as Mon

Singleton {
    id: root

    // Raw compositor state.
    property var workspaces: []
    property var windows: []
    property var outputs: []
    readonly property var monitorNumberMap: Mon.monitorNumberAssignments(outputs, displayBindsFile.text())
    readonly property var numberedOutputs: Mon.numberedOutputs(outputs, monitorNumberMap)
    property var boundOutputNames: []
    property var pendingBoundOutputNames: []
    property int monitorBindingsRequestId: -1

    // One-shot output queries are refreshed by workspace configuration events.
    property bool outputRefreshPending: false

    // Queued actions prevent a rapid sequence of UI clicks from killing an
    // earlier niri-msg process when Process.exec() is called again.
    property var actionQueue: []
    property string activeAction: ""
    property string pendingDisplayConfirmationToken: ""
    property int pendingDisplayConfirmationSeconds: 0
    property string lastDesiredMonitorBinds: ""

    // Managed-config transactions are serialized in this backend before they
    // reach the shared helper (which also locks across non-QML callers).
    property var configTransactionQueue: []
    property var activeConfigTransaction: null
    property int configTransactionSerial: 0

    signal managedFragmentWriteFinished(int requestId, string status, string message, string confirmationToken, int timeoutSeconds)

    // Derived focus state.
    property int focusedWorkspaceId: -1
    property int focusedWindowId: -1
    property string focusedOutput: ""
    readonly property string configPath: Quickshell.env("NIRI_CONFIG") || ((Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/niri/config.kdl")
    readonly property string transactionHelperPath: Quickshell.shellPath("scripts/niri-config-transaction.py")

    function reloadConfig() {
        return enqueueAction(["niri", "msg", "action", "load-config-file"], "reload Niri config after Sparrow palette update");
    }

    function powerOffOutputs() {
        return enqueueAction(["niri", "msg", "action", "power-off-monitors"], "power off Niri outputs");
    }

    function powerOnOutputs() {
        return enqueueAction(["niri", "msg", "action", "power-on-monitors"], "power on Niri outputs");
    }

    /**
     * Submit content for an explicitly Sparrow-managed fragment. Most callers
     * send constrained KDL; user-binds sends constrained role/chord/custom data.
     * The helper owns schema validation, argv serialization, staging, validation, backups, atomic replacement, reload,
     * and rollback. IDs, never filesystem paths, are accepted at this boundary.
     */
    function writeManagedFragment(fragmentId, content, confirm = false) {
        var requestId = ++configTransactionSerial;
        var supported = ["generated-colors", "user-appearance", "display-outputs", "display-binds", "user-input", "user-binds"];
        if (supported.indexOf(fragmentId) < 0 || typeof content !== "string"
                || (confirm && fragmentId !== "display-outputs")) {
            Qt.callLater(function() {
                root.managedFragmentWriteFinished(requestId, "invalid_request",
                    "unsupported managed fragment or confirmation request", "", 0);
            });
            return requestId;
        }

        var next = configTransactionQueue.slice();
        next.push({ requestId: requestId, operation: "transact", fragmentId: fragmentId,
                    content: content, confirm: confirm });
        configTransactionQueue = next;
        startNextConfigTransaction();
        return requestId;
    }

    function confirmManagedFragment(token) {
        return resolveManagedConfirmation("confirm", token);
    }

    function rollbackManagedFragment(token) {
        return resolveManagedConfirmation("rollback", token);
    }

    function resolveManagedConfirmation(operation, token) {
        var requestId = ++configTransactionSerial;
        if ((operation !== "confirm" && operation !== "rollback") || !token || token !== pendingDisplayConfirmationToken) {
            Qt.callLater(function() {
                root.managedFragmentWriteFinished(requestId, "invalid_confirmation",
                    "no matching display change is awaiting confirmation", "", 0);
            });
            return requestId;
        }
        var next = configTransactionQueue.slice();
        next.push({ requestId: requestId, operation: operation, token: token });
        configTransactionQueue = next;
        startNextConfigTransaction();
        return requestId;
    }

    function startNextConfigTransaction() {
        if (transactionProcess.running || configTransactionQueue.length === 0)
            return;

        var next = configTransactionQueue[0];
        configTransactionQueue = configTransactionQueue.slice(1);
        activeConfigTransaction = next;
        transactionProcess.running = true;
    }

    function finishConfigTransaction(exitCode) {
        var request = activeConfigTransaction;
        var result = null;
        try {
            result = JSON.parse(transactionOutput.text.trim());
        } catch (e) {
            result = null;
        }

        var status = result && result.status ? result.status : "helper_failed";
        var message = result && result.message ? result.message
            : (transactionError.text.trim() || "Niri config transaction helper exited with code " + exitCode);
        if (exitCode !== 0 && status === "success")
            status = "helper_failed";

        var token = result && result.confirmationToken ? result.confirmationToken : "";
        var timeout = result && result.timeoutSeconds ? Number(result.timeoutSeconds) : 0;
        if (status === "confirmation_pending") {
            pendingDisplayConfirmationToken = token;
            pendingDisplayConfirmationSeconds = timeout;
        } else if (request && (request.operation === "confirm" || request.operation === "rollback")
                   && (status === "confirmed" || status === "rolled_back"
                       || (request.operation === "rollback" && status === "already_resolved"))) {
            pendingDisplayConfirmationToken = "";
            pendingDisplayConfirmationSeconds = 0;
        }

        if (request)
            managedFragmentWriteFinished(request.requestId, status, message, token, timeout);
        if (request && request.requestId === monitorBindingsRequestId) {
            if (status === "success") {
                boundOutputNames = pendingBoundOutputNames.slice();
                displayBindsFile.reload();
            } else {
                lastDesiredMonitorBinds = "";
                console.warn("Sparrow Niri: monitor shortcut regeneration failed:", message);
            }
            pendingBoundOutputNames = [];
            monitorBindingsRequestId = -1;
        }
        activeConfigTransaction = null;
        Qt.callLater(root.startNextConfigTransaction);
    }

    function workspaceById(id) {
        for (var i = 0; i < workspaces.length; i++)
            if (workspaces[i].id === id)
                return workspaces[i];

        return null;
    }

    function windowById(id) {
        for (var i = 0; i < windows.length; i++)
            if (windows[i].id === id)
                return windows[i];

        return null;
    }

    function outputByName(name) {
        for (var i = 0; i < outputs.length; i++)
            if (outputs[i].name === name)
                return outputs[i];

        return null;
    }

    function refreshOutputs() {
        if (outputsQuery.running) {
            outputRefreshPending = true;
            return;
        }

        outputRefreshPending = false;
        outputsQuery.running = true;
    }

    function monitorNumberForOutput(name) {
        var output = outputByName(String(name));
        return output ? (monitorNumberMap[String(output.identity || output.name)] || 0) : 0;
    }

    function writeMonitorBindings(assignments) {
        if (outputs.length === 0 || pendingDisplayConfirmationToken.length > 0
                || monitorBindingsRequestId >= 0
                || (activeConfigTransaction && activeConfigTransaction.operation === "transact"
                    && activeConfigTransaction.fragmentId === "display-outputs" && activeConfigTransaction.confirm))
            return -1;
        var desired = Mon.monitorBinds(outputs, assignments, displayBindsFile.text());
        var desiredNames = Mon.numberedOutputs(outputs, Mon.monitorNumberAssignments(outputs, desired))
            .map(function (output) { return output.name; });
        if (desired === displayBindsFile.text()) {
            lastDesiredMonitorBinds = desired;
            boundOutputNames = desiredNames;
            return 0;
        }
        if (desired === lastDesiredMonitorBinds)
            return -1;
        lastDesiredMonitorBinds = desired;
        pendingBoundOutputNames = desiredNames;
        monitorBindingsRequestId = writeManagedFragment("display-binds", desired);
        return monitorBindingsRequestId >= 0 ? monitorBindingsRequestId : -1;
    }

    function setMonitorNumber(name, number) {
        var output = outputByName(String(name));
        if (!output || !output.enabled)
            return -1;
        var assignment = Mon.assignMonitorNumber(outputs, monitorNumberMap,
            String(output.identity || output.name), Number(number));
        if (!assignment.ok)
            return -1;
        return writeMonitorBindings(assignment.assignments);
    }

    function syncMonitorBindings() {
        if (outputs.length === 0 || pendingDisplayConfirmationToken.length > 0
                || monitorBindingsRequestId >= 0
                || (activeConfigTransaction && activeConfigTransaction.operation === "transact"
                    && activeConfigTransaction.fragmentId === "display-outputs" && activeConfigTransaction.confirm))
            return;
        writeMonitorBindings(monitorNumberMap);
    }

    function enqueueAction(command, description) {
        var next = actionQueue.slice();
        next.push({ command: command, description: description });
        actionQueue = next;
        startNextAction();
        return true;
    }

    function startNextAction() {
        if (actionProcess.running || actionQueue.length === 0)
            return;

        var next = actionQueue[0];
        actionQueue = actionQueue.slice(1);
        activeAction = next.description;
        actionProcess.exec(next.command);
    }

    // Takes the stable Niri workspace ID; the current index is resolved at
    // invocation time because dynamic-workspace indices can change.
    function focusWorkspace(workspaceId) {
        var workspace = workspaceById(Number(workspaceId));

        if (!workspace) {
            console.warn("Sparrow Niri: cannot focus unknown workspace ID", workspaceId);
            return false;
        }

        return enqueueAction(
            ["niri", "msg", "action", "focus-workspace", String(workspace.idx)],
            "focus workspace ID " + workspace.id + " (current index " + workspace.idx + ")"
        );
    }

    function focusWindow(windowId) {
        var id = Number(windowId);

        if (!windowById(id)) {
            console.warn("Sparrow Niri: cannot focus unknown window ID", windowId);
            return false;
        }

        return enqueueAction(
            ["niri", "msg", "action", "focus-window", "--id", String(id)],
            "focus window ID " + id
        );
    }

    function normalizedAppId(value) {
        var appId = String(value || "").trim().toLowerCase();
        var slash = appId.lastIndexOf("/");
        if (slash >= 0)
            appId = appId.substring(slash + 1);
        if (appId.endsWith(".desktop"))
            appId = appId.substring(0, appId.length - 8);
        return appId;
    }

    function bestApplicationWindow(matches) {
        if (matches.length === 0)
            return null;

        matches.sort(function(a, b) {
            if (!!a.is_focused !== !!b.is_focused)
                return a.is_focused ? -1 : 1;

            var aCurrent = a.workspace_id === root.focusedWorkspaceId;
            var bCurrent = b.workspace_id === root.focusedWorkspaceId;
            if (aCurrent !== bCurrent)
                return aCurrent ? -1 : 1;

            var aTime = a.focus_timestamp || {};
            var bTime = b.focus_timestamp || {};
            var aSecs = Number(aTime.secs || 0);
            var bSecs = Number(bTime.secs || 0);
            if (aSecs !== bSecs)
                return bSecs - aSecs;
            var aNanos = Number(aTime.nanos || 0);
            var bNanos = Number(bTime.nanos || 0);
            if (aNanos !== bNanos)
                return bNanos - aNanos;
            return Number(a.id) - Number(b.id);
        });
        return matches[0];
    }

    function findWindowForApplication(desktopEntry, appName) {
        var preferred = normalizedAppId(desktopEntry);
        var fallback = normalizedAppId(appName);

        function exactMatches(token) {
            if (!token)
                return [];
            return windows.filter(function(win) {
                return normalizedAppId(win.app_id) === token;
            });
        }

        var matches = exactMatches(preferred);
        if (matches.length > 0)
            return bestApplicationWindow(matches);

        if (fallback && fallback !== preferred)
            return bestApplicationWindow(exactMatches(fallback));
        return null;
    }

    function focusApplicationWindow(desktopEntry, appName) {
        var match = findWindowForApplication(desktopEntry, appName);
        if (!match)
            return false;
        return focusWindow(match.id);
    }

    function workspacesForOutput(output) {
        return workspaces
            .filter(function(ws) {
                return ws.output === output;
            })
            .sort(function(a, b) {
                return a.idx - b.idx;
            });
    }

    function windowsForWorkspace(workspaceId) {
        return windows.filter(function(win) {
            return win.workspace_id === workspaceId;
        });
    }

    function activeWorkspaceForOutput(output) {
        for (var i = 0; i < workspaces.length; i++) {
            var ws = workspaces[i];

            if (ws.output === output && ws.is_active)
                return ws;
        }

        return null;
    }

    function refreshDerivedState() {
        focusedWorkspaceId = -1;
        focusedOutput = "";

        for (var i = 0; i < workspaces.length; i++) {
            if (workspaces[i].is_focused) {
                focusedWorkspaceId = workspaces[i].id;
                focusedOutput = workspaces[i].output || "";
                break;
            }
        }

        focusedWindowId = -1;

        for (var j = 0; j < windows.length; j++) {
            if (windows[j].is_focused) {
                focusedWindowId = windows[j].id;
                break;
            }
        }
    }

    function replaceWindow(win) {
        var next = windows.slice();
        var found = false;

        for (var i = 0; i < next.length; i++) {
            if (next[i].id === win.id) {
                next[i] = win;
                found = true;
                break;
            }
        }

        if (!found)
            next.push(win);

        windows = next;
    }

    function removeWindow(id) {
        windows = windows.filter(function(win) {
            return win.id !== id;
        });
    }

    function patchWindow(id, changes) {
        var next = windows.slice();

        for (var i = 0; i < next.length; i++) {
            if (next[i].id !== id)
                continue;

            var copy = Object.assign({}, next[i]);

            for (var key in changes)
                copy[key] = changes[key];

            next[i] = copy;
            windows = next;
            return;
        }
    }

    function patchWorkspace(id, changes) {
        var next = workspaces.slice();

        for (var i = 0; i < next.length; i++) {
            if (next[i].id !== id)
                continue;

            var copy = Object.assign({}, next[i]);

            for (var key in changes)
                copy[key] = changes[key];

            next[i] = copy;
            workspaces = next;
            return;
        }
    }

    function handleEvent(event) {
        if (event.WorkspacesChanged) {
            workspaces = event.WorkspacesChanged.workspaces || [];
            refreshOutputs();
        }

        else if (event.WindowsChanged) {
            windows = event.WindowsChanged.windows || [];
        }

        else if (event.WorkspaceActivated) {
            var activated = event.WorkspaceActivated;
            var activatedWorkspace = workspaceById(activated.id);

            if (!activatedWorkspace) {
                refreshDerivedState();
                return;
            }

            var activatedOutput = activatedWorkspace.output || "";
            var next = workspaces.slice();

            for (var i = 0; i < next.length; i++) {
                var ws = Object.assign({}, next[i]);

                if (ws.output === activatedOutput)
                    ws.is_active = ws.id === activated.id;

                if (activated.focused)
                    ws.is_focused = ws.id === activated.id;

                next[i] = ws;
            }

            workspaces = next;
        }

        else if (event.WorkspaceActiveWindowChanged) {
            patchWorkspace(
                event.WorkspaceActiveWindowChanged.workspace_id,
                { active_window_id: event.WorkspaceActiveWindowChanged.active_window_id }
            );
        }

        else if (event.WindowOpenedOrChanged) {
            var changedWindow = event.WindowOpenedOrChanged.window;

            if (changedWindow.is_focused) {
                var normalized = windows.slice();

                for (var j = 0; j < normalized.length; j++) {
                    var existing = Object.assign({}, normalized[j]);

                    if (existing.id !== changedWindow.id)
                        existing.is_focused = false;

                    normalized[j] = existing;
                }

                windows = normalized;
            }

            replaceWindow(changedWindow);
        }

        else if (event.WindowClosed) {
            removeWindow(event.WindowClosed.id);
        }

        else if (event.ConfigLoaded) {
            refreshOutputs();
        }

        else if (event.WindowFocusChanged) {
            var focusId = event.WindowFocusChanged.id;
            var focused = windows.slice();

            for (var j = 0; j < focused.length; j++) {
                var win = Object.assign({}, focused[j]);
                win.is_focused = focusId !== null && win.id === focusId;
                focused[j] = win;
            }

            windows = focused;
        }

        else if (event.WindowLayoutsChanged) {
            var changes = event.WindowLayoutsChanged.changes || [];

            for (var k = 0; k < changes.length; k++)
                patchWindow(changes[k][0], { layout: changes[k][1] });
        }

        else if (event.WindowFocusTimestampChanged) {
            patchWindow(
                event.WindowFocusTimestampChanged.id,
                { focus_timestamp: event.WindowFocusTimestampChanged.focus_timestamp }
            );
        }

        refreshDerivedState();
    }

    Process {
        id: eventStream

        command: ["niri", "msg", "--json", "event-stream"]

        onExited: (exitCode, exitStatus) => {
            console.warn("Sparrow Niri: event stream exited with code", exitCode,
                         "status", exitStatus, "; retrying shortly");
            eventStreamRestart.start();
        }

        stdout: SplitParser {
            onRead: data => {
                try {
                    var event = JSON.parse(data);
                    root.handleEvent(event);
                } catch (e) {
                    console.warn("Sparrow Niri IPC parse error:", e, data);
                }
            }
        }
    }

    Timer {
        id: eventStreamRestart
        interval: 1000
        repeat: false
        onTriggered: eventStream.running = true
    }

    Process {
        id: outputsQuery
        command: ["niri", "msg", "--json", "outputs"]

        stdout: SplitParser {
            onRead: data => {
                try {
                    var byName = JSON.parse(data);
                    root.outputs = Mon.parseNiri(JSON.stringify(byName));
                } catch (e) {
                    console.warn("Sparrow Niri: output query parse error:", e, data);
                }
            }
        }

        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                console.warn("Sparrow Niri: outputs query exited with code", exitCode,
                             "status", exitStatus);

            if (root.outputRefreshPending)
                Qt.callLater(root.refreshOutputs);
            else
                Qt.callLater(root.syncMonitorBindings);
        }
    }

    FileView {
        id: displayBindsFile
        path: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config"))
            + "/niri/sparrow/display-binds.kdl"
        blockLoading: true
        printErrors: false
    }

    Process {
        id: transactionProcess
        command: ["python3", root.transactionHelperPath]
        stdinEnabled: true
        stdout: StdioCollector { id: transactionOutput }
        stderr: StdioCollector { id: transactionError }

        onStarted: {
            if (root.activeConfigTransaction) {
                var request = root.activeConfigTransaction.operation === "transact"
                    ? { fragment: root.activeConfigTransaction.fragmentId,
                        content: root.activeConfigTransaction.content,
                        confirm: root.activeConfigTransaction.confirm }
                    : { operation: root.activeConfigTransaction.operation,
                        token: root.activeConfigTransaction.token };
                transactionProcess.write(JSON.stringify(request) + "\n");
            }
        }

        onExited: (exitCode, exitStatus) => root.finishConfigTransaction(exitCode)
    }

    Process {
        id: actionProcess

        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                console.warn("Sparrow Niri: action failed:", root.activeAction,
                             "exit code", exitCode, "status", exitStatus);

            root.startNextAction();
        }
    }

    Component.onCompleted: {
        eventStream.running = true;
        refreshOutputs();
    }
}
