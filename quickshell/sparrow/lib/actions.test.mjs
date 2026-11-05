import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {test} from 'node:test';
const A = createRequire(import.meta.url)('./action-engine.js');
const action = (type='desktop.dnd', value=true, extra={}) => ({version:1,type,params:{value},...extra});
function harness(options={}) {
    let time=0, value=options.value ?? false, revision=0, supported=true, writes=0;
    let inspectCallbacks=[], applyCallback=null;
    const backend={now:()=>time,
        inspect:(a,cb)=>options.delayInspect ? inspectCallbacks.push(cb) : cb({supported,value,revision}),
        apply:(a,cb)=>{writes++; if(options.delayApply) {applyCallback=cb; return;}
            if(options.fail) {cb({ok:false,accepted:true,message:'backend error'}); return;}
            if(!options.noConvergence) {value=a.params.value;revision++;}
            cb({ok:true,accepted:true,guarantee:options.guarantee || 'verified'});
        }};
    const engine=A.createEngine(backend);
    return {engine,backend,get writes(){return writes;},
        change:v=>{value=v;revision++;}, unavailable:()=>{supported=false;},
        advance:ms=>{time+=ms;engine.tick();},
        inspect:()=>inspectCallbacks.shift()({supported,value,revision}),
        complete:()=>{value=true;revision++;applyCallback({ok:true,accepted:true,guarantee:'verified'});}};
}
test('all initial types validate and serialize canonically',()=>{
    const values={'desktop.dnd':true,'desktop.keepAwake':false,'appearance.mode':'light',
        'wallpaper.output':'/images/a.png','audio.defaultOutput':'alsa_sink.serial',
        'audio.defaultInput':'alsa_source.serial','audio.outputVolume':0.5,'audio.outputMute':true};
    for(const [type,value] of Object.entries(values)) {
        const a=action(type,value);
        if(['wallpaper.output','audio.outputVolume','audio.outputMute'].includes(type)) a.params.target='device-identity';
        const v=A.validate(a);assert.equal(v.ok,true,type);
        assert.deepEqual(A.deserialize(A.serialize(a)),v);
        assert.ok(A.describe(v.action).includes(type));
        assert.ok(A.resource(v.action));
    }
});
test('strict schema rejects unknown versions/fields, commands, bad values and endings',()=>{
    for(const a of [action('shell.command','rm'),{...action(),version:2},{...action(),foo:true},
        action('desktop.dnd',1),action('appearance.mode','sepia'),action('audio.outputVolume',2),
        action('wallpaper.output','relative.png'), action('audio.defaultOutput','bad\nname'),
        {...action(),timeoutMs:0},{...action(),capturePrevious:'yes'},
        {...action(),ending:{policy:'restore'},capturePrevious:false},
        {...action(),ending:{policy:'set',value:'bad'}},
        {...action(),params:{value:true,command:'arbitrary'}},
        {...action(),ending:{policy:'keep',value:true}}]) assert.equal(A.validate(a).ok,false,JSON.stringify(a));
    assert.equal(A.deserialize('{').ok,false);
});
test('preview is passive, normalized and independent of returned mutations',()=>{
    const h=harness();let p;
    h.engine.preview(action(),r=>p=r);assert.equal(p.ok,true);assert.equal(h.writes,0);
    assert.equal(h.engine.busy(),false);assert.equal(p.observation.value,false);
    p.action.params.value=false;
    assert.equal(A.validate(action()).action.params.value,true);
});
test('unsupported preview and execution never dispatch',()=>{
    const h=harness();h.unavailable();let p;h.engine.preview(action(),r=>p=r);
    assert.equal(p.ok,false);const id=h.engine.execute(action());assert.equal(h.engine.result(id).status,'skipped');assert.equal(h.writes,0);
});
test('read-back verifies flags; results distinguish accepted and applied',()=>{
    const h=harness();const events=[];h.engine.onResult(r=>events.push(r));
    const id=h.engine.execute(action());const r=h.engine.result(id);
    assert.equal(r.status,'verified');assert.equal(r.accepted,true);assert.equal(r.applied,true);assert.equal(r.verified,true);
    assert.equal(events[0].accepted,false);assert.equal(events[1].accepted,true);assert.equal(events[1].applied,false);
});
test('acceptance without convergence times out without claiming application',()=>{
    const h=harness({noConvergence:true});const id=h.engine.execute(action());h.advance(15000);
    const r=h.engine.result(id);assert.equal(r.status,'timed_out');assert.equal(r.accepted,true);assert.equal(r.applied,false);assert.equal(r.verified,false);
});
test('helper completion plus saved-state read-back is degraded, not visually verified',()=>{
    const h=harness({guarantee:'degraded'});const id=h.engine.execute(action());assert.equal(h.engine.result(id).status,'degraded');assert.equal(h.engine.result(id).verified,false);
});
test('backend failures remain structured',()=>{
    const h=harness({fail:true});const id=h.engine.execute(action());assert.equal(h.engine.result(id).status,'failed');assert.equal(h.engine.result(id).message,'backend error');
});
test('inspection throws fail closed and setters throwing release gate',()=>{
    const h=harness();h.backend.inspect=()=>{throw Error('read failure');};let id=h.engine.execute(action());assert.equal(h.engine.result(id).status,'skipped');
    const other=harness();other.backend.apply=()=>{throw Error('write failure');};id=other.engine.execute(action());assert.equal(other.engine.result(id).status,'failed');assert.equal(other.engine.busy(),false);
});
test('cancellation before dispatch prevents late preflight side effects',()=>{
    const h=harness({delayInspect:true});const id=h.engine.execute(action());assert.equal(h.engine.cancel(id),true);h.inspect();assert.equal(h.writes,0);assert.equal(h.engine.result(id).status,'cancelled');
});
test('cannot cancel dispatch; timeout quarantines conflicts until drain',()=>{
    const h=harness({delayApply:true});const id=h.engine.execute(action());assert.equal(h.engine.cancel(id),false);
    h.advance(15000);assert.equal(h.engine.result(id).status,'timed_out');assert.equal(h.engine.busy(),false);assert.equal(h.engine.blocked().length,1);
    assert.equal(h.engine.result(h.engine.execute(action())).status,'skipped');h.complete();assert.equal(h.engine.busy(),false);
    assert.equal(h.engine.result(id).status,'timed_out');assert.equal(h.engine.result(id).ownershipToken,undefined);
});
test('late preflight cannot dispatch after deadline even without a timer tick',()=>{
    const h=harness({delayInspect:true});const id=h.engine.execute(action());h.advance(16000);h.inspect();assert.equal(h.writes,0);assert.equal(h.engine.result(id).status,'timed_out');
});
test('restore captures baseline, enforces lease and restores only once',()=>{
    const h=harness();const id=h.engine.execute(action('desktop.dnd',true,{ending:{policy:'restore'}}));
    const token=h.engine.result(id).ownershipToken;assert.ok(token);
    assert.equal(h.engine.result(h.engine.execute(action())).status,'skipped');
    const release=h.engine.release(token);assert.equal(h.engine.result(release).status,'verified');assert.equal(h.writes,2);
    h.engine.release(token);assert.equal(h.writes,2);
});
test('manual change including ABA invalidates restore and explicit ending',()=>{
    for(const ending of [{policy:'restore'},{policy:'set',value:false}]) {
        const h=harness();const id=h.engine.execute(action('desktop.dnd',true,{ending}));
        h.change(false);h.change(true);const release=h.engine.release(h.engine.result(id).ownershipToken);
        assert.equal(h.engine.result(release).status,'skipped');assert.equal(h.writes,1);
    }
});
test('explicit ending is guarded and applied; keep never retains a lease',()=>{
    const h=harness();const id=h.engine.execute(action('desktop.dnd',true,{ending:{policy:'set',value:false}}));
    assert.equal(h.engine.result(h.engine.release(h.engine.result(id).ownershipToken)).status,'verified');
    const keep=h.engine.execute(action());assert.equal(h.engine.result(keep).ownershipToken,undefined);
});
test('unavailable restoration target never writes',()=>{
    const h=harness();const id=h.engine.execute(action('desktop.dnd',true,{ending:{policy:'restore'}}));h.unavailable();
    assert.equal(h.engine.result(h.engine.release(h.engine.result(id).ownershipToken)).status,'skipped');assert.equal(h.writes,1);
});
test('busy release retains lease for retry; abandon explicitly relinquishes',()=>{
    const h=harness();const id=h.engine.execute(action('desktop.dnd',true,{ending:{policy:'restore'}}));const token=h.engine.result(id).ownershipToken;
    h.backend.apply=(a,cb)=>{};h.engine.execute(action('desktop.keepAwake'));assert.equal(h.engine.result(h.engine.release(token)).status,'skipped');
    h.engine.abandon(token);assert.equal(h.engine.result(h.engine.release(token)).status,'skipped');
});
test('caller-supplied observation creates editable actions or reports ambiguity',()=>{
    assert.equal(A.fromObserved('audio.outputVolume','sink',{supported:true,value:0.4}).ok,true);
    assert.equal(A.fromObserved('audio.defaultInput',undefined,{supported:true,ambiguous:true,value:'same'}).ok,false);
    assert.equal(A.fromObserved('wallpaper.output','monitor',{supported:false}).ok,false);
});
test('volume verification tolerance is bounded',()=>{
    const h=harness({value:0.501,noConvergence:true});const a=action('audio.outputVolume',0.5);a.params.target='sink';
    assert.equal(h.engine.result(h.engine.execute(a)).status,'verified');
});
test('audio selectors reject missing, ambiguous, streams, monitor sources and unready devices',()=>{
    const sink={name:'sink.serial',isStream:false,isSink:true,ready:true,audio:{volume:0.5}};
    const source={name:'source.serial',isStream:false,isSink:false,ready:true,audio:{}};
    assert.equal(A.resolveAudioNode([sink,source],sink.name,false).node,sink);
    assert.equal(A.resolveAudioNode([sink,source],source.name,true).node,source);
    assert.equal(A.resolveAudioNode([sink],source.name,true).node,null);
    assert.equal(A.resolveAudioNode([sink,{...sink}],sink.name,false).ambiguous,true);
    for(const patch of [{ready:false},{isStream:true},{audio:null},{isSink:false}])
        assert.equal(A.resolveAudioNode([{...sink,...patch}],sink.name,false).node,null);
    assert.equal(A.resolveAudioNode([{...source,name:'sink.monitor'}],'sink.monitor',true).node,null);
});
test('accepted progress is visible before completion and retained on timeout',()=>{
    const h=harness();h.backend.apply=(a,done,accepted)=>accepted();const id=h.engine.execute(action());
    assert.equal(h.engine.result(id).accepted,true);assert.equal(h.engine.result(id).applied,false);
    h.advance(15000);assert.equal(h.engine.result(id).status,'timed_out');assert.equal(h.engine.result(id).accepted,true);
});
test('resource disappearance after accepted command fails without ownership',()=>{
    const h=harness();h.backend.apply=(a,done)=>{h.unavailable();done({ok:true,accepted:true});};
    const id=h.engine.execute(action('desktop.dnd',true,{ending:{policy:'restore'}}));
    assert.equal(h.engine.result(id).status,'failed');assert.equal(h.engine.result(id).ownershipToken,undefined);
});

