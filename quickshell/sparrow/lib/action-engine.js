/* Shared action contract. No QML, filesystem, timers, or desktop side effects here. */
var VERSION = 1;
var TYPES = {
    "desktop.dnd": "boolean", "desktop.keepAwake": "boolean",
    "appearance.mode": "appearance", "wallpaper.output": "wallpaper",
    "audio.defaultOutput": "device", "audio.defaultInput": "device",
    "audio.outputVolume": "volume", "audio.outputMute": "mute"
};
function copy(value) { return JSON.parse(JSON.stringify(value)); }
function object(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function keys(value, allowed) { return Object.keys(value).every(function(k) { return allowed.indexOf(k) >= 0; }); }
function text(value) { return typeof value === "string" && value.length > 0 && !/[\x00-\x1f]/.test(value); }
function valueValid(kind, value) {
    if (kind === "boolean" || kind === "mute") return typeof value === "boolean";
    if (kind === "volume") return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
    if (kind === "appearance") return ["auto", "light", "dark"].indexOf(value) >= 0;
    return text(value) && (kind !== "wallpaper" || value[0] === "/");
}
function validate(input) {
    if (!object(input) || !keys(input, ["version", "type", "params", "ending", "capturePrevious", "timeoutMs"]))
        return {ok:false, message:"Expected a versioned action object with known fields"};
    if (input.version !== VERSION || typeof input.type !== "string" || !Object.prototype.hasOwnProperty.call(TYPES, input.type))
        return {ok:false, message:"Unsupported schema version or action type"};
    var kind = TYPES[input.type], p = input.params;
    var targeted = ["volume", "mute", "wallpaper"].indexOf(kind) >= 0;
    if (!object(p) || !keys(p, targeted ? ["target", "value"] : ["value"])
            || !valueValid(kind, p.value) || (targeted && !text(p.target)))
        return {ok:false, message:"Invalid parameters for " + input.type};
    var ending = input.ending === undefined ? {policy:"keep"} : input.ending;
    if (!object(ending) || !keys(ending, ["policy", "value"])
            || ["keep", "restore", "set"].indexOf(ending.policy) < 0
            || (ending.policy === "set" ? !valueValid(kind, ending.value) : ending.value !== undefined))
        return {ok:false, message:"Invalid ending policy/value"};
    if (input.capturePrevious !== undefined && typeof input.capturePrevious !== "boolean")
        return {ok:false, message:"capturePrevious must be boolean"};
    if (ending.policy === "restore" && input.capturePrevious === false)
        return {ok:false, message:"Restore requires previous state capture"};
    var timeout = input.timeoutMs === undefined ? 15000 : input.timeoutMs;
    if (!Number.isInteger(timeout) || timeout < 100 || timeout > 120000)
        return {ok:false, message:"timeoutMs must be 100..120000"};
    return {ok:true, action:{version:VERSION, type:input.type,
        params:targeted ? {target:p.target, value:p.value} : {value:p.value},
        ending:ending.policy === "set" ? {policy:"set", value:ending.value} : {policy:ending.policy},
        capturePrevious:input.capturePrevious === true || ending.policy === "restore", timeoutMs:timeout}};
}
function serialize(action) {
    var v = validate(action); if (!v.ok) throw new Error(v.message); return JSON.stringify(v.action);
}
function deserialize(json) { try { return validate(JSON.parse(json)); } catch (e) { return {ok:false, message:"Invalid JSON"}; } }
function resource(a) {
    if (a.type === "wallpaper.output") return "wallpaper:" + a.params.target;
    if (a.type === "audio.outputVolume") return "audio:output:" + a.params.target + ":volume";
    if (a.type === "audio.outputMute") return "audio:output:" + a.params.target + ":mute";
    return a.type;
}
function resources(a) {
    var list = [resource(a)];
    if (a.type === "wallpaper.output" || a.type === "appearance.mode") list.push("appearance.palette");
    return list;
}
function describe(a) { return a.type + (a.params.target ? " (" + a.params.target + ")" : "") + " → " + String(a.params.value); }
function equal(a, b, type) {
    return type === "audio.outputVolume" ? typeof a === "number" && Math.abs(a-b) <= 0.005 : a === b;
}
// This converts one caller-supplied observation, never collects a snapshot.
function fromObserved(type, target, observation) {
    if (!observation || observation.ambiguous || !observation.supported)
        return {ok:false, message:observation && observation.ambiguous ? "Ambiguous observation" : "Unsupported observation"};
    var params = {value:observation.value}; if (target !== undefined) params.target = target;
    return validate({version:VERSION, type:type, params:params});
}
// PipeWire names are durable selectors only when unique in the current graph.
function resolveAudioNode(nodes, name, input) {
    var matches = nodes.filter(function(n) {
        return n && n.name === name && !n.isStream && n.isSink !== input
            && (!input || !/monitor/i.test(n.name || "")) && n.audio;
    });
    return {node:matches.length === 1 && matches[0].ready ? matches[0] : null, ambiguous:matches.length > 1};
}
/* Backend: inspect(action, callback), apply(action, callback), now().
 * inspect is passive and returns {supported,value,revision,message}; revision is
 * an opaque resource generation, including relevant dependency generations.
 * apply reports acceptance/completion separately; inspect verifies convergence.
 */
function createEngine(backend) {
    var serial = 0, active = null, owners = {}, results = {}, listeners = [], quarantine = {};
    var instance = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
    function emit(r) {
        results[r.id] = copy(r);
        listeners.slice().forEach(function(f) {
            try { f(copy(r)); }
            catch(e) { console.warn("Sparrow Actions result observer failed: " + String(e)); }
        });
    }
    function blockers(a) {
        return Object.keys(quarantine).filter(function(id) {
            return resources(quarantine[id].action).some(function(r) { return resources(a).indexOf(r) >= 0; });
        }).map(Number);
    }
    function clearQuarantine(job, reason) {
        if (quarantine[job.result.id] !== job) return;
        delete quarantine[job.result.id];
        var request=job.recovering;
        job.recovering=null;
        job.result.recoveryRequired = false;
        job.result.recovery = reason;
        emit(job.result); // terminal status never changes, only recovery evidence
        if (request) request.callback({recovered:true, message:reason});
    }
    function finish(job, status, message) {
        if (job.finished) return;
        job.finished = true;
        job.result.status = status; job.result.message = message || "";
        if (status === "timed_out" && job.dispatched && !job.backendDone) {
            quarantine[job.result.id] = job;
            job.result.recoveryRequired = true;
            job.result.recovery = "Conflicting resources quarantined; use recover(id, callback) to check quiescence. If still running, inspect/restart the owning Sparrow service after approval.";
        }
        if (active === job) active = null;
        emit(job.result);
    }
    function expired(job) {
        if (backend.now() < job.deadline) return false;
        finish(job,"timed_out","Deadline exceeded; dispatched effects may still finish"); return true;
    }
    function inspect(a, callback) {
        var called = false;
        function done(s) {
            if (called) return;
            called = true;
            callback(s && typeof s.supported === "boolean" ? s : {supported:false, message:"Invalid backend observation"});
        }
        try { backend.inspect(a, done); }
        catch(e) { if (!called) done({supported:false, message:String(e)}); else throw e; }
    }
    function preview(input, callback) {
        var v = validate(input);
        if (!v.ok) { callback(v); return; }
        inspect(v.action, function(s) {
            var blocked = blockers(v.action);
            callback({ok:s.supported && blocked.length === 0, action:v.action,
                resource:resource(v.action), resources:resources(v.action), description:describe(v.action),
                blockedBy:blocked, observation:copy(s)});
        });
    }
    function owns(record, observation) {
        return observation.supported && record.revision === observation.revision
            && equal(record.value, observation.value, record.action.type);
    }
    function check(job) {
        if (job.finished || job.checking) return;
        job.checking = true;
        inspect(job.action, function(s) {
            job.checking = false;
            if (job.finished || expired(job)) return;
            if (!s.supported) { finish(job, "failed", s.message || "Resource disappeared"); return; }
            if (!equal(s.value, job.action.params.value, job.action.type)) return;
            job.result.applied = true;
            job.result.verified = job.guarantee === "verified";
            if (job.action.ending.policy !== "keep") {
                var token = "owner-" + instance + "-" + job.result.id;
                owners[resource(job.action)] = {token:token, action:copy(job.action),
                    value:s.value, revision:s.revision, previous:job.previous, previousFingerprint:job.previousFingerprint};
                job.result.ownershipToken = token;
            }
            finish(job, job.result.verified ? "verified" : "degraded", job.guarantee === "verified"
                ? "Observed requested state" : "Helper completed and stored state matches; visible desktop not verified");
        });
    }
    function execute(input, guard) {
        var id = ++serial, r = {id:id, status:"running", accepted:false, applied:false, verified:false};
        var v = validate(input);
        if (!v.ok) { r.status="failed"; r.message=v.message; emit(r); return id; }
        if (active) { r.status="skipped"; r.message="Another backend operation is active"; emit(r); return id; }
        var a=v.action, key=resource(a);
        r.resource=key; r.resources=resources(a);
        var blocked=blockers(a);
        if (blocked.length) {
            r.status="skipped"; r.blockedBy=blocked;
            r.message="Resources quarantined by timed-out operation; call recover(id, callback)";
            emit(r); return id;
        }
        var conflicts = Object.keys(owners).some(function(k) {
            return owners[k] !== guard && resources(owners[k].action).some(function(r) { return resources(a).indexOf(r) >= 0; });
        });
        if (conflicts) { r.status="skipped"; r.message="Resource has an ownership lease; release it first"; emit(r); return id; }
        var job={action:a,result:r,deadline:backend.now()+a.timeoutMs,finished:false,dispatched:false,backendDone:false};
        active=job; emit(r);
        inspect(a, function(s) {
            if (job.finished || expired(job)) return;
            if (!s.supported) { finish(job,"skipped",s.message || "Unsupported capability"); return; }
            if (guard && (owners[key] !== guard || !owns(guard,s)
                    || (guard.action.ending.policy === "restore" && guard.previousFingerprint !== undefined
                        && guard.previousFingerprint !== s.targetFingerprint))) {
                if (owners[key] === guard) delete owners[key];
                finish(job,"skipped","Ownership lost or resource changed"); return;
            }
            if (a.capturePrevious && !valueValid(TYPES[a.type],s.value)) {
                finish(job,"skipped","Previous state cannot be restored safely"); return;
            }
            job.previous=a.capturePrevious ? s.value : undefined;
            job.previousFingerprint=s.valueFingerprint;
            if (a.capturePrevious) job.result.previous=s.value;
            // Release only after the guarded read immediately preceding dispatch.
            if (guard) delete owners[key];
            job.dispatched=true;
            try {
                backend.apply(a, function(outcome) {
                    if (job.backendDone) return;
                    job.backendDone=true;
                    if (job.finished) { clearQuarantine(job, "Backend completed; no ownership acquired"); return; }
                    if (expired(job)) return;
                    job.result.accepted=job.result.accepted || outcome.accepted === true;
                    job.result.applied=job.result.applied || outcome.applied === true;
                    if (!outcome.ok) { finish(job,"failed",outcome.message || "Backend failed; state may have changed"); return; }
                    job.guarantee=outcome.guarantee || "degraded";
                    emit(job.result); check(job);
                }, function(progress) {
                    if (!job.finished) {
                        job.result.accepted=true;
                        if (progress && progress.applied === true) job.result.applied=true;
                        emit(job.result);
                    }
                });
            } catch(e) { job.backendDone=true; finish(job,"failed",String(e)); }
        });
        return id;
    }
    function release(token) {
        var record=null;
        Object.keys(owners).some(function(k) { if (owners[k].token===token) {record=owners[k]; return true;} return false; });
        if (!record) {
            var result={id:++serial,status:"skipped",accepted:false,applied:false,verified:false,
                message:"Unknown or expired ownership token"}; emit(result); return result.id;
        }
        var a=copy(record.action), ending=a.ending;
        if (ending.policy === "keep") { delete owners[resource(a)]; return null; }
        a.params.value=ending.policy === "restore" ? record.previous : ending.value;
        a.ending={policy:"keep"}; a.capturePrevious=false;
        return execute(a, record);
    }
    function recover(id, callback) {
        var job = quarantine[id];
        if (!job) { callback({recovered:false, message:"No quarantined operation with this ID"}); return; }
        if (job.recovering) { callback({recovered:false, message:"Recovery check already pending"}); return; }
        if (!backend.recover) { callback({recovered:false, message:job.result.recovery}); return; }
        job.recovering = {deadline:backend.now()+2000, callback:callback};
        var request = job.recovering;
        function done(evidence) {
            if (job.recovering !== request) return;
            job.recovering = null;
            if (quarantine[id] !== job) { callback({recovered:true, message:"Backend already drained"}); return; }
            if (backend.now() >= request.deadline) { callback({recovered:false, message:"Recovery check timed out; resources remain quarantined"}); return; }
            if (evidence && evidence.safe === true) clearQuarantine(job, "Quiescence confirmed by backend recovery check");
            callback({recovered:!!(evidence && evidence.safe), message:evidence && evidence.message || job.result.recovery});
        }
        try { backend.recover(job.action, done); }
        catch(e) { done({safe:false, message:String(e)}); }
    }
    return {
        preview:preview, execute:execute, release:release, recover:recover,
        blocked:function() { return Object.keys(quarantine).map(function(id) {
            return {id:Number(id), resources:resources(quarantine[id].action), message:quarantine[id].result.recovery};
        }); },
        onResult:function(f) { listeners.push(f); return function() { listeners=listeners.filter(function(item) { return item!==f; }); }; },
        result:function(id) { return results[id] ? copy(results[id]) : null; },
        forget:function(id) { if ((!active || active.result.id!==id) && !quarantine[id]) delete results[id]; },
        abandon:function(token) { Object.keys(owners).forEach(function(k) { if(owners[k].token===token) delete owners[k]; }); },
        cancel:function(id) {
            if (!active || active.result.id!==id || active.finished) return false;
            if (active.dispatched) return false; // non-interruptible setters/transactions
            finish(active,"cancelled","Cancelled before dispatch"); return true;
        },
        tick:function() {
            Object.keys(quarantine).forEach(function(id) {
                var job=quarantine[id], request=job.recovering;
                if (request && backend.now()>=request.deadline) {
                    job.recovering=null;
                    request.callback({recovered:false,message:"Recovery check timed out; resources remain quarantined"});
                }
            });
            if (!active || active.finished) return;
            if (backend.now()>=active.deadline) { finish(active,"timed_out","Deadline exceeded; dispatched effects may still finish"); return; }
            if (active.backendDone) check(active);
        },
        busy:function() { return active!==null; },
        polling:function() { return active!==null || Object.keys(quarantine).some(function(id) { return !!quarantine[id].recovering; }); }
    };
}
if (typeof module !== "undefined") module.exports={VERSION:VERSION,TYPES:TYPES,validate:validate,serialize:serialize,
    deserialize:deserialize,resource:resource,resources:resources,describe:describe,fromObserved:fromObserved,resolveAudioNode:resolveAudioNode,createEngine:createEngine};
