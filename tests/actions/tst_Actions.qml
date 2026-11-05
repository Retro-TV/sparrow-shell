import QtQuick
import QtTest
import Quickshell
import "../../Singletons" as Services

TestCase {
    id: testCase
    name: "ActionAdapters"
    QtObject {
        id: flags
        property bool flagsStateReady: true
        property bool dnd: false
        property bool keepAwake: false
        property string appearanceMode: "auto"
        property string paletteMode: "dynamic"
        property string paletteVariant: "auto"
    }
    QtObject {
        id: audio
        property var nodes: ({values:[sink, source]})
        property var defaultAudioSink: sink
        property var defaultAudioSource: source
        property var preferredDefaultAudioSink: null
        property var preferredDefaultAudioSource: null
        onPreferredDefaultAudioSinkChanged: defaultAudioSink = preferredDefaultAudioSink
        onPreferredDefaultAudioSourceChanged: defaultAudioSource = preferredDefaultAudioSource
    }
    QtObject {
        id: sink
        property string name: "test.sink"
        property bool isSink: true
        property bool isStream: false
        property bool ready: true
        property var properties: ({})
        property QtObject audio: QtObject {
            property real volume: 0.3
            property bool muted: false
        }
    }
    QtObject {
        id: source
        property string name: "test.source"
        property bool isSink: false
        property bool isStream: false
        property bool ready: true
        property var properties: ({})
        property QtObject audio: QtObject {
            property real volume: 0.4
            property bool muted: false
        }
    }
    QtObject {
        id: compositor
        property var outputs: [{identity:"test.monitor", name:"DP-1", enabled:true}]
    }
    QtObject {
        id: walls
        property int actionRevision: 0
        property bool actionBusy: false
        property int writes: 0
        property bool failNext: false
        property bool holdAction: false
        property var pendingAction: null
        readonly property bool operationBusy: actionBusy
        function runAction(kind, path, output, done, accepted) {
            writes++; actionRevision++; actionBusy=true; accepted();
            if (failNext) { failNext = false; actionBusy=false; done({ok:false,accepted:true,message:"fake helper failure"}); return; }
            var complete=function() {
                walls.actionBusy=false;
                Quickshell.probeResult = {supported:true,
                    value:kind === "set" ? path : Quickshell.probeResult.value,
                    revision:String(walls.actionRevision)};
                done({ok:true,accepted:true,applied:true,guarantee:"degraded"});
            };
            if (holdAction) pendingAction=complete;
            else complete();
        }
    }
    function action(type, value, target, ending) {
        var a = {version:1, type:type, params:{value:value}};
        if (target !== undefined) a.params.target = target;
        if (ending) a.ending = ending;
        return a;
    }
    function initTestCase() { failOnWarning(/.*/); verify(Services.Actions.attach(flags, walls, compositor, audio)); }
    function test_behavior_preview_execute_restore() {
        var a = action("desktop.dnd", true, undefined, {policy:"restore"});
        var preview;
        Services.Actions.preview(a, function(r) { preview = r; });
        verify(preview.ok); compare(flags.dnd, false);
        var id = Services.Actions.execute(a);
        compare(Services.Actions.result(id).status, "verified"); compare(flags.dnd, true);
        var end = Services.Actions.release(Services.Actions.result(id).ownershipToken);
        compare(Services.Actions.result(end).status, "verified"); compare(flags.dnd, false);
        id = Services.Actions.execute(action("desktop.keepAwake", true));
        compare(Services.Actions.result(id).status, "verified"); compare(flags.keepAwake, true);
    }
    function test_audio_setters_and_readback() {
        var id = Services.Actions.execute(action("audio.defaultOutput", "test.sink"));
        compare(Services.Actions.result(id).status, "verified");
        id = Services.Actions.execute(action("audio.defaultInput", "test.source"));
        compare(Services.Actions.result(id).status, "verified");
        id = Services.Actions.execute(action("audio.outputVolume", 0.7, "test.sink"));
        compare(Services.Actions.result(id).status, "verified"); compare(sink.audio.volume, 0.7);
        id = Services.Actions.execute(action("audio.outputMute", true, "test.sink"));
        compare(Services.Actions.result(id).status, "verified"); compare(sink.audio.muted, true);
    }
    function test_missing_audio_device() {
        var id = Services.Actions.execute(action("audio.defaultOutput", "missing"));
        compare(Services.Actions.result(id).status, "skipped");
    }
    function test_manual_change_invalidates_restore() {
        var id = Services.Actions.execute(action("audio.outputVolume", 0.5, "test.sink", {policy:"restore"}));
        var token = Services.Actions.result(id).ownershipToken;
        sink.audio.volume = 0.2; sink.audio.volume = 0.5;
        var end = Services.Actions.release(token);
        compare(Services.Actions.result(end).status, "skipped"); compare(sink.audio.volume, 0.5);
    }
    function test_wallpaper_preview_and_execution_are_distinct() {
        var a = action("wallpaper.output", "/test/new.png", "test.monitor");
        var before = walls.writes;
        var preview = null;
        Services.Actions.preview(a, function(r) { preview = r; });
        tryVerify(function() { return preview !== null; });
        verify(preview.ok); compare(walls.writes, before);
        var id = Services.Actions.execute(a);
        tryVerify(function() { return Services.Actions.result(id).status !== "running"; });
        compare(Services.Actions.result(id).status, "degraded");
        compare(Services.Actions.result(id).verified, false); compare(walls.writes, before + 1);
    }
    function test_appearance_dynamic_only_and_helper_failure() {
        flags.paletteMode = "static";
        var id = Services.Actions.execute(action("appearance.mode", "light"));
        compare(Services.Actions.result(id).status, "skipped");
        flags.paletteMode = "dynamic";
        id = Services.Actions.execute(action("appearance.mode", "light"));
        tryVerify(function() { return Services.Actions.result(id).status !== "running"; });
        compare(Services.Actions.result(id).status, "degraded"); compare(flags.appearanceMode, "light");
        walls.failNext = true;
        id = Services.Actions.execute(action("wallpaper.output", "/test/fail.png", "test.monitor"));
        tryVerify(function() { return Services.Actions.result(id).status !== "running"; });
        compare(Services.Actions.result(id).status, "failed");
    }
    function test_cancel_during_passive_probe() {
        var before = walls.writes;
        var id = Services.Actions.execute(action("wallpaper.output", "/test/cancel.png", "test.monitor"));
        verify(Services.Actions.cancel(id));
        wait(10);
        compare(Services.Actions.result(id).status, "cancelled"); compare(walls.writes, before);
    }
    function test_missing_output_and_ambiguous_audio() {
        var before = walls.writes;
        var id = Services.Actions.execute(action("wallpaper.output", "/test/missing.png", "missing"));
        compare(Services.Actions.result(id).status, "skipped"); compare(walls.writes, before);
        audio.nodes = {values:[sink, sink, source]};
        id = Services.Actions.execute(action("audio.defaultOutput", "test.sink"));
        compare(Services.Actions.result(id).status, "skipped");
        audio.nodes = {values:[sink, source]};
    }

    function test_probe_failed_to_start_reports_without_dispatch() {
        Quickshell.failStart = true;
        var before = walls.writes;
        var id = Services.Actions.execute(action("wallpaper.output", "/test/a.png", "test.monitor"));
        tryVerify(function() { return Services.Actions.result(id).status !== "running"; });
        compare(Services.Actions.result(id).status, "skipped"); compare(walls.writes, before);
    }

    function test_busy_appearance_does_not_change_preference() {
        walls.actionBusy=true;
        var before=flags.appearanceMode;
        var id=Services.Actions.execute(action("appearance.mode",before === "dark" ? "light" : "dark"));
        tryVerify(function() { return Services.Actions.result(id).status !== "running"; });
        compare(flags.appearanceMode,before);compare(Services.Actions.result(id).accepted,false);
        walls.actionBusy=false;
    }
    function test_hung_dispatch_blocks_only_conflicts_and_late_drain_never_owns() {
        walls.holdAction=true;
        var a=action("wallpaper.output","/test/hung.png","test.monitor",{policy:"restore"});a.timeoutMs=100;
        var id=Services.Actions.execute(a);
        tryVerify(function() { return Services.Actions.result(id).status === "timed_out"; });
        compare(Services.Actions.blocked().length,1);
        var unrelated=Services.Actions.execute(action("desktop.keepAwake",!flags.keepAwake));
        compare(Services.Actions.result(unrelated).status,"verified");
        var conflict=Services.Actions.execute(action("wallpaper.output","/test/other.png","test.monitor"));
        compare(Services.Actions.result(conflict).status,"skipped");
        var recovery=null;Services.Actions.recover(id,function(r) {recovery=r;});
        compare(recovery.recovered,false);
        walls.holdAction=false;
        var complete=walls.pendingAction;walls.pendingAction=null;complete();
        compare(Services.Actions.blocked().length,0);compare(Services.Actions.result(id).status,"timed_out");
        verify(!Services.Actions.result(id).ownershipToken);
    }
    function test_recovery_requires_idle_owner_and_idle_writer_lock() {
        walls.holdAction=true;
        var a=action("wallpaper.output","/test/lost-callback.png","test.monitor");a.timeoutMs=100;
        var id=Services.Actions.execute(a);
        tryVerify(function() { return Services.Actions.result(id).status === "timed_out"; });
        // Model a fully stopped parent with a lost completion callback.
        walls.pendingAction=null;walls.holdAction=false;walls.actionBusy=false;
        Quickshell.recoverySafe=false;
        var response=null;Services.Actions.recover(id,function(r) {response=r;});
        tryVerify(function() {return response!==null;});compare(response.recovered,false);
        compare(Services.Actions.blocked().length,1);
        Quickshell.recoverySafe=true;response=null;
        Services.Actions.recover(id,function(r) {response=r;});
        tryVerify(function() {return response!==null;});compare(response.recovered,true);
        compare(Services.Actions.blocked().length,0);compare(Services.Actions.result(id).status,"timed_out");
    }
    function test_stuck_passive_preview_has_deadline_and_releases_probe() {
        Quickshell.holdProbes=true;
        var before=walls.writes,response=null;
        Services.Actions.preview(action("wallpaper.output","/test/probe.png","test.monitor"),function(r) {response=r;});
        tryVerify(function() {return response!==null;},3000);
        verify(!response.ok);compare(walls.writes,before);compare(Services.Actions.probes.length,0);
        Quickshell.holdProbes=false;
    }

}
