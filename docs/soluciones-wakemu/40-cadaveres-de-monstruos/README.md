# 40. Monster corpses after combat

**Status: implementation prepared; deployment and manual acceptance pending.** No restart or runtime migration was performed for this change.

## Scope and evidence

Preserve defeated monsters visibly on the exploration map after combat. The user observed three defeated Gobballs remaining in the first official dungeon room and explicitly confirmed this also applies to monsters outside dungeons. Room changes must not be treated as corpse destruction. Actor removal packets prove client visibility removal only, not persisted lifecycle termination. Re-entry visibility and lifecycle require verification. Establish native actor death/persistence state, lifetime and cleanup on map reload or encounter reset from captured packets; the user explicitly requested a default lifetime of one hour on 2026-10-09, subsequently clarified as configurable through the database. Preserve combat settlement and prevent corpse harvesting or interaction from duplicating rewards.

Private evidence: `.runtime/official-dungeon-capture/snapshots/user-complete` and `snapshots/with-backtracking`; capture started on 2026-10-08. Official and local client manifests differ; use the recorded version provenance and verify consumers before applying protocol data. Screenshots and user observations support behavior, not complete wire contracts.

## Acceptance

Prepare one complete manual system test with exact setup commands, actions and expected results after automatic transaction, reconnection and protocol verification. Preserve existing combat and spell behavior.

Dependencies: 29, 14, 16.


---

This is not only for dungeons, the corpses are available on the overworld too

## Prepared implementation (2026-10-09)

- Migration `087_persistent_monster_corpses.sql` stores presentation-only corpses and permanent idempotency receipts. The `settings.monster_corpse_policy` value defaults to `lifetime_seconds: 3600`. Each corpse persists its lifetime and a database constraint fixes its deadline to creation plus that duration; reconnect, room changes, policy changes and settlement retries do not extend existing corpses.
- `monster_corpses.retain` runs inside the successful PvE settlement transaction for the original defeated group. It excludes live members, summons and players. Corpse harvesting uses a separate durable claim and the existing native harvesting transaction. Current settlement restores the living group on player defeat, so partial kills in a lost fight do not generate additional remains.
- New actor identities use the existing global Lua-exact NPC allocator, keeping corpse appearance separate from a future living respawn. Coordinates come from the original exploration roster, rather than fight placement. Map and dungeon instance scope are preserved.
- World snapshots replay unexpired remains; the existing original-actor cleanup still removes defeated living identities. A one-second scheduler publishes native removal at expiry. The stored lifetime follows the database policy (3600 seconds by default); visible removal has at most the scheduler tick and normal delivery latency.
- Expiry receipts remain durable so an old settlement retry cannot create a new period of visibility. Restart does not restore expired remains.

### Native evidence

Installed client `eHd.fsW()` returns `pW`; `pW.aG` reads `currentFightId`, `isKo`, `isDead`, `isSummoned`, `isFleeing`, `obstacleId`, summon presence. `eGn.zm` applies `pW.Ug` to `eGj.gg` and `pW.Uf` to `eGj.lz`. The new `world_actor(dead=True)` sets only `isDead`; normal alive serialization is unchanged. `VerifyMonsterCorpse.java` decodes the generated complete `ctE/eHj` appearance using the installed client: **PASS**, fight `-1`, dead true, KO/summon/flee false. This verifies the wire state, not the final animation in the graphical client.

### Automatic validation

`PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_monster_corpses test_monster_corpses_postgres test_combat_monster_world test_combat_world_group_cleanup` with the explicit isolated PostgreSQL test database and read-only native catalog environment: **27 passed** (13 corpse unit tests, 6 corpse PostgreSQL integration tests, 5 existing monster world tests and 3 world group cleanup tests). Unit tests use fake transactions; PostgreSQL tests use `PostgresCase` isolated schemas in `wakemu_migration_test`, applying migration 087. They verify the default 3600-second deadline, changed policy of 600 seconds affecting only new corpses, invalid policy transaction rollback, atomic rollback, durable store reopen, idempotent identity/deadline, per-map instance visibility, retry after expiry-publication rollback, single expiry publication and no resurrection from delayed settlement retries. No public runtime tables were modified.

