# Original Otomai dialogue speaker identity recovered

**The original protector424 is bound directly to captured NPC actor
-1706442046308330.** This is a published native identity join, independent of
matching localized names, graphics or coordinates. Consequently the captured
PROTECTOR speaker424 response must not be rejected simply because its identity
is not the clicked NPC's actor ID.

`sniffer/java/AuditCapturedProtectorActorLinks.java` reads the original full
capture, decodes every13974 world snapshot using native `csW.dp`, then decodes
its `eEY()` protector records with native `wW.aG`. Every record must consume its
complete buffer. Seven world snapshots contain three protector records; all
three publish `wW.aiQ=424`, `wW.aiS.ajf=-1706442046308330`.
Detailed snapshots are preserved in
`.runtime/local/native-captured-otomai-protector-links.json`.

The installed native consumer provides the semantic proof:

1. `ciu` consumes13974 `csW.eEY` records through the protector serializer and
   registers them with `bLU`.
2. `bMa.b(bLO,wX)` calls `bLO.lH(wX.ajf)`; `bLO.cXS()` returns this actor ID.
3. `bje.dso()` searches registered protectors; its predicate is exactly
   `protector.cXS() == npc.Sn()`. `bje.dsH()` returns this associated protector.
4. Dialogue enum `eUF` identifies wire type1 as PROTECTOR and type2 as NPC.
   `bpb.dCW` resolves a PROTECTOR speaker ID through `bLU.Zo((int)speakerId)`;
   NPC speakers instead resolve the actor registry `bio.jv(actorId)`.

Thus a general qualifier can validate a protector speaker by requiring the
original snapshot's exact protector-to-clicked-actor mapping. It must preserve
failure for missing or contradictory mappings and must not substitute a name
match or accept every protector speaker.

The parent capture audit independently identifies the same actor as breed5459,
map1385 `(20,17,1)`, clicked through action1244 at frame1603, confirmed by the
12421 actor/action echo at frame1605, and opening12969 root5772 with speaker
PROTECTOR424 at frame1606. This report supplies the previously missing identity
bridge; the parent owns request/response qualification and any implementation.

## Independent native placement consistency

`AuditNpcProtectorIdentity.java` snapshots native `aMD` record424 immediately
inside its loader callback (the loader reuses mutable rows). It records native
XYZ `(ctJ,ctK,cki)=(20,17,1)`. `bLU.If` explicitly passes these fields to
`bLO.a(int,int,short)`, which writes the protector's position. Its other metadata
includes `cpi=22193`, `ctH=93601`; neither is breed5459.
The independently decoded map1385 POI also has protector marker12353,
`chi=3/chj=424`, at `(20,17,1)`. These corroborate the placement but are not used
as substitutes for the published actor identity bridge.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/AuditCapturedProtectorActorLinks.java
java -cp '.runtime/local/classes:client/lib/*' AuditCapturedProtectorActorLinks .runtime/official-creation/captures/2026-10-03T06-56-20.133993Z-13a6e59e/snapshot-final/decoded/frames.jsonl .runtime/local/native-captured-otomai-protector-links.json
```

No server source, client asset, database or service was changed. This audit
recovers one exact original initial binding through a general native speaker
identity contract; it does not invent unobserved dialogue transitions.

## Runtime publication requirement

Current `native_transports.bootstrap` publishes an empty protector list in13974.
A faithful PROTECTOR424 conversation requires publishing the protector record
with its actor ID rebound to the actual server NPC. `dcj` can lazily recover a
protector name through `bLU.If`, but choice criterion targets use `bLU.Zo`, and
actor locking uses the associated protector actor. Empty publication therefore
must not be treated as fully equivalent. Preserve wire speaker type1 and its
protector definition identity; do not replace it with type2 to avoid registration.
The capture oracle retains exact `record_base64` for every qualified protector
record. Rebinding must preserve native record layout and validate decoding.

## Minimal publication verified

`VerifyMinimalProtectorPublication.java` proves native world loading via
`cdH.bla(); cdH.exY().dW(...maps/data.jar!/worlds.lib)` registers territory93601
with world/map1385. A minimal41-byte `wW` retains only protector ID424,
`aiR` original native/current nation0 and territory93601, and `aiS` appearance
22193 and rebound actor ID. All ecology, economy and other optional sections
are absent. Native `wW` consumes it completely; native `bMd` reconstructs the
actor link; `bLU.c` registers it and `bLU.Zo424` returns the linked protector;
`csW` decodes its one-entry protector list. All four checks pass.

The optional-section null guards in native `fxa.a(ByteBuffer,P)` permit omitting
unrelated state. However, omitting `aiR` leaves the territory null and registration
fails in `fwR.b`; that rejected minimal attempt must not be used. The successful
minimal record and native field snapshot are in
`.runtime/local/native-minimal-protector424-publication.json`.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/VerifyMinimalProtectorPublication.java
java -cp '.runtime/local/classes:client/lib/*' VerifyMinimalProtectorPublication -1706442046308330 .runtime/local/native-minimal-protector424-publication.json
```

