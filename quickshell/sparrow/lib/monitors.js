/* Pure helpers for Niri output discovery, stable display numbering and KDL. */

var VALID_TRANSFORMS = [
    "normal", "90", "180", "270", "flipped", "flipped-90", "flipped-180", "flipped-270"
];

function lexical(a, b) {
    return a < b ? -1 : (a > b ? 1 : 0);
}

function normalizeTransform(value) {
    return String(value || "normal").toLowerCase().replace(/^flipped(90|180|270)$/, "flipped-$1");
}

function parseNiri(jsonText) {
    var raw;
    try {
        raw = JSON.parse(jsonText);
    } catch (e) {
        return [];
    }
    if (!raw || typeof raw !== "object" || Array.isArray(raw))
        return [];

    return Object.keys(raw).map(function (name) {
        var item = raw[name] || {};
        var logical = item.logical || null;
        var modes = (item.modes || []).map(function (mode) {
            return {
                w: Number(mode.width),
                h: Number(mode.height),
                refreshMilliHz: Number(mode.refresh_rate),
                preferred: mode.is_preferred === true
            };
        }).filter(function (mode) {
            return Number.isFinite(mode.w) && Number.isFinite(mode.h)
                && Number.isFinite(mode.refreshMilliHz) && mode.w > 0 && mode.h > 0;
        });
        var index = Number.isInteger(item.current_mode) ? item.current_mode : -1;
        var current = index >= 0 && index < modes.length ? modes[index] : null;
        var make = String(item.make || "").trim();
        var model = String(item.model || "").trim();
        var serial = item.serial === null || item.serial === undefined ? "" : String(item.serial).trim();
        var label = [make, model].filter(function (part) { return part.length > 0; }).join(" ");

        return {
            name: String(item.name || name),
            make: make,
            model: model,
            serial: serial,
            label: label || String(item.name || name),
            identity: make && model && serial ? [make, model, serial].join(" ") : String(item.name || name),
            physicalSize: item.physical_size || null,
            modes: modes,
            currentMode: current,
            currentModeIndex: index,
            enabled: current !== null && logical !== null,
            isCustomMode: item.is_custom_mode === true,
            vrrSupported: item.vrr_supported === true,
            vrrEnabled: item.vrr_enabled === true,
            x: logical ? Number(logical.x) : 0,
            y: logical ? Number(logical.y) : 0,
            logicalWidth: logical ? Number(logical.width) : 0,
            logicalHeight: logical ? Number(logical.height) : 0,
            scale: logical ? Number(logical.scale) : 1,
            transform: logical ? normalizeTransform(logical.transform || "Normal") : "normal"
        };
    });
}

/* Number assignments persist in comments inside Sparrow's generated binds file,
 * keyed by physical display identity rather than a transient connector name. */
function parseMonitorNumbers(text) {
    var result = {};
    var source = String(text || "");
    var metadata = /^    \/\/ sparrow-monitor-number ("(?:\\.|[^"\\])*") ([1-9][0-9]*)$/gm;
    var match;
    while ((match = metadata.exec(source)) !== null) {
        try {
            var identity = JSON.parse(match[1]);
            var number = Number(match[2]);
            if (identity && Number.isInteger(number) && number > 0)
                result[identity] = number;
        } catch (e) {
            // Ignore malformed metadata; the generated-fragment validator rejects it on write.
        }
    }

    // Migrate the previous generated format, whose key-to-connector binding was
    // the only saved indication of a display's number.
    if (Object.keys(result).length === 0) {
        var legacy = /^    Super\+F([1-9][0-9]*) hotkey-overlay-title=("(?:\\.|[^"\\])*") \{ focus-monitor ("(?:\\.|[^"\\])*"); \}$/gm;
        while ((match = legacy.exec(source)) !== null) {
            try {
                var connector = JSON.parse(match[3]);
                var legacyNumber = Number(match[1]);
                if (connector && !Object.prototype.hasOwnProperty.call(result, connector))
                    result[connector] = legacyNumber;
            } catch (e) {
                // Ignore malformed legacy bindings.
            }
        }
    }
    return result;
}