### Complete manual acceptance after the eventual authorized deployment

1. In an outdoor map with two clients A and B, run `!mob 1 10 1`, defeat the spawned monster with A and finish returning to exploration. Expect one visible dead monster for both clients and the ordinary reward only once for A. B observing receives no reward. Record the finish time.
2. Move away and return, then reconnect A and B. Expect the same corpse at the original exploration location; its lifetime must not restart. Attempt to attack: it must not start a fight. Native corpse collection is available when the species has a supported corpse action and the character meets its profession requirement.
3. Complete a Jalató dungeon room. Move to the next room and back; reconnect inside the retained dungeon instance. Expect the defeated monsters in that room only, with no new fight/reward and no leakage into another party's instance.
4. Keep a client in the original outdoor map across the one-hour deadline. Expect the corpse to disappear within the next one-second expiry tick and ordinary delivery latency. Re-enter/reconnect after expiry: it must remain absent. Check the dungeon remains against their own finish time.
5. If a living group later respawns, expect its living actor alongside any still-unexpired corpse, with independent identity; fighting it must not revive or reward the old corpse.

Graphical pose, safe picking, live expiry publication and dungeon reentry still require this acceptance. No client rendering acceptance is claimed before deployment.

### Bounded retained-scene reconciliation

Permanent settlement receipts are not replayed as an unlimited removal history. `reconcile(db, map_id, instance_id, known_actor_ids)` queries only currently visible remains and removes the identities known to that retained scene that are no longer active. Fresh scenes have no historical identities. `expired_removals` also accepts an explicit known-ID set and performs no query for an empty set. A fixed time cutoff is intentionally avoided: a spectator or combat may retain a scene longer than that cutoff. The dispatcher keeps a weak per-socket set, preserving known corpse identities while that connection temporarily leaves exploration. Individual joins/replays reconcile that set; terminal world broadcasts record the active appearances for the recipient sockets in the matching location, excluding fight participants and spectators. Closing a socket releases its tracking state automatically.

### Configurable database lifetime

The policy is read once per settlement from `settings` under `monster_corpse_policy`. `lifetime_seconds` must be an integer from 1 through 2678400 (31 days). Invalid or missing policy aborts the caller transaction; no silent fallback hides a configuration problem. Existing corpses preserve their stored duration and expiry when policy changes. No service restart is required for later policy edits.

After migration deployment, this exact SQL sets ten minutes for newly created remains:

```sql
UPDATE settings
SET value = jsonb_set(value, '{lifetime_seconds}', '600'::jsonb)
WHERE name = 'monster_corpse_policy';
```

Use `3600` instead of `600` to restore the default hour. This configuration command is documentation only; it was not executed on the runtime database.

### Live rendering regression correction (source prepared)

The user's deployed test exposed that decoding `pW.isDead=true` did not make an exploration NPC dead. Outside combat, `eGZ.pKv.gg` is a no-op. The corrected world appearance also sends native world property `eHQ.DEAD` (19), through `rK/rN/wU` (one entry, count 1). `eGv.zm` installs that property and `bje.dsA()` becomes true; `cgN` then calls `bje.dsq()`, whose visible-corpse branch uses `AnimStatiqueCadavre`. Ordinary living appearances keep their original empty property section. Native breed corpse-visibility rules remain intact.

`VerifyMonsterCorpse.java` now exercises the real native consumer: applying only the old `pW` data leaves `bje.dsA()` false, while applying the decoded world property makes it true. Actual `cWi.aK(npc)` records `FIGHTING_FORBIDDEN`; the installed native `cXb.bxQ` living-harvest visibility gate also requires `!dsA`. Native corpse collection remains a distinct menu depending on the breed and is implemented by the atomic resource harvesting flow below. This stronger consumer probe passes; the 26-test corpse gate passes as well. No restart, deployment or runtime-data mutation was performed for this correction. Graphical confirmation remains pending.


## Native corpse resource harvesting (prepared, not deployed by this agent)