test('previous-state capture is returned without forcing an ending policy',()=>{
    const h=harness();const id=h.engine.execute(action('desktop.dnd',true,{capturePrevious:true}));
    assert.equal(h.engine.result(id).previous,false);assert.equal(h.engine.result(id).ownershipToken,undefined);
});
test('shared palette resource rejects overlapping wallpaper/appearance leases',()=>{
    const h=harness({value:'auto'});
    const first=h.engine.execute(action('appearance.mode','light',{ending:{policy:'restore'}}));
    assert.ok(h.engine.result(first).ownershipToken);
    const wallpaper=action('wallpaper.output','/images/a.png');wallpaper.params.target='monitor';
    assert.equal(h.engine.result(h.engine.execute(wallpaper)).status,'skipped');
    assert.deepEqual(A.resources(A.validate(wallpaper).action),['wallpaper:monitor','appearance.palette']);
});

test('timeout quarantine permits disjoint actions and protects shared palette effects',()=>{
    const h=harness({delayApply:true,value:'auto'});
    const id=h.engine.execute(action('appearance.mode','light',{timeoutMs:100}));h.advance(100);
    assert.equal(h.engine.result(id).recoveryRequired,true);assert.equal(h.engine.polling(),false);
    const wall=action('wallpaper.output','/test/a.png');wall.params.target='monitor';
    let preview;h.engine.preview(wall,p=>preview=p);assert.equal(preview.ok,false);assert.deepEqual(preview.blockedBy,[id]);
    assert.equal(h.engine.result(h.engine.execute(wall)).status,'skipped');
    h.backend.apply=(a,done)=>{h.change(a.params.value);done({ok:true,accepted:true,guarantee:'verified'});};
    assert.equal(h.engine.result(h.engine.execute(action('desktop.dnd',true))).status,'verified');
    assert.equal(h.engine.blocked().length,1);
});
test('bounded recovery never unlocks on missing, failed or timed-out evidence',()=>{
    const h=harness({delayApply:true});const id=h.engine.execute(action('desktop.dnd',true,{timeoutMs:100}));h.advance(100);
    let response;h.engine.recover(id,r=>response=r);assert.equal(response.recovered,false);
    h.backend.recover=(a,done)=>done({safe:false,message:'writer active'});
    h.engine.recover(id,r=>response=r);assert.equal(response.message,'writer active');
    let late;h.backend.recover=(a,done)=>{late=done;};h.engine.recover(id,r=>response=r);
    assert.equal(h.engine.polling(),true);h.advance(2000);assert.equal(response.recovered,false);
    late({safe:true});assert.equal(h.engine.blocked().length,1);
    h.backend.recover=(a,done)=>done({safe:true,message:'writer idle'});h.engine.recover(id,r=>response=r);
    assert.equal(response.recovered,true);assert.equal(h.engine.blocked().length,0);
    assert.equal(h.engine.result(id).status,'timed_out');assert.equal(h.engine.result(id).ownershipToken,undefined);
});
test('late backend drain completes a pending recovery check exactly once',()=>{
    const h=harness({delayApply:true});const id=h.engine.execute(action('desktop.dnd',true,{timeoutMs:100}));h.advance(100);
    let late, calls=0;h.backend.recover=(a,done)=>{late=done;};h.engine.recover(id,r=>{calls++;assert.equal(r.recovered,true);});
    h.complete();late({safe:true});h.advance(2000);assert.equal(calls,1);assert.equal(h.engine.blocked().length,0);
});
test('result observers can chain actions and cannot release a running backend by throwing',()=>{
    const h=harness();let chained;
    h.engine.onResult(r=>{if(r.id===1 && r.status==='verified') chained=h.engine.execute(action('desktop.keepAwake',true));});
    h.engine.execute(action());assert.equal(h.engine.result(chained).status,'verified');
    const other=harness({delayApply:true});other.backend.apply=(a,done,accepted)=>accepted();other.engine.onResult(()=>{throw Error('observer bug');});
    const original=console.warn;console.warn=()=>{};
    try { const id=other.engine.execute(action());assert.equal(other.engine.busy(),true);other.advance(15000);assert.equal(other.engine.blocked()[0].id,id); }
    finally {console.warn=original;}
});
test('restart expires leases without restoring state or accepting old tokens',()=>{
    const h=harness();const old=h.engine.execute(action('desktop.dnd',true,{ending:{policy:'restore'}}));const token=h.engine.result(old).ownershipToken;
    const restarted=A.createEngine(h.backend);assert.equal(restarted.blocked().length,0);assert.equal(restarted.busy(),false);
    assert.equal(restarted.result(restarted.release(token)).status,'skipped');assert.equal(h.writes,1);
    const id=restarted.execute(action('desktop.dnd',true,{ending:{policy:'restore'}}));const fresh=restarted.result(id).ownershipToken;
    assert.notEqual(fresh,token);restarted.release(token);assert.equal(h.writes,2);
    assert.equal(restarted.result(restarted.release(fresh)).status,'verified');assert.equal(h.writes,3);
});
test('serialization is deterministic and rejects non-string identifiers',()=>{
    const first={version:1,type:'wallpaper.output',params:{value:'/test/a.png',target:'monitor'}};
    const second={version:1,type:'wallpaper.output',params:{target:'monitor',value:'/test/a.png'}};
    assert.equal(A.serialize(first),A.serialize(second));
    assert.equal(A.validate({...action(),type:{toString:()=> 'desktop.dnd'}}).ok,false);
    assert.equal(A.resolveAudioNode([{name:'sink',isSink:true,audio:{},ready:true},{name:'sink',isSink:true,audio:{},ready:false}],'sink',false).ambiguous,true);
});
test('changed previous wallpaper is not restored even when selection ownership is intact',()=>{
    let value='/test/old.png', revision=0, fingerprint='old-bytes', writes=0;
    const backend={now:()=>0,inspect:(a,done)=>done({supported:true,value,revision,valueFingerprint:fingerprint,targetFingerprint:'changed-bytes'}),
        apply:(a,done)=>{writes++;value=a.params.value;revision++;fingerprint='new-bytes';done({ok:true,accepted:true});}};
    const e=A.createEngine(backend),a=action('wallpaper.output','/test/new.png',{ending:{policy:'restore'}});a.params.target='monitor';
    const id=e.execute(a),token=e.result(id).ownershipToken;
    assert.equal(e.result(e.release(token)).status,'skipped');assert.equal(writes,1);
});

test('double inspection callback cannot dispatch twice and observers can unsubscribe',()=>{
    const h=harness();let calls=0;
    const off=h.engine.onResult(()=>calls++);off();
    h.backend.inspect=(a,done)=>{done({supported:true,value:false,revision:0});done({supported:true,value:false,revision:0});};
    const id=h.engine.execute(action());assert.equal(h.writes,1);assert.equal(calls,0);
    h.advance(15000);assert.equal(h.engine.result(id).status,'timed_out');
});

test('partial application evidence never regresses after a later backend failure',()=>{
    const h=harness();h.backend.apply=(a,done,accepted)=>{accepted({applied:true});done({ok:false,accepted:false,message:'recolor refused'});};
    const id=h.engine.execute(action());const r=h.engine.result(id);
    assert.equal(r.status,'failed');assert.equal(r.accepted,true);assert.equal(r.applied,true);assert.equal(r.verified,false);
});