Earlier references to93601 as a graphic ID are incorrect: native `fxa` resolves
`xh.ajE` through `fxf.Zp`, proving it is the territory identity. Appearance22193
is independently stored in `wX.aje`.

## Qualified server implementation (offline)

Additive migration142 stores the captured speaker type1/identity424 and its
protector-to-actor/map/territory/appearance contract. `npc_protectors.speaker`
validates the original actor contract and exact protector join before returning
the wire identity. `npc_protectors.record` emits the native41-byte minimal
record; `bootstrap_records` limits publication to public map1385 and an enabled
validated scene. Missing and contradictory joins fail closed. `npc_world.begin`
opens root5772 with type1/424 and rechecks owned objective10596 and map criteria
on each choice; only the observed initial closing choice is authorized.

`npc_world.matches_open_request` resolves exact `(speaker_type,speaker_id,node)`
for native12535 without confusing protector IDs with exploration actor IDs.
Existing NPC type2 packets remain unchanged. The root integrates bootstrap and
dispatcher hooks. Deployment and graphical acceptance remain separate gates.

## Independent offline qualification142

Luna ran the bounded current-source NPC gate:

```sh
PYTHONPATH=server:server/tests python3 -m unittest test_npc_protectors test_npc_world test_npc_dialogue test_npc_objective_facts test_npc_facts_dispatch test_npc_capture_scene test_npc_captured_world test_captured_npc_dialogues
```

All32 tests passed with no skips or errors. The separate12-test original capture
baseline also passed; it is a subset, not44 distinct tests. The six new protector
methods include exact record bytes, missing/contradictory/forged actor joins,
duplicate protector rejection, native12535 exact speaker matching, owned
objective10596 revalidation, original close choice and unchanged NPCspeaker2.

The original Java oracle independently passed `wW` decoding, `bMd` actor linkage,
`bLU` registration and `csW` protector-list decoding. Python and Java records
are byte-identical, SHA256
`609eee7b2033f9c9bb5e8d93710955ba6452b2826f108d6352c26f008fc6620d`.
Private evidence: `.runtime/local/npc-protector-validation/native-result.json`.
After dependency recovery, three new PostgreSQL methods plus the existing
three NPC PostgreSQL methods passed6/6 in7.995s against an isolated schema
with all142 migrations. Current helper/test/schema hashes matched the private
test snapshot, and per-test schema cleanup preserved the pre-existing schema
count8→8. No runtime public schema was used.
No services, client assets or runtime database were changed by this worker.
The root separately validates actual bootstrap/dispatcher integration.

An exhaustive scan of all original creation-capture12969 initial responses finds
exactly one non-NPC speaker: frame1606/root5772/type1/424. Therefore there is no
additional withheld protector initial root in that capture to activate. Mod'Ulo
and B.Toven still require an accredited action-to-root join; matching text alone
has not been promoted to a binding.

## Manual acceptance after full deployment

1. Use a character with objective10596 still incomplete; a new character has no
   completed owned objective fact. In normal chat run `!tp 1385 20 17 1`.
2. Otomai must appear at the original location and offer its native first dialog
   action1244. Open it: root5772 must identify the protector correctly and avoid
   an unknown/blank speaker or stuck actor lock.
3. Choose the native closing option13288, reopen, move away and reconnect.
   Closing must release the conversation; opening outside range must fail.
   No quest progress, item or reward is granted by this initial-scene adapter.
4. Existing Huly/Kheperalia on1385, Airyna on1388 and Grugal on1387 retain their
   native initial conversations. Foreign/private map instances must not publish
   protector424, and the quarantined map1134 trial actors remain absent.

Graphical acceptance is pending, separately from native decoding and pure tests.
