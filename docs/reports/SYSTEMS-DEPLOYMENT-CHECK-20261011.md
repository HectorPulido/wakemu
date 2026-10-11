# Systems deployment hash check — 2026-10-11

Read-only SHA-256 comparison of shared checkout files with `/app` in the running `wakfu-local-world-1` container (`532d507ebddb`). The container was queried only with `docker exec ... sha256sum`; no tests, service changes, or database operations were run.

**Result:** 35/35 selected files are present. 34 match the shared checkout byte-for-byte. One differs: `local_game_server.py`. No selected path was absent.

| Scope | Result |
|---|---|
| Stele dispatch/state, combat adapter, dungeon difficulty/scaling/modulation/rewards | Present; all hashes match |
| Rift runtime/policy/rewards/combat | Present; all hashes match |
| Tactical markers and battleground borders | Present; all hashes match |
| Wells/lights environment interactions and seats; flora ecology | Present; all hashes match |
| NPC capture/world contracts (132) | Present; all hashes match |
| Hero switch health (136) | Present; all hashes match |
| World dispatcher | Present but changed; hash details below |
| Migrations 125, 127–129, 131–133, 136 | Present; all hashes match |

The only mismatch is:

| File | Shared checkout SHA-256 | Running image SHA-256 | Status |
|---|---|---|---|
| `server/local_game_server.py` (`/app/local_game_server.py`) | `bb656ef629ae711bcd04e699dbd287b4fe09330164bfeaf68535d553d11369f5` | `7a4dd8a8134524a8155c448def6e3867ceab653bee5b11edb95490882adb2779` | Changed |

Matching module paths: `server/wakfu_server/combat/combat_session_adapter.py`; `server/wakfu_server/maps/{dungeon_stele.py,dungeon_stele_states.py,dungeon_combat_scaling.py,dungeon_scaling_entry.py,dungeon_difficulty.py,rift_policy.py,rift_runtime.py,rift_rewards.py,rift_currency_rewards.py,npc_world.py,npc_capture_contracts.py,npc_capture_scene.py,environment_interactions.py,environment_seats.py,flora_ecology.py}`; `server/wakfu_server/characters/{dungeon_modulation.py,dungeon_modulation_publication.py,dungeon_modulation_health.py,heroes.py}`; `server/wakfu_server/combat/{combat_rewards.py,rift_combat_adapter.py,rift_dispatch_combat.py,combat_tactical_markers.py,combat_border_policy.py,combat_battleground_border.py}`; and `server/migrations/{125_dungeon_difficulty_authority.sql,127_dungeon_automatic_modulation_policy.sql,128_dungeon_native_scaling_supplement.sql,129_environment_interactions.sql,131_native_random_combat_borders.sql,132_native_captured_npc_contracts.sql,133_native_dungeon_steles.sql,136_hero_switch_health_baseline.sql}`.

This check establishes file presence and content identity for the selected modules only. It does not establish runtime behavior or explain the `local_game_server.py` divergence.

## Subsequent completion check

The same active container remains healthy. The original35-file comparison above is a timestamped observation; subsequent implementation has changed the shared checkout. A fresh targeted read confirms these post-publication features are absent from that image:

| Feature | Active image |
| --- | --- |
| Score damage/runtime completion | Not deployed |
| Configurable rarity allocation | Not deployed |
| Trusted native administrative chat rights | Not deployed |
| Ranch portal session/dispatcher repair | Not deployed |
| NPC objective facts and three additional roots | Not deployed |
| Native intergame transport | Not deployed |

Native bag scene hydration helper is present, but the new dispatcher hook/session repair is not. Steles, tactical markers, Rift50× and transactional hero initialization still match their qualified implementations. File presence alone does not establish native graphical acceptance. No service changes were made for either comparison.

## Post-reboot verification of prepared additions

The user-authorized recovery restored the same published World image74d90f,
with all nine services running. A fresh read-only comparison confirms new
rarity allocation, native intergame transport, Ranch session, seat141 definitions,
protector NPC142 and physical nation-board modules remain absent. The existing
boss_score module differs from the completed shared implementation. Evidence:
`.runtime/local/systems-completion-20261011/post-recovery-feature-check.json`.
No new source/image publication occurred during recovery.

Direct deployed wire.py comparison additionally confirms its format22 nation
projection already matches the current corrected implementation. Its only
current-source differences are the prepared ACCOUNT_INFORMATION administrative
rights projection. The old passport visual failure predates this entry-packet
correction; a new graphical result is required, not an assumption that it still
fails. Deployed source copy: `.runtime/local/systems-completion-20261011/wire-deployed.py`.
