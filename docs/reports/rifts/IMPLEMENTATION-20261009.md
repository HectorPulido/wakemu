# Rift source implementation — 2026-10-09

Source only. No deployment, restart or live database mutation. Native extraction is documented in [the audit](STATUS-20261009.md) and [protocol evidence](NATIVE-PROTOCOL-20261009.md). Source implementation does not certify playable end-to-end rifts.

## Frozen local policy

Migration 090 seeds `settings.rift_catalog` with the ten exactly linked table147 definitions and native pools/entrances/interior objects. `settings.rift_policy` explicitly declares `policy_kind=local_dev_not_official`, 40 complete timeline rounds, four members maximum, four classic enemies or two ultimate enemies per wave, starting wave 1, deterministic uniform selection with replacement and native base grades. These are configurable local development choices, not recovered official balancing. No artifact probabilities, monster scaling or current official reward formulas are asserted.

Policy is frozen into every new run; changing the settings affects new runs only. Existing runs keep their seed, membership, catalog and policy across restart. Classic access ignores quests. Ultimate admission defaults disabled until transactional native key authority is connected; native protocol evidence now confirms exact start actions and one-key costs.

## Domain transaction contract

`rift_runtime.enter(db, wave_id, owner_character_id, members, seed=..., authorize=...)` requires canonical source/party/session authorization and freezes the run. It serializes overlapping memberships, rejects duplicates/unknown members and allocates a separate persistent instance namespace. `rift_entry_adapter` supplies canonical party/session/proximity/level checks and moves all accepted members in the same transaction.

`start(db, instance_id, owner_id, fight_id)` requires the exact frozen members on team 0 in `combat_fight_participants`. `bind_wave(db, instance_id, wave, actors)` freezes the accepted original NPC IDs and ordered native references; references must equal deterministic local selection. Summons are excluded by the caller's original roster authority. `record_wave` rejects stale or invented equal-sized actor lists and creates one immutable wave receipt, with its next reference selection, in the same checkpoint transaction.

`persist_progress(db, fight)` consumes `rift_wave_state.staged_receipts` after an accepted action, records each wave, validates the frozen next reference list and binds its new actor identities. It must never be called from speculative cast previews. Failed native actor admission or checkpoint writes roll back progression. Receipt replay cannot advance twice, regenerate random choices or replace identities.

`settle(db, instance_id, fight_id, outcome=..., turn=..., apply_rewards=...)` records one terminal result. Surviving before the frozen turn budget is rejected. Only wins invoke an explicit reward authority callback, within the same transaction; loss/closure cannot pay. No ordinary world group lease, per-wave ordinary drops or world corpse authority belongs to these wave transitions. The callback must explicitly implement disabled or configured local rewards until official probability authority is recovered.

## Integration requirements

1. Register initial native enemy authority through the existing NPC creation path, then bind the first wave alongside the initial combat checkpoint.
2. Opt the fight into the serializable combat adapter; ordinary fights remain unchanged.
3. Admit new waves inside the same fight with actual native NPC creation, arena/physical/global/timeline authority and observer/reconnect creation replay. Accepted commands persist staged facts with their checkpoint before publication.
4. Route native portal/start actions, map bootstrap, wave 13051 notifications and final result counters using the exact contracts; lore actions must not create combat.
5. Settle once with explicit local reward policy and restore world positions. No end-to-end manual acceptance is claimed until this wiring is validated and deployed later.

## Tests

Pure selection tests cover deterministic retries, native-pool membership, separate ultimate size and malformed/unsupported policies. PostgreSQL tests use disposable schemas to exercise durable receipts/reopen, failed-spawn rollback, reward callback exactly once, reward rollback, loss/no reward, early-survival rejection, active-membership conflict, frozen settings, arbitrary actor rejection, ultimate fail-closed and staged checkpoint replay.

Commands:

```sh
PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_rift_runtime test_rift_runtime_postgres
```

PostgreSQL requires the explicitly isolated test URL and password-file environment used by repository tests. Final validation totals are reported by the testing agent; source state alone is not gameplay acceptance.

## Instance namespace and native wire widths

