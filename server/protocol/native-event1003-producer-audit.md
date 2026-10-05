# Event1003: audited subscription selection and inferred server lifecycle

The passive5051 listener316633 subscribes mask5=[1003]; its deferred child is
316634. This proves subscription, not when/how a source event is emitted.
No child is forced during initialization by this audit.

FindNativeEventConstant inventories all integer1003 constants AND all
BitSet/PV/Qf delivery callsites in wakfu-client.jar. The native engine classes
Qe/eZR/eXD reside in that JAR. The delivery inventory contains Qe.L,
eZR.L, eXD collision producers and interface/manager bridges only. None
provides an observed fight-start1003 producer. Qe.bbJ emits channel2, not6.
FindNativeDefinitionEventProducers loads every aNw definition and checks aZO;
the output native-event1003-definition-sources.json is empty.

The tempting ffE.d()==1003 is a different QM notification namespace.
big.dnN calls newffE after eGj.dnN reset. eGj.a(PN,List,boolean) also calls
newffE during effect-manager reset. big.a(QM) delegates to bkN.a(QM);
bkN's1003 case clears cached arrays and invalidates14 UI fields (states,
allStates, breed characteristic text/images, positive/negative states).
That complete branch invokes neither Qf nor BitSet event delivery.

eFl.pqQ and eFK.pyl contain1003 alongside1001/1002/1005/1028, confirming
it belongs to the catalog trigger/filter vocabulary. Those are lookup sets,
not producers. buP.FIGHT_START has ordinal2 and btX.FIGHT_STARTED quest
event27; neither establishes a mapping to effect trigger1003.

For a normal, nonreversed/nonglobal mask5 listener, Qi/eZX require delivery
channel6. This is a necessary selection rule, not evidence that fight start
emits channel6 or whether its source is absent. Existing source-absent native
rebinding preserves the listener's original actors. A future external source
must not manufacture a running-effect UID/value/container: Qf explicitly
accepts null Object/Qe, while current NativeEventSource models a real running
effect with UID. Timing/order relative to all fighter passive registrations,
recipient managers and source presence remain unaudited.

The initial audit added no automatic1003 producer. The subsequent explicit
server inference below adds one; no UID is fabricated and no predicate skipped.
The client evidence alone currently cannot establish the server's external
fight-start event contract. Native snippets were inspected with Java22 javap
for Qe,eZR,Qf,Qi,eGj,big,bkN,ffE,eFl,eFK,buP,btX. Reproduce the integer/
delivery inventory with FindNativeEventConstant and the empty definition
inventory with FindNativeDefinitionEventProducers1003.

## Explicit server implementation inference (2026-10-04)

The installed definition inventory now exports 717 subscriptions in
native-event1003-subscriptions.json, including 24 player-spell associations.
32 associated effect descriptions mention combat beginning (broader search:
combate + inicio/comienzo/principio). Examples span Elio149039, dodge-to-armor
283259/314932 and creature101102. These labels support a fight-start meaning;
they do not prove the producer callsite, exact recipients or source object.

The local official-creation snapshot-final capture includes 110 application
packets registering these native subscriptions. Examples326924 and416965
appear before fight-creation12847/start-action12892/new-table-turn13477.
The capture proves registration precedes that battle boundary. It does not
prove a null-source1003 delivery or identify every deferred child activation.

combat_start_events.deliver_fight_start implements an explicit server-side
inference: after all controlled class roots and NPC creation are installed,
at the first-turn boundary, deliver1003 through channels6/60/61 to each actual manager once.
These select disjoint normal/reversed/global subscriber categories; real5051
listener316633 is global and requires61. Channel6 alone cannot activate it.
The caller must attest the complete initialized roster. Channel6 is the native
normal mask5 selection channel; treating the external event source as null
is an implementation choice supported by Qf's null-source contract, rather
than an observed server source. No running-effect UID/value/container is
manufactured. NativeExternalEvent preserves the original listener actors and
sets native_trigger_context=None; ordinary criteria/probability/clone guards,
allocation, listener depletion and retained removal continue through replay.

Fight.ready already starts turn1 and increments only current.turn_count;
the producer verifies precisely that first-turn pattern. Invocation belongs
in the private initialization transaction before its first-turn packets are
published and before any client action. native_start_event_delivered is an
explicit Fight field and must survive checkpoints/reconnection. A failure
requires discarding the preview/outbox, including allocated clone UIDs.

The production preparation API now exposes
prepare_server_initialization(..., fight_start=False). False preserves the
installation-only audit. True runs the external producer on the returned
private preview and appends its private outbox. Controlled actors must all
have native_class_initializations markers; the caller attests the complete
created roster including ordinary NPCs. Generic Checkpoints.snapshot/read
already preserve every Fight field, including both markers; startup recovery
currently aborts interrupted fights rather than reconstructing Fight objects.

Validation:15 isolated replay/start tests passed, including disjoint channel
selection, null source actor preservation, clone UID allocation, whole-roster
and first-turn validation, and failure leaving the delivery marker unset.
Checkpoint test preserves both lifecycle and initialization markers. Real
5051 reaches state3231 and its native child197707(class20); after the generic
HP maximum handler was supplied, other starting innate conditions exposed
HasEffectWithActionId. Cross-breed real4795 similarly reaches native HP
maximum execution and then exposes IsBreed. These are retained as strict
end-to-end regression tests, not bypassed or reported successful prematurely.

Subsequent real-entry regression: Yopuka4795 level20 with fight_start=True
completed and increased HP maximum versus installation-only; source snapshot
was unchanged. The initialization suite completed5/6 tests successfully,
including start-failure rollback and existing relative-group installation.
The sole remaining error for Sacrógrito5051 was GetInstanceId after HP20,
HasEffectWithActionId and IsBreed support was supplied. This is an explicit
unresolved criterion guard, not failure to produce1003.

Final root verification after common criterion/HP/grant handlers were supplied:
initialization suite6/6 passed (session52600,11.467s), including real
Sacrógrito5051→3231, real Yopuka4795 maximum-HP increase, install-only default,
source snapshot rollback and failure discarding the private initialization.
No deferred child was forced. The producer boundary/source absence remain
explicit documented server-side inferences, rather than newly claimed client
callsites. This closes the previously noted starting-criterion blockers for
these regression cases; it does not claim complete breed/passive gameplay.
