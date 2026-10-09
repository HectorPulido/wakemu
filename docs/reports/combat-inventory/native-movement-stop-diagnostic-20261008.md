# Intermittent own-player running animation after movement

The reported symptom is the local player Npers continuing its running animation after reaching the endpoint. No corresponding movement-stop defect is proven yet; no synthetic stop or endpoint correction has been added.

## Native routes inspected

World request13331 is **cnl**, not cny. cnl serializes movement mode plus aAT path. The server validates the previous approved route, commits its endpoint and publishes csR13852 only to other clients; the owner already animates the route locally. Native cgN forwards csR to beS.b(aAT), converting the path into amK. This is a complete path animation, not a start-only instruction requiring a separate stop packet.

Combat13624 carries the full origin/destination path; the production movement transaction follows it with action flush and actor state12873. Native path completion belongs to the local acS callback chain. World13530 is an authoritative position/path correction, not a universal movement-finished notification. Sending it after every route would interrupt legitimate replacement paths and stair traversal.

The world handler currently ignores zero-step13331. Native aAT.eY and csR accept a zero-step serialized path; however cnl's normal amK conversion rejects paths with fewer than two points. A streaming inspection of the current game-server log found **zero zero-step13331 requests** (15-byte body). This branch therefore does not explain the observed screenshot and has not been changed as a purported fix.

## Actual callback error found

The current client-console log contains a renderer exception at12:29:35.416 local time:

```
NullPointerException: bpq.Xi() because bAT.dTN() is null
cWt.eVE -> cWt.pathEnded -> acS.bvv
```

Original cWt is a move-to-interaction listener: it dereferences its interaction target when the path ends. acS.bvv clears its movement/path fields and updates movement state before iterating pathEnded listeners. That iteration has no per-listener exception boundary, so this error can prevent later listeners from running. It is an evidence-backed candidate for a callback problem, not a demonstrated explanation of the later Npers screenshot. No matching fresh pathEnded exception was found around the latest13:34 movement.

## Next reproduction evidence

For the next occurrence, preserve the exact local time and whether the walk began from an ordinary ground click or a monster/resource interaction. Correlate the preceding server `movement`/`movement_rejected`/`movement_redirected` records with the client renderer exception, the current actor ID, endpoint and latest native path. Compare a plain walk and an interrupted/replaced walk; keep the normal complete route. A fix must address the failing producer or callback, rather than adding periodic teleport/stop packets.

The13331 diagnostic now records movement mode, final direction, approved route point count and the fact that the owner animates locally without a path echo. A zero-step request emits `movement_zero_step_ignored` with its authoritative position instead of remaining invisible. These are bounded log fields only; AST syntax validation passed. No services, client code or movement behavior were changed.

## User-supplied time window and diagnostic endpoint

The user localized the symptom to about13:20 Bogotá /18:20 UTC. In the current client session, the±15-minute window contains no fresh renderer/pathEnded exception. Npers6 has a normal5-step route at18:18:55 from(-216,-41,0) to(-211,-39,0), followed by no new route until18:23:31. The capture around that first route contains scene12789 and other-actor13852 paths; it does not contain an owner13530 correction. The older12:29 interaction-target exception is therefore excluded as a demonstrated cause for this occurrence.

A bounded, read-only `/movement-diagnostic` endpoint has been added to the existing localhost CaptureAgent inspector for the next scheduled client launch. It snapshots the actual own player's ID/position, native movement mode, current path point count and indices, moving flag, animator implementation classes, pending path step counts, and at most16 path-end listeners. A cWt listener additionally records whether its interaction target still exists. It never sets movement/animation state, sends packets or invents an actor.

When the symptom is visible, read `.runtime/local/inspector.json` privately and request `/movement-diagnostic` using its existing `X-Inspector-Key` authorization; preserve the JSON without printing the secret. Capture once while running in place and again after an ordinary short walk. A null path plus false moving flag with a running pose isolates animator presentation; a remaining path/index identifies incomplete native path consumption. This evidence is required before a behavior patch can be justified.

## Confirmed stationary state and guarded idle fallback

The loaded inspector captured Npers6 at19:04:53 UTC after the user reported the14:00 Bogotá occurrence: current path and interpolation were null, all path indices were-1, `cjv=false`, no pending routes and zero path-end listeners. Native mode8 and normal adf/adB animators remained present. This rules out an unfinished authoritative path at that snapshot.

Original adf.b ignores the boolean returned by acX.eg at movement completion. For a player, beS.bvM constructs the current animation name plus `-Fin`. If that finish animation is unavailable and eg returns false, the current running pose survives even though acS has completed the path. The actual idle source is acX.bpT.

The new NativeMovementStop wrapper preserves the original finish attempt exactly once. A successful finish remains unchanged. Only a failed finish on the actual own player's movement object, with null path and false moving flag, permits one attempt to set the native bpT idle. It neither teleports nor changes server movement, NPCs, active paths or accepted finish animations. CaptureAgent replaces the existing invocation using identical receiver/argument stack consumption, avoiding the local-variable/frame defect that broke the earlier spell hook.

The endpoint now includes current animation `bkG`, native idle `bpT`, requested finish `bvM`, and a bounded last-fallback record (attempt count/time/actor/finish/idle/acceptance). These observations will establish whether the fallback handled the real occurrence after the combined validated client-agent reload. The pre-change snapshot proves stationarity; it does not prove the unavailable finish name, which the newly added fields must capture.

## Loaded-client check at19:31 UTC

A read-only query at19:31:32 still identifies the client capture that started18:56:30. Its movement endpoint lacks `bkG`, `bpT`, `bvM` and `idle_fallback`, proving it is the earlier diagnostic implementation without NativeMovementStop. Npers is stationary with no current path. Desbalizaje acceptance in this client does not validate the later movement fallback. One combined client-agent reload is still required before collecting actual finish/idle acceptance; no reload was performed by this investigation.
