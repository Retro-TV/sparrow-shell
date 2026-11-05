import QtQuick
import QtTest
import Quickshell
import "../../Singletons" as Services

TestCase {
    name: "WallpaperOwner"
    function initTestCase() { failOnWarning(/.*/); }
    function test_action_and_manual_requests_share_one_mutation_lane() {
        // Initialize production Walls with inert IO. Initial output list is empty.
        compare(Services.Walls.actionBusy, false);
        wait(20);
        Quickshell.commands = [];
        Quickshell.holdMutations = true;
        var result = null;
        var accepted = false;
        Services.Walls.runAction("set", "/test/a.png", "DP-1", function(r) {result=r;}, function() {accepted=true;});
        tryVerify(function() { return accepted; });
        verify(Services.Walls.actionBusy);
        Services.Walls.apply("/test/manual.png", "DP-1");
        Services.Walls.next();
        Services.Walls.recolor();
        compare(Quickshell.heldProcesses.length, 1);
        var busy = null;
        Services.Walls.runAction("set", "/test/b.png", "DP-1", function(r) {busy=r;});
        compare(busy.ok, false); compare(busy.accepted, false);
        Quickshell.holdMutations = false;
        Quickshell.releaseProcesses();
        tryVerify(function() { return result !== null && !Services.Walls.operationBusy && !Services.Walls.queuedRecolor; });
        compare(result.ok, true); compare(result.guarantee, "degraded");
        var mutations = Quickshell.commands.filter(function(c) { return ["set", "next", "recolor"].indexOf(c[2]) >= 0; });
        compare(mutations.length, 3);
        compare(mutations[0][2], "set"); compare(mutations[1][2], "next");
        compare(mutations[2][2], "recolor");
    }
    function test_failed_start_releases_owner() {
        Quickshell.failStart = true;
        var result = null;
        Services.Walls.runAction("set", "/test/a.png", "DP-1", function(r) { result=r; });
        tryVerify(function() { return result !== null; });
        compare(result.ok, false); compare(result.accepted, false); compare(Services.Walls.actionBusy, false);
    }

    function test_completion_callback_can_start_another_request() {
        var first = null;
        var second = null;
        Services.Walls.runAction("set", "/test/first.png", "DP-1", function(r) {
            first = r;
            Services.Walls.runAction("set", "/test/second.png", "DP-1", function(next) { second=next; });
        });
        tryVerify(function() { return first !== null && second !== null; });
        compare(first.ok, true); compare(second.ok, true);
    }

    function test_new_explicit_selection_supersedes_older_queued_random() {
        Quickshell.commands = [];
        Quickshell.holdMutations = true;
        Services.Walls.runAction("set", "/test/a.png", "DP-1", function(r) {});
        tryVerify(function() { return Quickshell.heldProcesses.length === 1; });
        Services.Walls.next();
        Services.Walls.apply("/test/newest.png", "DP-1");
        Quickshell.holdMutations = false;
        Quickshell.releaseProcesses();
        tryVerify(function() { return !Services.Walls.operationBusy && !Services.Walls.queuedApply; });
        var mutations=Quickshell.commands.filter(function(c) { return ["set","next"].indexOf(c[2])>=0; });
        compare(mutations.length,2); compare(mutations[1][3],"/test/newest.png");
    }

}