Rift persistent instance IDs start at 288230376151711745 and remain PostgreSQL signed 64-bit integers. These are server-only visibility/ownership keys: `WORLD.location` scopes `(map_id,instance_id)`. `native_transports.bootstrap` format28 serializes native asset `map_id` in its position `q` field and does not serialize `instance_id`; `combat_monster_world.world_actor` does the same. ProtoDungeon has no server instance-ID field. Its `allowed_ids` are character IDs and must never receive run instance IDs. A regression test checks that bootstrap bytes remain identical when only server instance scope changes, even above 2^53. This avoids conflating Java/Lua actor-ID constraints with server-only run namespaces. NPC identities still use the existing bounded exact allocator.

## Dispatcher preparation and exit services

`rift_dispatch_lifecycle` selects a verified reachable native arrival floor, prepares initial base-grade native NPCs using the existing placement engine and exact negative UID allocator, and provides a pure `next_roster(fight,pending)` for accepted-action wave admission. Its checkpoint state carries frozen catalog/policy/seed plus preallocated unused actor IDs. The provider cannot allocate database IDs during a speculative cast; the caller reserves/replenishes identities transactionally. Native directed edges determine reachable free arena cells; no grid-neighbor shortcuts are inferred. The provider does not replace native NPC creation/effect/timeline authority.

`rift_exit.leave` fences and flushes affected accounts' queued positions, verifies the current selected session and exact frozen membership, resolves the native 17-byte exit through the existing teleporter criterion/cost/altitude checks, and rejects registry or durable active fights. Before combat, an owner exit cancels the entire run and restores all frozen members atomically; a guest cannot silently break the frozen party. Terminal-run members may exit individually. Existing sockets receive queued generation-scoped map hydration; durable positions cover reconnect.

The default explicit reward policy is `settings.rift_reward_policy = {"kind":"disabled","xp":0,"kamas":0}`. Changing it to unsupported values fails closed until an actual authority is implemented. This is a development baseline with no invented official prizes.

Validation completed against current source: **17/17 tests passed**, including ten disposable-schema PostgreSQL tests and seven pure policy/geometry/exit fixtures, in 10.991 seconds. Native portal serialization and wave-notification oracle also passed. These results cover the domain/adapters, not dispatcher or full graphical acceptance.

Native fight-local obstacle byte capacity is 127 registered actors. Keeping every dead wave fighter indefinitely can exhaust it after roughly 31 classic waves. Correct native retirement/reuse must be established before certifying unlimited waves; preallocated globally unique actor UIDs do not remove this separate capacity constraint.

## Dispatcher integration prepared in source

The shared dispatcher now intercepts the native 12-byte `cpF/12870` portal action 11, including its two trailing zero bytes. Rift transitions fence and flush every affected account's position buffer before the database transaction, reject a changed barrier scope, release old position baselines, and queue generation-specific hydration. Existing sockets bootstrap the committed native asset map; reconnect reads that same durable position.

Classic interior action 0 creates an ordinary placement fight with native base-grade NPCs, automatically admits the complete frozen party through normal placement admission, and binds the first wave to that fight. The run has no world monster-group lease. The explicit local approach policy allows at most three cells in X/Y and two altitude units from the server-owned portal/activator. Arrival is selected from reachable exported native floor near the unique activator; this is a development policy, not a recovered official coordinate.

Every accepted rift operation, server NPC action, acknowledgement and timeout passes through the shared registry's opt-in preparation callback. It consumes pending waves on a detached candidate, creates fresh ordinary NPCs with native characteristics/QI/timeline authority, and synchronously persists the fight checkpoint and wave receipts before adopting or publishing the candidate. Existing ordinary combat takes its original path. Current native appearances precede complete placement, observer and reconnect bootstraps; incremental reinforcements use ordered 12608 appearance followed by 13091 admission and a native-action-allocated 13051 wave notification. Native world group IDs use the exact positive fight ID, never the private server instance namespace.

Final settlement records one rift receipt in the ordinary combat settlement transaction, suppresses ordinary monster drops and uses the explicitly disabled zero-XP/zero-kama development reward policy. Startup reconciles interrupted bound fights so members can exit rather than remaining locked in a running instance. Native fighter-history exhaustion closes with an explicit development capacity outcome and a native-compatible defeat result, no victory and no prize; it does not recycle referenced dead fighter IDs.