function monitorNumberAssignments(outputs, previousText) {
    var parsed = parseMonitorNumbers(previousText);
    var result = Object.assign({}, parsed);
    (outputs || []).forEach(function (output) {
        var identity = String(output.identity || output.name);
        if (output.name !== identity && Object.prototype.hasOwnProperty.call(result, output.name)) {
            // If a previous generated file stored both connector and physical
            // identity keys, the actual F-key assignment is authoritative.
            result[identity] = result[output.name];
            delete result[output.name];
        }
    });
    var used = {};
    Object.keys(result).sort(lexical).forEach(function (identity) {
        var number = result[identity];
        if (!Number.isInteger(number) || number < 1 || used[number])
            delete result[identity];
        else
            used[number] = true;
    });

    var legacyByConnector = {};
    Object.keys(parsed).forEach(function (key) { legacyByConnector[key] = parsed[key]; });
    var connected = (outputs || []).filter(function (output) { return output.enabled; });
    connected.forEach(function (output) {
        var identity = String(output.identity || output.name);
        if (!Object.prototype.hasOwnProperty.call(result, identity)
                && Object.prototype.hasOwnProperty.call(legacyByConnector, output.name)) {
            var legacyNumber = legacyByConnector[output.name];
            if (!used[legacyNumber]) {
                result[identity] = legacyNumber;
                used[legacyNumber] = true;
            }
        }
    });

    // First-time setup follows the current visual order. Thereafter each number
    // is explicit and remains with that physical display.
    var visuallyOrdered = connected.slice().sort(function (a, b) {
        return Number(a.y) - Number(b.y) || Number(a.x) - Number(b.x)
            || lexical(String(a.name), String(b.name));
    });
    visuallyOrdered.forEach(function (output) {
        var identity = String(output.identity || output.name);
        if (Object.prototype.hasOwnProperty.call(result, identity))
            return;
        var number = 1;
        while (used[number]) number++;
        result[identity] = number;
        used[number] = true;
    });
    return result;
}

function numberedOutputs(outputs, assignments, previousText) {
    var numbers = assignments || monitorNumberAssignments(outputs, previousText);
    return (outputs || []).filter(function (output) { return output.enabled; }).slice().sort(function (a, b) {
        var an = numbers[String(a.identity || a.name)] || Number.MAX_SAFE_INTEGER;
        var bn = numbers[String(b.identity || b.name)] || Number.MAX_SAFE_INTEGER;
        return an - bn || lexical(String(a.identity || a.name), String(b.identity || b.name));
    }).map(function (output) {
        var copy = Object.assign({}, output);
        copy.displayNumber = numbers[String(output.identity || output.name)] || 0;
        return copy;
    });
}

function assignMonitorNumber(outputs, assignments, identity, number) {
    var result = Object.assign({}, assignments || {});
    var next = Number(number);
    if (!identity || !Number.isInteger(next) || next < 1)
        return { ok: false, error: "Choose a valid display number." };
    var selected = (outputs || []).find(function (output) {
        return String(output.identity || output.name) === String(identity);
    });
    if (!selected || !selected.enabled)
        return { ok: false, error: "The selected display is not connected and enabled." };
    var previous = result[String(identity)];
    var occupant = Object.keys(result).find(function (key) {
        return key !== String(identity) && result[key] === next;
    });
    result[String(identity)] = next;
    if (occupant && Number.isInteger(previous) && previous > 0)
        result[occupant] = previous;
    else if (occupant)
        delete result[occupant];
    return { ok: true, assignments: result, swappedIdentity: occupant || "" };
}

function logicalSize(mode, scale, transform) {
    if (!mode || !Number.isFinite(scale) || scale <= 0)
        return { width: 0, height: 0 };
    var swaps = ["90", "270", "flipped-90", "flipped-270"].indexOf(String(transform).toLowerCase()) !== -1;
    return {
        width: (swaps ? mode.h : mode.w) / scale,
        height: (swaps ? mode.w : mode.h) / scale
    };
}

function overlapError(rectangles) {
    for (var i = 0; i < rectangles.length; i++) {
        var a = rectangles[i];
        for (var j = i + 1; j < rectangles.length; j++) {
            var b = rectangles[j];
            if (a.x < b.x + b.width && a.x + a.width > b.x
                && a.y < b.y + b.height && a.y + a.height > b.y)
                return "Displays " + a.label + " and " + b.label + " overlap.";
        }
    }
    return "";
}

/* Snap a dragged output to the nearest legal edge-adjacent slot. The shorter
 * axis is fully aligned within the target's span, so the outputs share an edge
 * rather than overlap or leave a one-pixel gap. Candidates that collide with
 * any third output are discarded. */
