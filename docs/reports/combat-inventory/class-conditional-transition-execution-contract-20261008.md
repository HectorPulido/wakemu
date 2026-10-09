# Owned conditional transition execution

`server/tools/audit_class_conditional_transitions.py` consumes the source-derived 651-branch transition plan. It builds legal decks and executes actual owned prerequisite casts after production Ready and actual turn advancement. It never inserts states, grants, resource values or positions.

The bounded default chooses one candidate per prerequisite state and level 20/200. The current source plan contains 48 prerequisite states: 40 have usable candidate edges, producing 75 representative cases from 4,385 source edges. Eight states have no usable caller candidate at these levels: 3333, 3699, 6752, 6872, 7647, 7950, 9309 and 9315. These are explicit pending cases, not unreachable proofs. Candidate loops, unavailable deck requirements and native-extra callers without actual grants remain visible.

Producer ranking combines legal deck availability, recorded actual owned permission and source depth. A shallow actual granted caller can rank before a deeply nested ordinary-spell ancestor. Whole-criterion positive preparations select additional genuine producers and a legal optional passive when its source initializes the required state during actual Ready. Additional unavailable passive requirements remain explicit. No passive is cast as an active action.

Literal native `HasState(state, level)` requires exact level equality, while `HasStateFromLevel` uses a minimum. The executor records those constraints and attempts up to three actual producer repeats, advancing real turns when needed; actual observed levels and full production casting criteria decide success. A missing or expired state is never synthesized to satisfy the threshold.

For each independent actual Ready baseline, the tool searches production-eligible caller targets, prepares and commits the caller, then searches and commits the original conditional spell against that resulting fight. A conditional branch is verified only when its exact source table index appears among actual matched rules and the actual selected caster/target Qf ledger contains the required state immediately before the conditional cast. Equivalent matched rules retain all source identities; an unknown equivalent branch never becomes a fabricated unique identity.

If the conditional request has no eligible target after its real producer, the executor attempts up to four actual end/ACK/owned-turn cycles while the required state remains present. Every stage records actual ledger levels/timers and re-runs production eligibility, including complete boolean criteria, resources and interval limits. Expiry before eligibility remains a failed sequence context. The default target bound is 256, preserving bounded-search evidence when a map has more candidates.

For a verified transition, ON and OFF independently clone the same qualified precast runtime. The OFF control attempts up to eight actual end/ACK/owned-turn cycles; ON costs and cooldowns cannot contaminate it. It records ordered ledgers and original carrier UIDs, and verifies removal only after those carriers expire through actual lifecycle execution and an actual restored spell commit no longer selects the requested branch. Unavailable restored targets trigger another bounded legal turn, without refilling resources. Baseline and alternative native selections remain separately recorded. Persistent states, removed target actors, unavailable restored targets and lifecycle failures remain pending. It does not directly delete any state or fabricate a removal producer.

Evidence includes actual costs, effective casting flags, native casting diagnostics, exact matched criteria/indexes, baseline and selected raw fyP tuples, actor/area ledgers, source preservation, plan SHA-256 and tool stability. Source inventory coverage, preparation success, conditional identity proof and removal proof are separate outcomes.

Pure checks: `test_class_conditional_transition_inventory`, `test_combat_casting_selection_provenance` and `test_class_normal_cast_inventory` — 8 tests passed. Heavy execution is serialized with validation; pure checks do not establish gameplay success.

Queued smoke command:

```sh
PYTHONPATH=server:server/tools python3 server/tools/audit_class_conditional_transitions.py \
  .runtime/combat-review-20261008/class-conditional-transitions-smoke-01.json \
  --levels 20 --states 3711 7651 --candidate-limit 256
```

The default full command omits those filters. No services, databases, AI or client are required.

Smoke05 establishes branch 1 of spell 2060 with actual state 3711 at level 1. It does not establish the level-2 branch requiring the original counter path. Spell 6908 actually selects branch 1 with state 7651 at level 2 and no state 7745; this is valid alternative evidence, not requested branch-0 proof. Passive 6925 is in the legitimate Ready deck, but its ancestor effect 344474 requires `GetCharac("WP") >= GetCharacMax("WP")` before effect 346179 applies state 7745. The applicator is retained with reverse subscription to turn-start event 1001 (native beD mask), so absence at Ready does not establish a false WP guard. The fixture seeds actual current and maximum WP equally. Missing passive prerequisites now receive up to eight actual end/ACK/owned-start cycles before the caller spends resources, recording actual characteristic snapshots and state ledgers. No passive is cast as an active spell. Actual replay must establish whether that native subscription produces the requested state. No WP refill or state injection is performed.

The independent-control regression and current pure source/ownership/selection batch pass 14 tests. Actual expiry restoration remains pending the next serialized replay.

Native regeneration boundary 1037 now follows the ordinary end event 1002 in the same unpublished turn-end preview, before expiry. Native state 7675 installs 343570 (reverse mask 1037), whose 343571 child uses family 193 to gain 1 current WP unless passive 6935 is present. The opening path instead uses family 194 to lose half the sampled WP. Installed English descriptions `content.33.343565` and `content.4.6935` establish end-of-turn natural regeneration; `content.33.344474` establishes the full-WP start condition. Original client callsite search did not establish an emitter or order; 1002 then 1037 is explicit Wakemu ordering policy. Exact native subscriber masks, all ordinary actor/global channels, end suppression, once-only markers and atomic rollback are preserved. No resource setter is added to turn advancement.

Focused replay 09 establishes both requested conditional branches. State 3711 has actual expiry and restored-cast proof. State 7651 is persistent before its cast, but the actual successful 6908 commit consumes it. The independent OFF control now replays the same validated owned action only when ON postcommit ledgers prove complete reference absence; it records the independent producer cost and trace, then advances actual legal turns for the restored cast. This is labeled actual spell consumption, separately from timer expiry. A missing owner ledger or replacement carrier with the same state reference does not prove consumption.