The final local gate passed **83/83** adapter/dispatcher/native-wave/shared-combat tests and the separate **12/12** domain/exit PostgreSQL batch in disposable schemas. These are separate executed batches, not a claim of full repository or graphical acceptance. No deployment or restart was performed.

## Complete manual acceptance after a later deployment

1. Use two accounts with selected characters of level 21 or above. If necessary run `!level 21`, then reselect the character as instructed by the console. On each account run `!teleport 527 -192 -29 0`; this is the exported walkable Tainela exit arrival, beside portal 33010.
2. Enter solo first. Click the dimensional-rift portal, then its native enter action. Expect interior map 1314 and an operable start activator; entrance action should not immediately create combat. Exit before starting and expect the Tainela exterior again.
3. Form a two-character party outside, keep both characters next to the portal, and enter as leader. Expect both accounts in the same private interior. A nonleader must not cancel or start the frozen run; the leader's unstarted exit should restore both accounts outside.
4. Reenter with that party and use the classic start action on the interior activator. Expect one shared placement fight containing both characters and four native enemies. The lore action must only show its normal background interface. Ready both characters and fight normally.
5. Defeat a full wave. Expect four new ordinary enemies within the same fight, no victory window, no map transfer, no per-wave XP/kamas/items, and continuing current combat resources/timeline. Repeat for multiple waves; verify attacks, movement, summons and NPC turns still work.
6. Reconnect one account during combat. Expect current living enemies, dead history and effects to be reconstructed without duplicated admission. Observer bootstrap uses the same native appearance prefix and is covered automatically; the initial private-entry flow provides no separate route for a third account to join as a visitor, so manual late-observer acceptance remains pending that route.
7. Complete the configured survival budget or lose. Expect a single terminal result, zero development prizes, and usable native continuation and exit. Check no persistent world corpses or ordinary monster-group rewards were created for the wave roster.
8. Test a definitive entrance separately. It must reject admission while native key consumption is deliberately disabled; the definitive no-key bubble must not start a classic fight.

Artifacts, official scaling, official reward probabilities, rankings/chests, definitive key transactions and unlimited native fighter retirement remain outside this initial playable development baseline. Their absence must be retained in acceptance reporting.

### Native roster capacity investigation and controlled termination

Native obstacle slots are already retired by verified ordinary-death completion:
`fcb.aD -> H -> aQ -> QI.g`. The server's ordinary QI retirement follows that
path and permits first-free slot reuse. Historical actor retention, rather than
simultaneous obstacle slots, currently bounds rift recovery to 127 actors.

Offline `javap` examination of `fem.eP(ByteBuffer)` shows signed-byte counts for
its removed-status map (`sbE`) and bonus collection (`sbD.dLy()`). `fcb.dLy()`
selects IN_PLAY and OFF_PLAY predicates (`fdD.fYb/fYd`, `fdU/fdW`), excluding
OUT_OF_PLAY actors. The current recovery serializer includes historical actors
more broadly; correcting that projection alone would not prove safe removal of
the removed-status history. `fem.eu(long)` removes a removed-status record, and
`fcb.bd(F)` can call it through the timeline object, but its permanent-retirement
caller/lifecycle has not been established. Ordinary combat is therefore unchanged.

Until native permanent history retirement is proven, admission that would exceed
127 retained actors terminates explicitly with `capacity_exhausted`, no winner
and no rewards. It preserves the last cleared wave as an immutable durable
receipt, consumes no successor actor identities, and does not remain stuck in a
pending wave. A wave cleared at the final turn also records its kills without
requiring a successor wave to spawn. This is a local implementation boundary,
not an official rift rule or a claim of unlimited verified runtime.

Interrupted running instances close alongside canonical fight aborts or startup
recovery, with no inferred rewards. Characters retain their interior location
and can use the native exit after reconnecting.

Additional read-only native readiness checks passed for all seven classic interior maps: a reachable arrival and separated formation for four players/four enemies were found on each actual exported map. All 115 unique native NPC references in those seven pools produced valid base-grade creation characteristics. These checks establish available geometry/stat curves, not official encounter mechanics.