function snapOutputPosition(rectangles, movingName, proposed) {
    var moving = (rectangles || []).find(function (r) {
        return r.name === movingName && r.enabled !== false;
    });
    if (!moving)
        return { ok: false, error: "The dragged display is not enabled." };

    var others = (rectangles || []).filter(function (r) {
        return r.enabled !== false && r.name !== movingName;
    });
    if (others.length === 0)
        return { ok: true, position: { x: Math.round(proposed.x), y: Math.round(proposed.y) }, target: "", side: "" };

    function clamp(value, low, high) {
        return Math.max(low, Math.min(high, value));
    }

    var candidates = [];
    others.forEach(function (target) {
        var alignY = clamp(proposed.y,
            Math.min(target.y, target.y + target.height - moving.height),
            Math.max(target.y, target.y + target.height - moving.height));
        var alignX = clamp(proposed.x,
            Math.min(target.x, target.x + target.width - moving.width),
            Math.max(target.x, target.x + target.width - moving.width));
        [
            { side: "left", x: Math.floor(target.x - moving.width), y: Math.round(alignY) },
            { side: "right", x: Math.ceil(target.x + target.width), y: Math.round(alignY) },
            { side: "above", x: Math.round(alignX), y: Math.floor(target.y - moving.height) },
            { side: "below", x: Math.round(alignX), y: Math.ceil(target.y + target.height) }
        ].forEach(function (position) {
            var rect = { name: movingName, label: moving.label, x: position.x, y: position.y,
                width: moving.width, height: moving.height };
            var collisions = others.filter(function (other) {
                return other.name !== target.name && overlapError([rect, other]).length > 0;
            });
            if (collisions.length > 0)
                return;
            var dx = position.x - proposed.x;
            var dy = position.y - proposed.y;
            candidates.push({ position: { x: position.x, y: position.y }, target: target.name,
                side: position.side, score: dx * dx + dy * dy });
        });
    });

    if (candidates.length === 0)
        return { ok: false, error: "No edge-adjacent position is free of other displays." };
    candidates.sort(function (a, b) {
        return a.score - b.score || lexical(a.target, b.target) || lexical(a.side, b.side);
    });
    return { ok: true, position: candidates[0].position,
        target: candidates[0].target, side: candidates[0].side };
}

function modeString(mode) {
    return mode.w + "x" + mode.h + "@" + (mode.refreshMilliHz / 1000).toFixed(3);
}

function kdlString(value) {
    return JSON.stringify(String(value));
}

/* Retain generated settings for disconnected displays, so using the same SSD
 * on a laptop does not erase the desktop's per-monitor configuration. */
function parseManagedOutputBlocks(text) {
    var result = {};
    var re = /^output ("(?:\\.|[^"\\])*") \{\n([\s\S]*?)^\}\s*$/gm;
    var match;
    while ((match = re.exec(String(text || ""))) !== null) {
        var identity;
        try { identity = JSON.parse(match[1]); } catch (e) { continue; }
        var body = match[2];
        var mode = /^    mode ("(?:\\.|[^"\\])*")$/m.exec(body);
        var scale = /^    scale ([0-9]+(?:\.[0-9]+)?)$/m.exec(body);
        var transform = /^    transform ("(?:\\.|[^"\\])*")$/m.exec(body);
        var position = /^    position x=(-?[0-9]+) y=(-?[0-9]+)$/m.exec(body);
        var off = /^    off$/m.test(body);
        if (!mode || !scale || !transform || !position)
            continue;
        try {
            result[identity] = {
                identity: identity,
                mode: JSON.parse(mode[1]),
                scale: Number(scale[1]),
                transform: JSON.parse(transform[1]),
                focusAtStartup: /^    focus-at-startup$/m.test(body),
                x: Number(position[1]),
                y: Number(position[2]),
                enabled: !off,
                block: match[0]
            };
        } catch (e) {
            // Ignore malformed stale state; Niri validation will still protect writes.
        }
    }
    return result;
}

