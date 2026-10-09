# Class summon recognition across the lifecycle

The Cra Desbalizaje failure exposed a shared serialization bug: native fighter snapshots emitted `pW.Uh=0` for a registered summon. The native client applies this field through `eGn.zm → eGj.ly`, changing `dTE()` and causing `IsSummon` criteria to reject the actor. The correction belongs to the common registered-actor serializer, rather than individual classes or spells.

`registered_summon_stats` emits `pW.Uh=1` from the validated registration authority. Actor identity, profile, descriptor level, caster, current controller, current Fight object, obstacle and snapshot provenance must still match. Both ordinary live serializers now reject summon sources, preventing a compatibility caller from silently writing an ordinary `pW` section for a summon.

## Coverage inventory

| Boundary | Implementation | Recognition contract |
| --- | --- | --- |
| Fresh class creation, family307 | `combat_summon_creation.NativeSummonBuilder`, `combat_summon_handler`, `combat_summon_codec` | Common registered `bje` constructor records `is_summon=True`; native descriptor/effect introduces the actor. |
| Owned captured creation, family324 | `combat_captured_summon`, shared builder | Same registration; Symbiot source/slot ownership is additional provenance, not a replacement for summon identity. |
| Character copy, family1002 | `combat_character_copy_handler`, `combat_character_copy_codec`, shared builder | Native profile2382/type1 remains a summon; copied appearance, PA and allocated action UIDs do not turn it into a PC. |
| Temporary form, family933 | `combat_morph_spellbook`, existing actor/registration | Changes the current book/form of an existing actor; it does not create another durable PC or remove the existing summon registration. Subsequent stat routes still use registered recognition. |
| Postcommit resource/stat delivery | `combat_spell_commit`, caller's `current_combat_stats`/session serializer | Registered-actor branch precedes player/NPC branches and uses the committed Fight. |
| Client movement | `combat_movement_runtime.apply_client`, both world-server movement routes | Binary stats callback receives the moved candidate actor and its exact candidate Fight before commit; registered route avoids looking up the summon in the PC-only character map. |
| Actual turn/recovery | `combat_runtime_messages`, `CombatSessionAdapter.ready_transition` | Binary runtime serializer receives the actual current Fight; registered source emits the same summon flag. |
| Active reconnect/join | `CombatSessionAdapter.actor_payload` | Registered serializer precedes Store player lookup; complete retained effects use `active_actor_effects`. |
| Spectator snapshot | `combat_spectator_snapshot`, session actor payload | Uses the same actor serializer and current retained population; no independent false summon flag. |
| Death/retirement | `combat_summon_retirement`, `combat_summon_stats` | Registration and source stay retained. Only validated retirement permits obstacle `-1`; `pW.Uh` remains true. |
| Captured slot release | `combat_captured_roster_lifecycle`, retirement/checkpoint integration | Slot availability changes independently of summon recognition and keeps owner/descriptor identity. |
| Checkpoint/terminal snapshot | `fight_checkpoint_store.snapshot`, `fight_store` | Persist complete actors and registrations. Durable PC membership excludes only validated registered summons. |
| Disconnection/individual withdrawal | `combat_health`, `combat_pve_withdraw`, `combat_abandon` | PC membership remains separate; private continuation preserves real controller fields instead of clearing summon control. |
| Interrupted process recovery | `Checkpoints.recover_interrupted` | Marks interrupted fights aborted; it does not reconstruct or resume live actors. No resumable client-recognition claim is made. |

The constructor metadata currently covers 39 fresh class profiles, 33 owned captured profiles and the separately attested copied profile2382. These are source domains, not 39 + 33 + 1 independently completed gameplay tests. Dynamic captured ownership supplies its actual profile; monster AI and unrestricted monster ability catalogs are outside this work.

Ordinary player/world NPC serializers intentionally emit false. Legacy melee, NPC and class compatibility callers cannot serialize a summon through those ordinary live wrappers; they must provide the actual registered Fight route. There is no fallback based on positive actor IDs, account ownership, team, appearance or class name.

The remaining compatibility call sites are `combat_melee`, `combat_execute`, `combat_npc_attack`, `combat_iop_cast` and `combat_xelor_cast`. Their execution paths require the PC character identity and supplied world-monster identity before serialization. Current created class actors are absent from that world-monster source map, so these helpers are not the normal controlled-summon action path. They retain the strict ordinary serializer safeguard. General class actions use `prepare_server_spell`/registered source authority instead. The real reachable client-movement routes previously bypassed this authority and are now connected to it; simply rejecting those movements would not have repaired functionality.

## Reusable verification and manual acceptance

Focused tests cover the native `pW` byte, current actor/Fight identity, ordinary-route rejection, retirement signed obstacle, actual turn/recovery, complete active effects and PC durable roster separation. Tests are delegated to the team's validation owner; full gameplay coverage is tracked separately in the class reports.

For any class with a summon: create it through the legitimate class action; inspect/target it with an action whose native criterion requires `IsSummon`; advance to its actual turn where native eligibility permits; perform an owned action using its client-provided UID; reconnect while it survives; repeat the summon-target action; then use the legitimate removal/death sequence and verify its QI occupancy/turn disappears. Finish the encounter and return to the world. Expected: no recognition flip, foreign UID acceptance, stale roster checkpoint, extra durable participant or repeat terminal reward. A summon with no native turn/action book should be checked through targeting and removal, without fabricating a playable turn.

Cra Desbalizaje is manually confirmed by the user on r31. Osa's latest restored captured-actor attack report records a real controlled turn and committed attack, but reports source instability; it is not a sealed full-class acceptance result. A 1002 allocated-book cast and independent retirement stress were verified earlier; these do not establish native automatic expiry. No new deployment, service restart or live DB mutation was performed for this review.
