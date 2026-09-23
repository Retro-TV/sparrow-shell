import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Mon = require("./monitors.js");

let failed = 0;
function eq(actual, expected, msg) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a === e) console.log("PASS " + msg);
    else { failed++; console.log("FAIL " + msg + "\n  expected " + e + "\n  got      " + a); }
}
function ok(cond, msg) { eq(!!cond, true, msg); }

const raw = {
    "DP-3": {
        name: "DP-3", make: "HKC OVERSEAS LIMITED", model: "GN05", serial: "0000000000001",
        modes: [
            { width: 2560, height: 1440, refresh_rate: 59951, is_preferred: true },
            { width: 2560, height: 1440, refresh_rate: 240002, is_preferred: false }
        ], current_mode: 0, is_custom_mode: false, logical: { x: 0, y: 0, width: 2560, height: 1440, scale: 1, transform: "Normal" }
    },
    "HDMI-A-1": {
        name: "HDMI-A-1", make: "Hisense Electric Co., Ltd.", model: "HISENSE", serial: "0x00000001",
        modes: [{ width: 3840, height: 2160, refresh_rate: 60000, is_preferred: true }], current_mode: 0,
        logical: { x: 2560, y: 0, width: 3840, height: 2160, scale: 1, transform: "Normal" }
    },
    "DP-2": {
        name: "DP-2", make: "Iiyama North America", model: "PL2770H", serial: "0x30303238",
        modes: [{ width: 1920, height: 1080, refresh_rate: 60000, is_preferred: true }], current_mode: 0,
        logical: { x: 6400, y: 0, width: 1920, height: 1080, scale: 1, transform: "Normal" }
    }
};

const outputs = Mon.parseNiri(JSON.stringify(raw));
eq(outputs.length, 3, "parse all connected outputs");
eq(outputs[0].currentMode.refreshMilliHz, 59951, "keep the compositor's exact current refresh");
eq(outputs[0].modes[1].refreshMilliHz, 240002, "keep the exact high-refresh mode");
eq(outputs[0].identity, "HKC OVERSEAS LIMITED GN05 0000000000001", "prefer portable make/model/serial identity");
eq(Mon.normalizeTransform("Flipped90"), "flipped-90", "normalize Niri IPC transform to config syntax");
eq(Mon.modeString(outputs[0].modes[1]), "2560x1440@240.002", "serialize exact Niri refresh syntax");
eq(Mon.logicalSize({ w: 1920, h: 1080 }, 1.5, "90"), { width: 720, height: 1280 }, "account for scale and quarter-turn transform");
ok(Mon.overlapError([{ label: "A", x: 0, y: 0, width: 100, height: 100 }, { label: "B", x: 99, y: 0, width: 100, height: 100 }]).length > 0, "reject overlapping output rectangles");
eq(Mon.overlapError([{ label: "A", x: 0, y: 0, width: 100, height: 100 }, { label: "B", x: 100, y: 0, width: 100, height: 100 }]), "", "allow edge-adjacent outputs");
const snapped = Mon.snapOutputPosition([
    { name: "A", label: "A", x: 0, y: 0, width: 100, height: 100, enabled: true },
    { name: "B", label: "B", x: 240, y: 0, width: 50, height: 50, enabled: true }
], "B", { x: 99, y: 12 });
eq(snapped, { ok: true, position: { x: 100, y: 12 }, target: "A", side: "right" }, "snap a one-pixel-overlap drop flush to the adjacent edge");
ok(Mon.overlapError([
    { x: snapped.position.x, y: snapped.position.y, width: 50, height: 50 },
    { x: 0, y: 0, width: 100, height: 100 }
]).length === 0, "snapped edge placement cannot overlap the target");

const fragment = Mon.buildOutputFragment(outputs, {}, "");
ok(fragment.ok, "build a Niri output fragment");
ok(fragment.text.includes('mode "2560x1440@59.951"'), "emit the currently active mode without rounding");
ok(fragment.text.includes('output "Hisense Electric Co., Ltd. HISENSE 0x00000001"'), "use monitor identity for persistent output configuration");
const retained = Mon.buildOutputFragment([outputs[0]], {}, fragment.text);
ok(retained.text.includes('output "Hisense Electric Co., Ltd. HISENSE 0x00000001"'), "retain disconnected output config for portable use");
const startupFocus = Mon.buildOutputFragment(outputs, {
    "DP-3": { focusAtStartup: true },
    "HDMI-A-1": { focusAtStartup: false },
    "DP-2": { focusAtStartup: false }
}, "");
ok(startupFocus.text.includes('output "HKC OVERSEAS LIMITED GN05 0000000000001" {\n    mode "2560x1440@59.951"\n    scale 1\n    transform "normal"\n    focus-at-startup\n'), "emit Niri's native startup-focus output setting");
eq(Mon.parseManagedOutputBlocks(startupFocus.text)[outputs[0].identity].focusAtStartup, true, "parse the persisted startup-focus setting");
const multipleStartupFocus = Mon.buildOutputFragment(outputs, {
    "DP-3": { focusAtStartup: true }, "HDMI-A-1": { focusAtStartup: true }
}, "");
eq(multipleStartupFocus.error, "Only one display can be focused at Niri startup.", "reject multiple startup-focus displays");