function buildOutputFragment(outputs, settingsByName, previousText) {
    var connectedIdentities = {};
    var prepared = [];
    var minX = 0;
    var minY = 0;
    var positioned = (outputs || []).filter(function (output) {
        var settings = (settingsByName || {})[output.name] || {};
        return settings.enabled === undefined ? output.enabled : settings.enabled !== false;
    }).map(function (output) {
        var position = (settingsByName || {})[output.name] && (settingsByName || {})[output.name].position;
        return position || { x: output.x, y: output.y };
    });
    if (positioned.length > 0) {
        minX = Math.min.apply(null, positioned.map(function (p) { return Number(p.x); }));
        minY = Math.min.apply(null, positioned.map(function (p) { return Number(p.y); }));
    }

    (outputs || []).forEach(function (output) {
        var settings = (settingsByName || {})[output.name] || {};
        var current = output.currentMode;
        var mode = settings.mode || current;
        if (!mode)
            return;
        var transform = VALID_TRANSFORMS.indexOf(String(settings.transform || output.transform).toLowerCase()) >= 0
            ? String(settings.transform || output.transform).toLowerCase() : "normal";
        var scale = Number(settings.scale === undefined ? output.scale : settings.scale);
        if (!Number.isFinite(scale) || scale < 0.1 || scale > 10)
            return;
        var position = settings.position || { x: output.x, y: output.y };
        var size = logicalSize(mode, scale, transform);
        prepared.push({
            output: output,
            identity: String(output.identity || output.name),
            mode: mode,
            scale: scale,
            transform: transform,
            focusAtStartup: settings.focusAtStartup === true,
            x: Math.round(Number(position.x) - minX),
            y: Math.round(Number(position.y) - minY),
            width: size.width,
            height: size.height,
            enabled: settings.enabled === undefined ? output.enabled : settings.enabled !== false
        });
        connectedIdentities[String(output.identity || output.name)] = true;
    });

    var rectangles = prepared.filter(function (entry) { return entry.enabled; }).map(function (entry) {
        return { label: entry.output.label, x: entry.x, y: entry.y,
            width: entry.width, height: entry.height };
    });
    var overlap = overlapError(rectangles);
    if (overlap)
        return { ok: false, error: overlap, text: "" };
    if (prepared.filter(function (entry) { return entry.focusAtStartup; }).length > 1)
        return { ok: false, error: "Only one display can be focused at Niri startup.", text: "" };

    var lines = ["// Generated by Sparrow Display settings; do not edit."];
    prepared.sort(function (a, b) { return lexical(a.identity, b.identity); });
    prepared.forEach(function (entry) {
        lines.push("output " + kdlString(entry.identity) + " {");
        if (!entry.enabled)
            lines.push("    off");
        lines.push("    mode " + kdlString(modeString(entry.mode)));
        lines.push("    scale " + String(entry.scale));
        lines.push("    transform " + kdlString(entry.transform));
        if (entry.focusAtStartup)
            lines.push("    focus-at-startup");
        lines.push("    position x=" + entry.x + " y=" + entry.y);
        lines.push("}");
    });

    var old = parseManagedOutputBlocks(previousText);
    var hasConnectedOutputs = prepared.length > 0;
    Object.keys(old).sort(lexical).forEach(function (identity) {
        if (!connectedIdentities[identity]) {
            var retainedBlock = old[identity].block;
            if (hasConnectedOutputs)
                retainedBlock = retainedBlock.replace(/^    focus-at-startup\n/m, "");
            lines.push(retainedBlock);
        }
    });
    return { ok: true, error: "", text: lines.join("\n") + "\n" };
}

function monitorBinds(outputs, assignments, previousText) {
    var numbers = monitorNumberAssignments(outputs, previousText);
    Object.keys(assignments || {}).forEach(function (identity) {
        if (Number.isInteger(assignments[identity]) && assignments[identity] > 0)
            numbers[identity] = assignments[identity];
    });
    var ordered = numberedOutputs(outputs, numbers);
    var lines = ["// Generated by Sparrow from the current Niri output arrangement.", "binds {"];
    Object.keys(numbers).sort(function (a, b) {
        return numbers[a] - numbers[b] || lexical(a, b);
    }).forEach(function (identity) {
        lines.push("    // sparrow-monitor-number " + kdlString(identity) + " " + numbers[identity]);
    });
    for (var i = 0; i < ordered.length; i++) {
        var n = ordered[i].displayNumber;
        var key = "F" + n;
        lines.push("    Super+" + key + " hotkey-overlay-title=" + kdlString("Focus display " + n)
            + " { focus-monitor " + kdlString(ordered[i].name) + "; }");
        lines.push("    Super+Shift+" + key + " hotkey-overlay-title=" + kdlString("Move focused window to display " + n)
            + " { move-window-to-monitor " + kdlString(ordered[i].name) + "; }");
    }
    lines.push("}");
    return lines.join("\n") + "\n";
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        VALID_TRANSFORMS,
        normalizeTransform,
        parseNiri,
        parseMonitorNumbers,
        monitorNumberAssignments,
        assignMonitorNumber,
        numberedOutputs,
        snapOutputPosition,
        logicalSize,
        overlapError,
        modeString,
        parseManagedOutputBlocks,
        buildOutputFragment,
        monitorBinds
    };
}
