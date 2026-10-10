# Dungeon failure review — 2026-10-09

Read-only review of the latest r58 manual acceptance, shared source and generated configuration artifacts. No runtime code, database, image or service was changed. Generated artifacts describe the configuration pipeline; this review did not query the current run's frozen database configuration, so exact run/policy identity remains to be correlated before a repair.

## Findings and confidence

| Issue | Evidence | Conclusion |
| --- | --- | --- |
| Tofullero first encounter unreachable | Hector's normal party entry leaves both characters at a closed gate; the monster group is behind it | Failed live acceptance. Exact gate/client movement cause remains unknown |
| Tofu Real appears in first encounter | Screenshot roster matches the generated configuration's first roster, including reference 1259 | Generated pool policy is a concrete cause of invalid early boss inclusion; this is not proof that progression jumped to the final room |
| Native room order | Local topology explicitly has `official_room_order_verified: false` | Current room order is generated, not a verified native sequence |
| Casa de Miabuelita | Trusted achievement baseline implemented; no new successful full client run recorded | Criterion fix has source evidence but entry and complete progression remain unaccepted |
| Jalató | Prior user run succeeded | Retain acceptance; use as regression control |
| Sorciere/Wagnar | Persistent exploration `HasState` authority absent | Deliberate fail-closed limitation, separate from the Tofullero gate |

## Proven composition problem

`server/wakfu_server/maps/dungeon_local_roster_policy.py:53` sorts the dungeon's entire species pool. At line 164 the generator fills each incomplete room to eight units by cycling that same pool; it never restricts boss species to a final encounter. At line 172 the role is assigned solely from the native catalog's `is_boss` boolean. This role is metadata, not an exclusion rule.

The private generated artifact `.runtime/local/methodwakfu-dungeons/local-policy-configs-all87/configurations.json` contains slug `le-tofulailler`, route `native_dungeon_27`, template 29, asset 1087. Its first roster is:

```text
4, 5, 6, 704, 1259, 4, 5, 6
```

This is exactly Tofu, Tofona, Bebé tofu, Gorditofu, Tofu Real, Tofu, Tofona, Bebé tofu, as in Hector's screenshot. All eight slots are marked generated. Reference 1259 is labeled `role: monster` in this artifact. Room 2 also includes 1259; room 3 includes it twice. Therefore “boss first” need not mean the server selected the last progression index: the room-one configuration itself contains the boss. Treat the species pool as allowed identities, not authoritative encounter composition. Catalog boss classification also needs verification before using it to enforce a general boss policy.

## Entry and closed gate: proven gaps, unresolved exact cause

`server/tools/discover_dungeon_native_routes.py:91` explicitly creates local logical rooms rather than official room order. Components are ranked by size at line 137, anchors by degree/centroid and then formation feasibility, and the result records unverified order at line 243. The Tofullero artifact anchors are `(34,-29,-11)`, `(11,-45,-8)`, `(16,-26,0)`.

`server/wakfu_server/maps/dungeon_runtime.py:28` resolves entry to the pinned current-room anchor. It validates membership in the room cell set, not client interaction reachability across runtime gate states. At line 53, enemy formation uses the room's filtered static geometry. `server/wakfu_server/maps/dungeon_encounters.py:41` verifies formation connectivity and party capacity on that geometry. These are useful static checks but do not establish that the client can move to or select the published monster group with native gate/collision objects present.

`server/wakfu_server/maps/dungeon_object_states.py:44` disables native dungeon interactions for the local automatic policy; line 84 publishes native transport objects as hidden and unusable. `server/local_game_server.py:7218` independently rejects native interior travel under that policy. These changes do not prove a visible gate's collision state was removed. The source therefore contains a structural mismatch between generated static graph reachability and actual client traversal. It does **not** establish which gate object, collision, altitude, entry snapshot or publication mismatch caused this specific attempt.

The entry callback is connected at `server/local_game_server.py:7305`, alongside initial room creation. `server/wakfu_server/maps/dungeon_transport.py:109` authorizes the party and atomically creates/reuses its run. Before repair, correlate each character's committed position, active instance/policy version, current room, published group member positions and relevant object-state packets from this attempt. Do not infer those values from screenshots alone. A reused run also intentionally resumes its current room rather than resetting to room one.

## Casa de Miabuelita and other criteria

`server/wakfu_server/maps/dungeon_achievement_authority.py:9` accepts a trusted running/completed/objectives snapshot and rejects absent or contradictory authority. Migration 086 initializes local characters with an explicit empty baseline, preserving existing snapshots. Miabuelita's criterion excludes a temporary quest state rather than requiring a quest completion. This supports the prior criterion fix; it does not validate physical entry, encounter placement or progression. See `docs/soluciones-wakemu/29-mazmorras-e-instancias/ACHIEVEMENT-AUTHORITY-20261009.md`. No fabricated quest completion or blanket `HasState` bypass should be introduced.

## General remediation proposal — not implemented

1. Audit all installed configurations for generated versus verified topology and rosters, early boss references, duplicate final boss slots, and mismatches between catalog boss flags and trusted dungeon boss identity. Preserve verified complete rooms.
2. Compile room order and roster composition from authoritative per-room evidence. Where evidence is absent, expose explicit local policy and avoid presenting it as native composition. Enforce general final-boss placement only with trusted boss identity; do not add a Tofullero-only monster deletion patch.
3. Validate entry-to-encounter reachability against runtime native object states and the client's movement contract, including gate collision and stacked altitude. Either support the corresponding native gate progression correctly or select a fully validated local arena/entry pair. Hiding a transport object is insufficient evidence of traversability.
4. Version corrected configurations. New runs use the new version; existing frozen runs require an explicit recovery/migration policy instead of silently mutating ongoing combat rosters or duplicating spawn receipts.
5. Add regression fixtures derived from the failed real topology and object-state contract. Existing generated formation and auto-transition tests cannot alone close this failure.

## Acceptance after implementation

One complete normal-entry run, with two party members and a separate party for isolation:

1. Place both party members outdoors with `!tp 527 -128 -33 0`; enter through the normal Tofullero entrance. Do not teleport into asset 1087 as proof of entry.
2. Both players must occupy the same run, move normally to the first group and start combat without crossing an unusable gate. The initial roster must match the reviewed first-room evidence and exclude the final boss unless that evidence explicitly requires it.
3. Complete every encounter. Verify ordered transitions, no skipped room, no early/final duplicate boss, one reward settlement per victory, and all party members returning to exploration. Reconnect between rooms and verify current-room restoration.
4. A separate party must have an independent run and group identities. Finish the first run and verify normal exterior exit and a fresh run's first encounter.
5. Repeat normal Miabuelita entry and a complete run, then repeat accepted Jalató entry/progression/exit as regression checks. Preserve quest criterion rejection for the excluded temporary state.

Current Tofullero acceptance is blocked by the already reproduced first encounter failure. Hector should not be asked to kill the inaccessible group or bypass the gate administratively to demonstrate success.
