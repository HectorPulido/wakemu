# Native constructor and encounter resource findings

This investigation covers references 3510, 5708, 2778, 5710 and 3174 from the original pending-under-10 validation. Native source is the installed-client extraction in `.runtime/monster-combat-extraction-20261010`, not inferred gameplay balance.

## Shared constructor correction

Reference 3510 (Chaos guardian plant) starts with state 3339 and its HP-minimum runner eWV877. The native runner checks its target PV and HP characteristic; it does not require an active combat turn or QI roster membership. The Python runner incorrectly required both registered source/target and active fight. It now resolves the actual detached actor through the existing audited constructor scope, allowing only SELF during placement. Registered placement actors and detached casts against another actor remain rejected. No actor is inserted into the roster to satisfy the runner.

Evidence: `.runtime/local/native-minimum-eWV-20261008.txt`, eWV.c offsets 0–90. Three new regression tests cover detached SELF retention, placement rejection, and other-target rejection. Together with the four existing minimum-resource tests, all seven passed.

## Zero-duration constructor states

Reference 5708 (Cybwork patético) starts with state 2345 (duration -1) and state 2354 (duration 0, realtime duration 0). The previous constructor gate rejected any duration different from -1, incorrectly treating zero as a positive finite clock. The gate now rejects only positive turn or realtime durations and preserves the actual native duration in the carrier context. No synthetic timeline is created. Four new tests and eight existing summon-initial-state tests passed.

Native eZk.Ty tests positive gtL/guH; eZk.bbX tests negative gtL/guH. Both return false for zero duration/realtime. Zero is therefore instantaneous without inherited delay, not an indefinite state. See `.runtime/local/state-registration-eZk.txt`, Ty and bbX, and `.runtime/local/native-Qe-current.txt`, g(PV), offsets 511–522.

Instantaneous state 2354 has child 106857 (group330) with trigger-mask slot 5 containing events 1033/1036. Native eZk.c offsets 215–263 pass the actual fyW PL object to each child and execute the child independently of the carrier retention result. The artificial Python rejection of subscriptions under an instantaneous state has been removed. Existing subscription-family/event-mask guards and the child’s own native retention decision remain mandatory. The existing owned-state-container mechanism preserves the actual PL snapshot only while an actual retained child owns it; no persistent carrier or fabricated timeline is created. A new regression verifies registration, absent carrier/ledger/wire payload, valid child-owned PL lifetime and rejection of a stale owner UID after its child is removed. Placement proof must count retained carriers rather than requiring one carrier per raw initial-state triple.

Relevant extracted state/effect rows are saved in `.runtime/monster-pending-activation-20261010/constructor-relevant-native.json`.

## Native resources and encounter actors

| Reference | Native resources | Blocking native requirement |
|---|---|---|
| 2778, white gobbly spirit | HP20, AP2, MP3, WP4 | Spell4019 costs AP4. Its HasState702 branch costs MP4, also greater than its native MP3. State702 is Enutrof's generic Perfórserker modifier, not an intrinsic initial state of this reference. |
| 5710, interdimensional Ordagova | HP23212, AP10, MP5, WP0 | Spell4641 costs MP6 and requires an AI-controlled caster on team0, excluding an ordinary team1 enemy fixture. Other owned spells can execute. |
| 3174, drago trainer | HP0, AP0, MP0, WP0; all native characteristic curves zero | Cannot initialize an ordinary living fighter. Its sprint/capture spell repertoire indicates an encounter actor; native encounter construction must supply the actual context before it can be tested as combat. |

These facts do not authorize inventing HP/AP/MP, reducing native spell costs, injecting unrelated states, or bypassing team criteria. A legitimate native effect or encounter initialization must provide any extra resource/context. Until that producer is proven and replayed, these cases cannot be classified as fully functional ordinary enemies.

## Replayable class-buff preparation

`server/tools/monster_class_buff_scenarios.py` supplies two declarative native recipes for testing conditional resource availability:

