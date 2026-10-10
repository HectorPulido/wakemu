# Sacrier inventory and readiness review — 2026-10-09

> Historical inventory baseline: subsequent local corrections and current validation are recorded in [the implementation review](sacro-implementation-review-20261009.md). No deployment is implied.


## Delivery scope

Inventory, implementation review and offline validation only. No production
implementation, gameplay database writes, deployment or restart was performed
by this audit. Cra and Iop remain provisionally accepted as 2/18; Sacrier is not
accepted as 3/18. Findings below are work to do, not fixes delivered.

Authoritative published catalog revision:
`a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.
The historical ownership graph was reconciled against current children,
state/grant/area/morph parameters and literal criterion dependencies. This
added 95 effects, six states, three morph actions and profile 5900. Structural
closure includes conditional and false branches; it is not execution coverage.

## Percentages with explicit denominators

There is no defensible single percentage for complete class functionality.
The following measurements answer different questions and must not be averaged.

| Measurement | Current result | What it proves |
| --- | --- | --- |
| Classified class register inventoried | 21 active + 20 passive + 5 granted + 3 morph actions; 2 innates | Complete identified action/register scope, not complete gameplay |
| Current referenced effect definitions present | 1029/1029, 100% | Data presence |
| Current referenced state definitions present | 51/52, 98.08% | State 759 is missing |
| Reachable effect families with a binding | 68/68, 100% | A handler exists, including gated handlers; unsupported branches remain |
| Normal-deck cast attempts prepared | 62/64, 96.875% | Actual offline cast preparation in the sampled baseline contexts |
| Distinct active/level pairs with at least one prepared variant | 35/35, 100% | 14 available actives at level 20 and all 21 at level 200; does not erase failed variants |
| Passive scenarios installed | 20/20, 100% | Native initialization accepts each equipped passive |
| Passive scenarios with an observed cycle | 19/20, 95% | One basic scenario per passive; Immolation is blocked |
| Passive scenarios with the harness activation observation | 10/20, 50% | Observed triggers in this harness; other cases are not automatically missing implementations |
| Fresh focused Heart of Blood and Berserker tests | 4/4 | Three actual grant/armor/heal/consumption tests plus actual turn-start recalculation |

In particular, **96.875% is sampled casting preparation, not “Sacrier is
96.875% finished.”** No exhaustive manual acceptance of this class exists.
The normal audit's deployment gate is false; it must not be presented as a
successful deployment/complete acceptance gate.

## Concrete findings and work remaining

| ID | Priority | Finding | Required closure |
| --- | --- | --- | --- |
| SAC-01 | P1 | Missing state 759 in native Berserker 3702 dependency closure. Installers 316596/316608/316615 and removal 316760 reference it. Immediate guards are ordinary team/HP-accumulator criteria, not literal false. | Recover the original definition or prove its original absence/alternative contract; trace actual event reachability. Do not invent replacement effects. |
| SAC-02 | P1 | Immolation 7224 fails its real passive cycle at own turn start: 162662 → 162663 → 162668, family 421, `Unaudited native dispel flags: [17]`. | Audit native flag 17 semantics and general dispel handling, then rerun all dependents. Family 321 uses a separate handler and is not proven blocked by this validator. |
| SAC-03 | P1 | Columnata 5037 self-target variants fail at both level 20 and 200: 196997 → 416129 → 416131, family 1013, target NPC -7, `Invalid native armor fight/target`. Other variants prepare. Both failures preserve the original fight. | Resolve whether the armor child is incorrectly attempted after lethal target damage or has incorrect target/life eligibility. Replay surviving and lethal targets, self-centered area, critical branch and rollback. This is a reproduced branch rejection, not a claim every Columnata cast fails. |
| SAC-04 | P1 | Publisher completeness for subscribed events 4/60/74/1041/2263 is not established. Pact of Wakfu 7217 listener 353414 uses events 60/2263; implementation of family 912 alone does not prove delivery. | Recover intrinsic/external publication, actual source, channel and timing; execute qualifying paid-cost branch. Do not confuse channel 60 with event 60. Event 2235 already has intrinsic armor producers 1010/1012/1013. |
| SAC-05 | P1 | Complete Sacrifice 5044 interception, deferred position exchange and cleanup are not established by generic redirect tests or a single initial cast. | Real ally attack → redirect 161467 → delayed 196837 → swap 161468; direct/indirect damage, zero hit, multiple protectors, stabilized/carried actors, low-HP cleanup and dead/disconnected owner. Its ratio is 100; unrelated unsupported ratio -2 is not a Sacrier blocker. |
| SAC-06 | P1 | Granted and morph action lifecycles have partial historical and current evidence. | Real grants 5046/6065/8586/8587/8593, profile 5900 actions 8588/8589/8590, exact ownership, real prerequisites, expiration, original book restoration and reconnect. Do not inject prerequisite states. |
| SAC-07 | P1 | HP/self-damage, armor and retained threshold combinations are not exhaustively tested. | Missing/current/max/raw HP, stored damage, 20% and 50% boundaries in both directions, armor-only hits, multi-target self effects, heal modifiers, Punishment, Refusal armor reaction, zero and lethal cases, passive interactions and costs once. Refusal 5052 is not classified as an absent revival spell from its name. |
| SAC-08 | P1 | Displacement/reaction and map boundaries require complete current acceptance. | Pull/approach/teleport/swap, Cinetosis damage, geometry, LOS, height, footprint/radius, stabilized/carried actors, dead occupancy, arena limit, collisions and correct visible actor identity. |
| SAC-09 | P1 | Shared multiplayer and finish lifecycle is not class-certified. | PvP and PvM, two clients, readiness/first turn, turn progression, reconnect, surrender, death animations, temporary UI/book cleanup, rewards and dungeon room progression. Existing rails do not fabricate ACKs or hide deterministic missing implementations. |
| SAC-10 | P2 | Several legacy tests cannot currently serve as a clean acceptance gate. | Replace filesystem-only catalog assumptions with the actual published catalog authority; supply complete native QI fixtures, update source-backed channel expectations and rerun meaningful assertions. Do not relabel fixture failures as verified live bugs. |

The isolated Columnata comparison strengthens SAC-03: NPC5525 level1 (12 HP)
rejects at caster levels20/200; NPC3646 level12 (84 HP) prepares at both caster
levels, leaving76 HP/+2 armor and20 HP/+17 armor respectively. The damage child
416130 executes before armor child416131. This points to a lethal-target
lifecycle problem; the original native rule for the armor sibling after lethal
damage still requires verification. Fourteen additional granted-action attempts
also prepared in the baseline audit; they do not certify all granted/morph
prerequisites or lifecycle variants.

## Existing Cra/Iop work already applicable

- **Shared group target transmission:** preserves native on-target and
  transmit-target behavior. Essential to nested self/ally/enemy effects; retain
  it while investigating armor/redirection, rather than adding class exceptions.
- **Actual granted-spell ownership and retained managers:** reuse native owner,
  UID, initialization and cleanup contracts for Sacrier grants and form books.
  Beacon-specific behavior is not a Sacrier feature.
- **Attack preparation policy:** use only if the actual native damage/modifier/
  marker/removal pattern matches; never copy Iop spell/state IDs or consume
  unrelated Sacrier resources on every attack.
- **Transactions and primitive checkpoint state:** preview execution, exact
  once-only payment, source/RNG rollback and serialization protect nested
  blood/armor/movement/reaction chains.
- **Aptitudes and movement:** selected-build caps, HP/armor/heal consumers,
  Barrier renewal and tackle/dodge payment are shared. Their presence does not
  certify Sacrier-specific formulas or expiration.
- **Death, LOS, ownership and combat lifecycle:** source-qualified actor IDs,
  proper occupancy/status, participant membership, bounded transient retry and
  reconnect/finish cleanup remain common regression requirements for all three
  classes. Wrong death animation remains a separately unverified presentation
  report, not automatically closed by server targeting changes.

Read-only inspection during this audit observed healthy running world
`wakemu-world:haven-pet-refresh-20261009-r56`, image SHA256
`c27f9ea6e2f3524908327ed983a720fb135c94e469e9a258eaa8df0f801fccac`.
Its preparation, group dispatch, turn guard and periodic aptitude source hashes
matched the corresponding current shared files. This was another agent's
deployment; this audit did not deploy it or certify every file in that image.

## Complete evidence and acceptance package

- [All active/passive/granted/innate rows and current dependency reconciliation](sacro-catalog-audit-20261009.md).
- [Machine-readable definitions, current edges, area 1605 and profile 5900](sacro-catalog-audit-20261009.json).
- [Current family registrations](sacro-current-family-routes-20261009.json).
- [52 criterion names and 34 subscribed/published event IDs](sacro-context-inventory-20261009.json). All 52 names have explicit evaluator branches; actual provider/source correctness remains separate.
- [Runtime risk review with exact native paths](sacro-runtime-risk-audit-20261009.md).
- [Fresh tests, failures, fixture limitations and full manual acceptance](sacro-validation-audit-20261009.md).
- [Normal cast attempts including the two rejected Columnata branches](sacro-normal-casts-current-20261009.json).
- [All 20 passive cycles](sacro-passive-activation-current-20261009-rerun.json).

The manual package uses a disposable level-250 Sacrier (`!nivel 250`) to expose
the whole register, with a separate level-60 subset. It requires actual unlocked
decks and earned state/grant prerequisites, not injected states. Complete
acceptance must include each action/passive, negative cases and the shared
multiplayer/dungeon lifecycle. None of the inventory percentages replaces that
acceptance or authorizes describing the class as finished.