The final native wave notification is wired and decoded by regression tests. Native final-report counters are now proven to be fields 10–13 of ROOT `FightReport` (`ji`), distinct from player-record field 10 (death). Those optional rift counters are not emitted by this baseline; ordinary terminal reports remain in use. Artifacts, scaling, rewards and rankings remain explicitly pending rather than inferred from UI fields.


## Configurable local DEV item rewards (source update)

[Reward policy, exact defaults, durability and acceptance](REWARDS-20261009.md) supersedes the earlier disabled-item reward baseline in source. Migration095 enables explicitly local equipment, shards, verified BASIC sublimations and physical learnable costumes, delivered atomically through existing inventory/temporary loot authority. XP/kamas stay zero; losses/closure pay nothing. This reward update has not been deployed.


## Observed r63 manual probe (2026-10-09 local evening)

Read-only logs place the actual probe at 22:25–22:28 America/Bogota
(03:25–03:28 UTC on October 10), earlier than the initially reported window.
Character 4 first attempted admission as a non-leader and was rejected at
03:25:42 UTC. A party request followed; successful admission at 03:25:48
created instance 288230376151711745 with the immutable roster `[4]`.
The durable record confirms fight129 reached wave2, cleared wave1 and defeated
four monsters. The user surrendered during wave2. The ordinary abandon path
aborted the fight and closed the rift without rewards; native exit returned the
character to map527 at03:28:26 UTC.

This verifies a solo entry, first-wave completion, successor-wave appearance
and exit following surrender. It does not establish four-player admission,
40-turn survival, reward delivery or complete acceptance. The earlier non-leader
rejection and frozen solo roster do not show a party member silently omitted.

## Six-member local DEV party override (source update)

Migration096 sets `settings.rift_policy.max_members` to **6** for new runs.
The validated configurable range is 1–6; existing instances keep their frozen
policy. This user-requested difficulty adjustment is a local DEV override: native
rift UI evidence still describes four characters, and that historical evidence is
not rewritten as an official six-character rule.

General party membership already supports six (`player_party_policy`, migration030).
The entry adapter derives and validates the complete canonical party dynamically;
arrival checks reserve enough reachable native floor, initial enemy formation
reserves `len(run.members)` player slots, and ordinary native combat placement
has capacity for at least six. No ordinary combat/spell code was changed.

Regression coverage includes six real selected account sessions entering and
moving together, immutable frozen policy after a subsequent configuration change,
exact six-participant start, installed native map1314 initial NPC formation and
placement capacity, seven-member rejection with no partial movement/run, and
arrival failure rolling back the complete six-member transition. This source
update has not been applied to the running database or deployed.

### All-classic-map and native client gate follow-up

A single isolated PostgreSQL batch test now validates **all seven classic native
maps** (1314, 1316, 1320, 1322, 1329, 1330, 1345): native geometry loading,
six-member reachable arrival, initial native NPC formation and final native arena
placement capacity of at least six. The seven-map batch passed in 2.499 seconds.

The offline reproducible `sniffer/java/ExportRiftPartyGateEvidence.java` exports
`aNE/aNF` destination gates referenced by the ten public wave definitions, using
the exact `baP -> flE/flF` mapping. Its output is
[native-party-gates.json](native-party-gates.json). All ten destination criteria
are empty; the exporter asserts this. The native portal `bCy.b(QT,Rd)` delegates
to destination/hero/cost checks in `bFE/flU`; no four-member count comparison exists
in that path. The classic start descriptor1456 has an empty action criterion and
only `not IsHero()` as its start effect criterion. `bBH` generic interaction
usability/action dispatch has no rift-specific four-member comparison. Thus the
four-member informational UI text is not an observed pre-packet admission cap
in these installed-client portal/start paths. This evidence does not replace
pending graphical acceptance with six real clients or claim upstream support.

Reproduce the native gate extraction from repository root:

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp sniffer/java/ExportRiftPartyGateEvidence.java
java -cp '/tmp:client/lib/*' ExportRiftPartyGateEvidence docs/reports/rifts/native-party-gates.json
```