- AP: actual Xelor (breed5), level3, owned deck spell2839 (Devotion), native cost4WP, range1–3. It applies native state7545 at level3; its clock is target-based and expires at turn end with duration2.
- MP: actual Enutrof (breed3), level3, owned deck spell6324 (Acceleration), native cost2AP/1WP, range1–3, native non-enemy criterion. Its existing effect tree grants MP through children384825/384826, without fabricated resource assignments.

The helper requires an allied team0 recipient, a distinct controlled class caster, the actual validated owned deck and a supplied native LOS authority. It prepares and commits the normal server spell transaction with actual actor serialization, adopts the committed fight, and advances real turns to the recipient. It requires an observable resource increase that survives until the recipient's turn. It records native spell costs and before/after resource values. Four new ownership/failfast tests passed. End-to-end native replay remains part of the main cohort validation; these declarative recipes alone are not proof of a functional monster.

## Actual NPC tactical controller assignment

Native eGj.fqL delegates to eGZ.fqL, which reads mutable pHH; eGj.lx/eGZ.lx write the same value. The server already serializes the actual field through po.SX in both ordinary actor serializers. The historical fresh snapshot default was False for every actor, even when an activated ordinary NPC was controlled by the server tactical service. Consequently AI-only native criteria failed despite real server controller ownership.

The fresh placement boundary now assigns True only to an ordinary, uncontrolled NPC whose actual native-owned repertoire intersects the enabled activation policy at its actual level. Player-controlled actors, registered summons, actors with summon action books, unactivated references and out-of-range levels preserve their existing constructor path. This is a Wakemu controller assignment; it does not assert that every native creature is intrinsically AI-controlled. Later eYH325 effects remain authoritative because assignment occurs only on fresh initialization.

Initial placement rebuilds and uses actual monster stats for these assigned NPCs, including references without native initial states. This keeps po.SX consistent with the runtime value from the first published actor snapshot. Existing reconnect/session serialization already consumes the same actual field.

Evidence: `.runtime/local/native-summon-eGj.txt` fqL/lx; `.runtime/local/native-summon-eGz.txt` fqL/lx. Dispatch evidence: `combat_tactical_ai.NativeProvider` excludes controlled/dead actors; NPC casts use native abilities plus `imports_enabled` before selecting the imported runtime. Six new tests cover selection, exclusions, empty scope, fresh snapshot assignment and serializer authority.

## Delayed class buffs require production lifecycle callbacks

The earlier helper advanced the Fight state machine directly, which changes turns but does not deliver native event1001. Devotion's state7545 child340275 subscribes to that event and applies state6749 only when it runs. The class-buff scenario now advances through RuntimeMessages with the production turn-start and turn-end providers, expiration runtime and real turn acknowledgements. A delayed resource increase is accepted only after the recipient's actual turn-start callbacks have executed. No resources are assigned by the scenario.

Native replay confirmed the white gobbly spirit's AP increases from2 to5 at its actual turn start, with23 initialization packets,9 buff packets and39 lifecycle packets. The serializer follows the production registered-summon branch before ordinary actor serialization: Enutrof initialization legitimately creates a registered Drheller, which cannot be serialized as an ordinary monster.

## Remaining spell scene requirements

Spell4019 is a range1 enemy dispel, not a direct attack: effects105144 and332059 remove states2324 and7299 respectively. Both states are named "Alcanzado por los Espíritus". A full read-only state catalog scan found effect316169 applying2324 inside state2334, "Aparición de Tótems de Transformación". Its group316157 subscribes to fight-start event1003 and applies the state to its actual self target. No304 producer of7299 or of state2334 was found in that catalog. A legitimate encounter owner of2334 is therefore needed to construct this dispel scenario; an ordinary adjacent enemy without either state cannot satisfy the effect.

Spell4641 has range0–0 and four enemy-selector roots147070,144105,147071 and144304, all with native area `ring-1-3`. The selected cell must be the caster's cell, while a hostile actor must occupy the surrounding ring. Self exclusion is intentional. Selecting another cell correctly fails range validation; selecting self with no hostile actor in the ring correctly finds no eligible effect. The actual MP buff now succeeds, so this remaining condition concerns scene geometry and team ownership.
