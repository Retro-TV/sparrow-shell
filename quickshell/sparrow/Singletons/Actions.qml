pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import "../lib/action-engine.js" as Contract

// Lazy backend API only. Call attach with already-running owners; preview must
// not instantiate Flags/Walls (their startup paths can write state).
Singleton {
    id: root
    property var audio: Pipewire
    property var flags: null
    property var walls: null
    property var compositor: null
    property var engine: null
    property int behaviorRevision: 0
    property int awakeRevision: 0
    property int appearanceRevision: 0
    property int graphRevision: 0
    property int defaultOutputRevision: 0
    property int defaultInputRevision: 0
    property var audioRevisions: ({})
    property var probes: []
    property bool engineBusy: false
    property bool appearancePending: false
    signal resultChanged(var result)

    ElapsedTimer { id: actionClock }

    function attach(flagsOwner, wallsOwner, niriOwner, audioOwner) {
        if (engine) return false;
        if (audioOwner) audio = audioOwner;
        flags = flagsOwner;
        walls = wallsOwner;
        compositor = niriOwner;
        actionClock.restart();
        engine = Contract.createEngine({now: function() { return actionClock.elapsedMs(); },
            inspect: root.inspect, apply: root.apply, recover: root.recoverBackend});
        engine.onResult(function(result) { root.resultChanged(result); });
        return true;
    }
    function preview(action, callback) {
        if (!engine) { callback({ok:false, message:"Attach existing services first"}); return; }
        engine.preview(action, callback);
    }
    function execute(action) {
        if (!engine) return -1;
        var id = engine.execute(action); engineBusy = engine.polling(); return id;
    }
    function release(token) {
        if (!engine) return -1;
        var id = engine.release(token); engineBusy = engine.polling(); return id;
    }
    function blocked() { return engine ? engine.blocked() : []; }
    function recover(id, callback) {
        if (!engine) { callback({recovered:false, message:"Attach existing services first"}); return; }
        engine.recover(id, callback);
        engineBusy = engine.polling();
    }
    function recoverBackend(a, callback) {
        if (!walls || walls.operationBusy || appearancePending) {
            callback({safe:false, message:"Writer still active. Conflicting actions stay blocked; inspect the owner, or restart sparrow-shell.service after approval. Never bypass the wallpaper lock."});
            return;
        }
        runProbe({type:"recovery"}, "", function(s) {
            callback({safe:s.supported && s.safe === true && !walls.operationBusy && !appearancePending,
                message:s.message || "Writer quiescence could not be confirmed"});
        });
    }
    function cancel(id) { return engine ? engine.cancel(id) : false; }
    function result(id) { return engine ? engine.result(id) : null; }
    function forget(id) { if (engine) engine.forget(id); }
    function abandon(token) { if (engine) engine.abandon(token); }
    function validate(action) { return Contract.validate(action); }
    function serialize(action) { return Contract.serialize(action); }
    function deserialize(json) { return Contract.deserialize(json); }
    function fromObserved(type, target, observation) { return Contract.fromObserved(type, target, observation); }

    function bumpAudio(name, field) {
        var next = Object.assign({}, audioRevisions);
        var key = name + ":" + field;
        next[key] = (next[key] || 0) + 1;
        audioRevisions = next;
    }
    function node(name, input) {
        return Contract.resolveAudioNode(audioNodes, name, input).node;
    }
    function output(identity) {
        if (!compositor) return null;
        var matches = compositor.outputs.filter(function(o) { return o.identity === identity && o.enabled; });
        return matches.length === 1 ? matches[0] : null;
    }
    function observeAudio(a) {
        var input = a.type === "audio.defaultInput";
        var defaults = a.type === "audio.defaultOutput" || input;
        var wanted = node(defaults ? a.params.value : a.params.target, input);
        if (!wanted) return {supported:false,
            ambiguous:Contract.resolveAudioNode(audioNodes, defaults ? a.params.value : a.params.target, input).ambiguous,
            message:"Audio device unavailable, unready or ambiguous"};
        var current = input ? audio.defaultAudioSource : audio.defaultAudioSink;
        if (defaults) return {supported:true, value:current ? current.name : "",
            revision:graphRevision + ":" + (input ? defaultInputRevision : defaultOutputRevision)};
        var field = a.type === "audio.outputVolume" ? "volume" : "muted";
        return {supported:true, value:wanted.audio[field],
            revision:graphRevision + ":" + (audioRevisions[wanted.name + ":" + field] || 0)};
    }
    function inspect(a, callback) {
        if (!flags || !flags.flagsStateReady) { callback({supported:false, message:"Flags not ready"}); return; }
        if (a.type === "desktop.dnd") { callback({supported:true, value:flags.dnd, revision:behaviorRevision}); return; }
        if (a.type === "desktop.keepAwake") { callback({supported:true, value:flags.keepAwake, revision:awakeRevision}); return; }
        if (a.type.indexOf("audio.") === 0) { callback(observeAudio(a)); return; }
        if (!walls || !compositor) { callback({supported:false, message:"Wallpaper services not attached"}); return; }
        if (a.type === "appearance.mode" && flags.paletteMode !== "dynamic") {
            callback({supported:false, message:"Light/dark preference requires Dynamic palette mode"}); return;
        }
        var out = a.type === "wallpaper.output" ? output(a.params.target) : null;
        if (a.type === "wallpaper.output" && !out) {
            callback({supported:false, message:"Output unavailable or ambiguous"}); return;
        }
        // Snapshot dependency generations before async reads, then reject stale reads.
        var revision = appearanceRevision + ":" + walls.actionRevision;
        runProbe(a, out ? out.name : "", function(s) {
            if (revision !== appearanceRevision + ":" + walls.actionRevision) {
                callback({supported:false, message:"Wallpaper/appearance changed during inspection"}); return;
            }
            if (a.type === "wallpaper.output" && (!root.output(a.params.target) || root.output(a.params.target).name !== out.name)) {
                callback({supported:false, message:"Output changed during inspection"}); return;
            }
            if (a.type === "appearance.mode") s.value = flags.appearanceMode;
            s.revision = revision + ":" + s.revision;
            callback(s);
        });
    }
    function runProbe(a, outputName, done) {
        if (probes.length >= 8) { done({supported:false, message:"Too many pending prerequisite probes"}); return; }
        var process = probeComponent.createObject(root, {action:a, outputName:outputName, done:done});
        if (!process) { done({supported:false, message:"Cannot create prerequisite probe"}); return; }
        probes = probes.concat([process]);
    }
    function apply(a, callback, accepted) {
        if (a.type === "desktop.dnd") flags.dnd = a.params.value;
        else if (a.type === "desktop.keepAwake") flags.keepAwake = a.params.value;
        else if (a.type.indexOf("audio.") === 0) {
            let input = a.type === "audio.defaultInput";
            let defaults = a.type === "audio.defaultOutput" || input;
            let device = node(defaults ? a.params.value : a.params.target, input);
            if (!device) { callback({ok:false, accepted:false, message:"Audio device disappeared"}); return; }
            if (defaults) {
                if (input) audio.preferredDefaultAudioSource = device;
                else audio.preferredDefaultAudioSink = device;
            } else device.audio[a.type === "audio.outputVolume" ? "volume" : "muted"] = a.params.value;
        } else {
            let out = a.type === "wallpaper.output" ? output(a.params.target) : null;
            if (walls.operationBusy || walls.queuedApply || walls.queuedNext || walls.queuedRecolor
                    || (a.type === "wallpaper.output" && !out)) {
                callback({ok:false, accepted:false, message:"Wallpaper busy or output disappeared"}); return;
            }
            if (a.type === "appearance.mode") {
                if (flags.paletteMode !== "dynamic") { callback({ok:false, accepted:false, message:"Palette mode changed"}); return; }
                flags.appearanceMode = a.params.value;
                // Flags writes its adapter before this timer launches the reader.
                accepted({applied:flags.appearanceMode === a.params.value});
                appearancePending = true;
                recolorTimer.done = function(outcome) { root.appearancePending=false; callback(outcome); };
                recolorTimer.expectedRevision = appearanceRevision;
                recolorTimer.start();
            } else {
                runWallpaper("set", a.params.value, out.name, callback, accepted);
            }
            return;
        }
        accepted();
        callback({ok:true, accepted:true, applied:false, guarantee:"verified"});
    }
    function runWallpaper(kind, path, outputName, callback, accepted) {
        var expectedAppearance = appearanceRevision;
        var expectedWallpaper = walls.actionRevision + 1;
        walls.runAction(kind, path, outputName, function(outcome) {
            if (outcome.ok && (expectedAppearance !== appearanceRevision || expectedWallpaper !== walls.actionRevision)) {
                callback({ok:false, accepted:true, applied:outcome.applied,
                    message:"Manual wallpaper or appearance change during execution; no ownership acquired"});
                return;
            }
            callback(outcome);
        }, accepted);
    }
    Timer {
        id: recolorTimer
        property var done: null
        property int expectedRevision: 0
        interval: 300
        onTriggered: {
            var callback = done;
            done = null;
            if (root.appearanceRevision !== expectedRevision) {
                callback({ok:false, accepted:true, message:"Appearance changed before recolor"}); return;
            }
            var revision = expectedRevision;
            root.inspect({type:"appearance.mode", params:{value:root.flags.appearanceMode}}, function(s) {
                if (revision !== root.appearanceRevision || !s.supported
                        || s.persistedMode !== root.flags.appearanceMode || s.persistedPaletteMode !== "dynamic") {
                    callback({ok:false, accepted:true, applied:true,
                        message:"Appearance preference changed or was not persisted; recolor not dispatched"}); return;
                }
                root.runWallpaper("recolor", "", "", callback, function() {});
            });
        }
    }
    Timer {
        interval: 100
        repeat: true
        running: root.engineBusy
        onTriggered: { root.engine.tick(); root.engineBusy = root.engine.polling(); }
    }
    Connections {
        target: root.flags
        function onDndChanged() { root.behaviorRevision++; }
        function onKeepAwakeChanged() { root.awakeRevision++; }
        function onAppearanceModeChanged() { root.appearanceRevision++; }
        function onPaletteModeChanged() { root.appearanceRevision++; }
        function onPaletteVariantChanged() { root.appearanceRevision++; }
    }
    Connections {
        target: root.audio
        function onDefaultAudioSinkChanged() { root.defaultOutputRevision++; }
        function onDefaultAudioSourceChanged() { root.defaultInputRevision++; }
    }
    readonly property var audioNodes: audio && audio.nodes ? audio.nodes.values : []
    onAudioNodesChanged: graphRevision++
    PwObjectTracker { objects: root.audio === Pipewire ? root.audioNodes.filter(function(n) { return n && !n.isStream && n.audio; }) : [] }
    Instantiator {
        model: root.audioNodes
        delegate: Item {
            id: nodeObserver
            required property var modelData
            Connections {
                target: nodeObserver.modelData.audio
                function onVolumeChanged() { root.bumpAudio(nodeObserver.modelData.name, "volume"); }
                function onMutedChanged() { root.bumpAudio(nodeObserver.modelData.name, "muted"); }
            }
            Connections {
                target: nodeObserver.modelData
                function onReadyChanged() { root.graphRevision++; }
                function onNameChanged() { root.graphRevision++; }
                function onPropertiesChanged() { root.graphRevision++; }
            }
        }
    }
    Component {
        id: probeComponent
        Process {
            id: probe
            property var action
            property string outputName
            property var done
            property bool settled: false
            function completeProbe(observation) {
                if (settled) return;
                settled = true;
                var callback = done;
                done = null;
                root.probes = root.probes.filter(function(p) { return p !== probe; });
                destroy();
                callback(observation);
            }
            property Timer deadlineTimer: Timer {
                interval: 2000
                running: !probe.settled
                onTriggered: {
                    // Only this read-only probe is interruptible, never a writer.
                    probe.completeProbe({supported:false, safe:false, message:"Prerequisite probe timed out"});
                    if (probe.running) probe.signal(15);
                }
            }
            onRunningChanged: if (!running) Qt.callLater(function() {
                if (probe && !probe.settled) probe.completeProbe({supported:false, message:"Prerequisite probe did not complete"});
            })
            command: ["python3", Quickshell.shellPath("scripts/action-probe.py")]
            stdinEnabled: true
            Component.onCompleted: running = true
            onStarted: {
                write(JSON.stringify({type:action.type, params:action.params, output:outputName}));
                stdinEnabled = false;
            }
            stdout: StdioCollector { id: probeOutput }
            onExited: (exitCode, exitStatus) => {
                var observation = {supported:false, message:"Prerequisite probe failed"};
                try { if (exitCode === 0) observation = JSON.parse(probeOutput.text); } catch(e) { /* structured failure above */ }
                completeProbe(observation);
            }
        }
    }
}