User clarified that collecting the resource must remove the corpse. Migration `093_monster_corpse_harvesting.sql` adds consumed state and a unique token to the durable receipt; consumed rows remain as settlement tombstones. The server authorizes only exact `IsDead("target")` corpse collection actions. The corpse encoder leaves both known dead/living criteria to the native client so it can explain exclusions accurately; only unsupported/empty criteria are disabled through `sR`. Profession, required level, duration and output resource come from the existing native `monster-encyclopedia.json` collection catalog. Quantity remains the existing explicit `settings.monster_harvest.quantity` policy.

`harvest_target` resolves a scoped durable corpse when no living group exists. `Harvests.begin` rechecks the current corpse and uses its authoritative zero HP. Completion atomically claims the unconsumed, unexpired corpse together with normal inventory insertion/stacking, profession XP and the existing harvest receipt. Full inventory, expiration, ownership failure or transaction rollback cannot consume the corpse or grant a resource. Successful harvesting emits native actor removal to the map/instance and excludes the consumed corpse from subsequent snapshots. Existing timers replay consumed removals as a delivery fallback; reconnect never revives it. Combat/ecology rewards are not awarded again.

Native consumer oracle with species 735 verifies DEAD19, forbidden attack, disabled living collection actions and enabled native corpse action 3749. Final automated gate: **65 tests passed, zero skipped** across `test_monster_corpses`, `test_monster_corpses_postgres`, `test_combat_monster_world`, `test_combat_world_group_cleanup`, `test_monster_collect` and `test_monster_corpse_harvesting`. The new harvesting module passes 8 cases: dispatcher living-first resolution and scoped corpse fallback, atomic resource/profession-XP/receipt/consumption, duplicate completion, expiry before and after occupation start, concurrent workers with one winning claim, and inventory failure rolling back the claim and rewards. Luna independently reran the complete gate and native Java oracle. No runtime DB changes or service restart were performed by this agent.

### Manual harvesting acceptance after deployment

1. Use a character with Trapper learned (profession 74). Defeat a Jalató (reference 1) and return to exploration. Expect a corpse pose, no enabled attack, and its native corpse collection action (3722).
2. Choose the enabled hand icon to collect the corpse resource: native duration is 3000 ms, required Trapper level 0, output item reference 2731. Expect the configured resource quantity exactly once, normal profession XP and immediate corpse disappearance for all characters on that map/instance.
3. Reconnect and revisit the room/map. Expect the resource retained and the corpse absent, with no duplicated reward.
4. Repeat with another corpse while the base inventory is full. Expect no resource and no consumed corpse; free a slot and retry successfully.
5. Let another corpse expire using the configured lifetime; collecting an expired or already-collected corpse must not grant any resource.

### r63 manual feedback: corpse pose accepted; seed tooltip corrected in source

The user screenshot at 22:37 on 2026-10-09 confirms the corpse pose. It shows the seed extraction icon disabled and the hand collection icon enabled. These are different native actions: Jalató seed action 3723 (resource 2246) requires `not IsDead("target")`; corpse hand action 3722 (resource 2731) requires `IsDead("target")`. Seeds must therefore remain unavailable on a dead Jalató. Resource harvesting and disappearance are still awaiting manual acceptance using the hand action.

The misleading “Recolectado recientemente” tooltip came from serializing the living-only action as unavailable in `sR`. Native `cXc.eVy` reports `collect.error.npc.collected` for that availability flag before evaluating the action criterion. The corrected encoder leaves native living/dead criteria available for their own eligibility evaluation, so the seed action is rejected by its actual target-state criterion rather than a fake cooldown. Server validation still rejects living-only actions on corpses.

`VerifyMonsterCorpse.java` now applies the real decoded world property to a native `bje`, checks that native action availability is not falsely marked collected, and evaluates the real `eQb/eQd` parsed predicates: dead collection succeeds and living-only seed extraction fails for the dead target. The independent `VerifyCorpseHarvestCriteria.java` probe verifies the same native predicates against both living and dead actors. No restart or deployment was performed for this tooltip correction.
