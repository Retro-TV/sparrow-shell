pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    // Raw compositor state.
    property var workspaces: []
    property var windows: []
    property var outputs: []

    // One-shot output queries are refreshed by workspace configuration events.
    property bool outputRefreshPending: false

    // Queued actions prevent a rapid sequence of UI clicks from killing an
    // earlier niri-msg process when Process.exec() is called again.
    property var actionQueue: []
    property string activeAction: ""

    // Derived focus state.
    property int focusedWorkspaceId: -1
    property int focusedWindowId: -1
    property string focusedOutput: ""

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
                    var next = [];

                    Object.keys(byName).forEach(function(name) {
                        var output = Object.assign({}, byName[name]);
                        output.name = output.name || name;
                        next.push(output);
                    });

                    root.outputs = next;
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
        }
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
