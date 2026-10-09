# Cra event producer code audit — 2026-10-08

Read-only inventory of breed9 event producers and retained lifecycle. This is not functional acceptance. The JSON contains all 40 class spell records, 50 listener definitions, native masks, direct parents, source hashes and the complete 21-event mapping. No tests or services were run.

## Confirmed gaps

- **2288:** `combat_state_decurse.py:28` executes321 without any phase emitter; factory `combat_effect_runtime.py:1361` does not bind an event lifecycle. Native sources350821/347121/352099/352104/352262 publish2288 in PK mask6, but the production route never delivers it. Precision recomputation398436 subscribes to2287/2288;304 correctly emits2287.
- **2177:** source352184 is null400 with emitted mask6[2177]. `combat_stat_handler.py:268` and `:350` publish null phases only for an activation clone or area target. Normal actor nulls have neither; factory `combat_effect_runtime.py:1273` prepares only eWQ/eWR. Therefore declaring mask6 support does not close state7794 listeners350010/352185.
- **1010:** no explicit publisher or fullgraph mask6 producer. Death emits1013 (`combat_ordinary_events.py:48`), preserving actual killer/UID. Listener351404 (nested under351403, active7807) and removal-only416440/416442 require1010. Its original external timing/source remains unproven;1013 cannot be treated as an alias.
- **1012/1015/1018:** absent publishers, restricted to185234/185235 cosmetic branch.185234 requires `GetActiveCosmeticId(5)>0`; this is a conditional gap rather than an empty-cosmetic nominal failure.

## Required event matrix

| Event | Production status | Source |
|---|---|---|
| 1 | produced | `server/wakfu_server/combat/combat_ordinary_events.py:214` |
| 2 | produced | `server/wakfu_server/combat/combat_damage_events.py:40` |
| 74 | produced | `server/wakfu_server/combat/combat_current_stat_consumer.py:51` |
| 79 | produced | `server/wakfu_server/combat/combat_ordinary_events.py:481` |
| 202 | produced | `server/wakfu_server/combat/combat_current_hp_restore.py:73` |
| 1001 | server_policy | `server/wakfu_server/combat/combat_server_spell.py:395` |
| 1002 | server_policy | `server/wakfu_server/combat/combat_server_spell.py:348` |
| 1003 | server_policy | `server/wakfu_server/combat/combat_server_spell.py:310` |
| 1010 | absent | `server/wakfu_server/combat/combat_ordinary_events.py:48` |
| 1012 | absent_conditional_cosmetic | `server/wakfu_server/combat/combat_ordinary_events.py:214` |
| 1015 | absent_conditional_cosmetic | `server/wakfu_server/combat/combat_ordinary_events.py:214` |
| 1018 | absent_conditional_cosmetic | `server/wakfu_server/combat/combat_ordinary_events.py:214` |
| 1024 | server_policy | `server/wakfu_server/combat/combat_spell_transaction.py:103` |
| 1025 | server_policy | `server/wakfu_server/combat/combat_spell_transaction.py:103` |
| 1028 | server_policy | `server/wakfu_server/combat/combat_server_spell.py:310` |
| 1037 | server_policy | `server/wakfu_server/combat/combat_server_spell.py:350` |
| 2177 | missing_direct_null_phase | `server/wakfu_server/combat/combat_stat_handler.py:268` |
| 2235 | produced | `server/wakfu_server/combat/combat_current_stat_consumer.py:51` |
| 2276 | produced_with_null_gap | `server/wakfu_server/combat/combat_damage_events.py:40` |
| 2287 | produced | `server/wakfu_server/combat/combat_state_handler.py:186` |
| 2288 | absent_state_decurse_phase | `server/wakfu_server/combat/combat_state_decurse.py:28` |

## Context and retained lifecycle limits

Native mask indices0–5 are subscription channels; index6 is emitted bits. They are not interchangeable (`combat_trigger_masks.py`). Ordinary source phases provide channels1/2/3/4 and actual Qe metadata. External policy channels6/60/61 use `NativeExternalEvent`, whose triggering UID/caster/target/context are null (`combat_event_replay.py:124`). Active spell scope supplies1024/1025 spell identity; it does not supply an original killer or triggering state. Typed eWu events carry the actual state reference (`combat_event_replay.py:324`).

1024/1025,1028/1003 and1001/1002/1037 are explicit Wakemu server policies with actual production callers. They are not claimed as recovered original server callers. Turn global delivery (`combat_turn_events.py:31`) enumerates actor history rather than the exact global PV iterator used by cast events; no concrete Cra area listener failure is certified here.

Oldgraph missing beacon states7779/7780/7781 were independently resolved in the actual combat-state catalog. Their null/display roots have no subscription masks;357566/357565/357567 are explicitly `False` display damage roots. They do not constitute missing beacon damage subscriptions. Source data and their hashes are recorded in the JSON supplement.

Probability, criteria, target selectors, ownership and state guards remain required. A source subscription does not prove that a legal class context executes it. No mutation or test execution was performed by this audit.

## Implementation follow-up

The direct-null phase gap above was subsequently repaired in `combat_stat_handler.py`: ordinary actor eXE and activation clones now both emit one phase1/2/3/4 sequence, with the actual allocated/clone UID, actual transferred value and PK emitted mask6. Area targets retain their separate mutually exclusive phase branch. No eWQ/eWR preparation or PA calculation is applied to null400. Original audit findings remain a record of the pre-fix source; focused validation is tracked separately.