const override = Mon.buildOutputFragment(outputs, {
    "DP-3": { mode: outputs[0].modes[1], scale: 1, transform: "normal", position: { x: 0, y: 0 } }
}, "");
ok(override.text.includes('mode "2560x1440@240.002"'), "write selected high-refresh mode exactly");
const defaultNumbers = Mon.monitorNumberAssignments(outputs, "");
eq(outputs.map(o => defaultNumbers[o.identity]), [1, 2, 3], "initial display numbers follow the current arrangement");
const reassigned = Mon.assignMonitorNumber(outputs, defaultNumbers, outputs[1].identity, 1);
ok(reassigned.ok, "allow explicit monitor-number selection");
eq([reassigned.assignments[outputs[1].identity], reassigned.assignments[outputs[0].identity]], [1, 2], "choosing an occupied number swaps assignments without duplicates");
const binds = Mon.monitorBinds(outputs, reassigned.assignments);
ok(binds.includes('    // sparrow-monitor-number "Hisense Electric Co., Ltd. HISENSE 0x00000001" 1'), "persist explicit display-number assignment by monitor identity");
ok(binds.includes('Super+F1 hotkey-overlay-title="Focus display 1" { focus-monitor "HDMI-A-1"; }'), "bind display focus to its explicitly assigned number");
ok(binds.includes('Super+Shift+F2 hotkey-overlay-title="Move focused window to display 2" { move-window-to-monitor "DP-3"; }'), "bind window move to the same explicit number");
const roundTripNumbers = Mon.monitorNumberAssignments(outputs, binds);
eq(outputs.map(o => roundTripNumbers[o.identity]), [2, 1, 3], "read back persistent display numbers");
let requestedNumbers = defaultNumbers;
requestedNumbers = Mon.assignMonitorNumber(outputs, requestedNumbers, outputs[2].identity, 2).assignments;
requestedNumbers = Mon.assignMonitorNumber(outputs, requestedNumbers, outputs[1].identity, 3).assignments;
eq(outputs.map(o => requestedNumbers[o.identity]), [1, 3, 2], "support 1440p as 1, TV as 3, and 1080p as 2");
const requestedBinds = Mon.monitorBinds(outputs, requestedNumbers);
ok(requestedBinds.includes('Super+F1 hotkey-overlay-title="Focus display 1" { focus-monitor "DP-3"; }'), "bind requested 1440p display to number 1");
ok(requestedBinds.includes('Super+F2 hotkey-overlay-title="Focus display 2" { focus-monitor "DP-2"; }'), "bind requested 1080p display to number 2");
ok(requestedBinds.includes('Super+F3 hotkey-overlay-title="Focus display 3" { focus-monitor "HDMI-A-1"; }'), "bind requested 4K TV to number 3");
const single = Mon.monitorBinds(outputs.filter(o => o.name === "DP-3"), reassigned.assignments, binds);
ok(single.includes('Super+F2 hotkey-overlay-title="Focus display 2" { focus-monitor "DP-3"; }'), "keep the assigned number when other displays disconnect");
ok(single.includes('    // sparrow-monitor-number "Hisense Electric Co., Ltd. HISENSE 0x00000001" 1'), "retain disconnected display number metadata");
const migrated = Mon.monitorNumberAssignments(outputs, "// Generated by Sparrow from the current Niri output arrangement.\nbinds {\n    Super+F1 hotkey-overlay-title=\"Focus display 1\" { focus-monitor \"DP-3\"; }\n}\n");
eq(migrated[outputs[0].identity], 1, "migrate connector-based numbers to stable monitor identity");
const mixedMetadata = Mon.monitorNumberAssignments(outputs,
    'binds {\n    // sparrow-monitor-number "DP-3" 2\n'
    + '    // sparrow-monitor-number "HKC OVERSEAS LIMITED GN05 0000000000001" 5\n'
    + '    // sparrow-monitor-number "HDMI-A-1" 1\n'
    + '    // sparrow-monitor-number "Hisense Electric Co., Ltd. HISENSE 0x00000001" 4\n'
    + '    // sparrow-monitor-number "DP-2" 3\n'
    + '    // sparrow-monitor-number "Iiyama North America PL2770H 0x30303238" 6\n}');
eq(outputs.map(o => mixedMetadata[o.identity]), [2, 1, 3], "prefer existing connector numbers when repairing mixed legacy and identity metadata");

process.exit(failed === 0 ? 0 : 1);
