# Multiplayer errors: evidence, causes and repair tracking

Times below are UTC from server JSONL; client logs display approximately five
hours earlier. Private screenshots and selected events are preserved under
`.runtime/local/evidence/multiplayer-20261009/`; do not commit these artifacts.
Participants: Npers (Cra, character 6) and Prueba Oficios (Iop, character 4).
This is a shared combat lifecycle investigation, not missing class spells.

| Failure | Evidence | Confirmed cause | Repair status |
| --- | --- | --- | --- |
| Both players Ready, encounter remains in placement | Fight 87, 04:18:57: `Missing actual native fighter participation authority` | Joined actor was added to the roster without native PV or QI registration; relocated physical XYZ was stale | General admission producer deployed in r48; fresh PvE manually reached active combat |
| Surrender during placement disconnects | Fight 87, opcode 13952: `NoneType` has no attribute `fight`, dispatcher line 5619 | Placement legitimately has no runtime, but dispatcher dereferenced it | Dispatcher reads shared fight; deployed r48. Later disconnects below have a separate cause |
| Reconnect rejects subsequent checkpoints | Fight 87, 04:33 onward: `Checkpoint writer ownership changed` | Durable participant generation advanced while worker owner generation remained old | Drained, durable-first generation transition deployed r48; 11 worker tests passed |
| Reconnect displays different actor populations | User screenshots: Iop sees itself; Cra sees both PCs but no NPCs | Server retained all five actors and serialized complete bootstrap. Client presentation failure is observed; deletion is not proven | Do not invent a missing spawn packet. Recheck after registration and timeline corrections |
| First multiplayer turn uses different actors on client/server | Fight 88, client 23:44:25.915: expected actor 4, requested actor 6; current/next order disagree | Client independently computes a different initial order; first actor advance precedes authoritative timeline restoration | General multiplayer first-boundary restoration implemented; automatic verification pending |
| Cra deck disappears, resources display another actor, neither player can move, repeated `Atajo ya presente` | User screenshots `0me8sr`, `nc38BU`; user later observed recovery | Same fight 88 timeline assertion triggers repeated native recovery. These are associated symptoms; a separate deck codec defect is not established | Verify deck/control and resources after timeline fix; do not filter shared gameplay packets by guess |
| Iop disconnected at PvE completion and level-up toast shows undefined after logout | Fight 88: 04:47:06.403 `Stale health update`; client connection lost before native end presentation. XP/level persisted | Idle world health regeneration ran while still attached to finished combat, with stale cached health/level | General exploration-only health tick guard implemented; tests pending. No health CAS guard removed |
| Dungeon appears empty / Cra not advanced immediately | Fight 88 both `dungeon_transition_deferred`; user reconnects Iop and both advance with NPCs present | Party transition waits for the missing Iop return; observed progression resumes after reconnect | Treat as consequence of disconnect until retested; no barrier bypass or forced party movement |
| Friendly challenge accepts but Ready fails | Fight 89: accepted 04:49:18; Ready 04:49:25: `Missing complete owned native QI population` | Duel constructor omitted serialized arena QI snapshot before fighter slot initialization; native PV initialization also absent | Source-backed constructor correction in progress; same authority used for PvE required |
| Friendly challenge surrender disconnects Iop again | Fight 89: 04:50:01.336 `Stale health update`; cached world HP differs from settled combat HP | Same idle health tick during attached settlement as fight 88 | Covered by the general health guard; verify actual forfeit and both returns |

## Existing verified repair baseline

r48 is the complete shared server image, not an overlay. Native join tests
4/4, shared/start/Ready tests 55/55, actual Cra/Iop regressions 7/7 and worker
tests 11/11 passed. Withdrawal/dispatcher: 28 tests, 6 isolated PostgreSQL
skips. This automatic baseline did not prove initial client timeline agreement
or complete dungeon/duel visual acceptance; the new reports keep those open.

## Repair and deployment requirements

Preserve actor ownership, strict native authority checks, checkpoint fences,
all original effect trees and private settlement delivery. New fixes must
cover the shared system rather than particular class, map or actor IDs.
Before restarting the single world service, validate the complete current
checkout and compare its source manifest with the complete built image.

## Complete manual acceptance after fixes

1. Start a fresh two-player PvE encounter; join during placement and Ready
   both. Repeat with reversed Ready order and with placement timeout.
2. On the first and following rounds, each client must show the same actor
   order and current turn. Only the owning character can act. Its own deck,
   HP, AP, MP and WP must remain correct; no duplicate-shortcut spam.
3. Reconnect each client during placement and active combat. Both must see
   all PCs and NPCs and continue without recovery loops or checkpoint errors.
4. Finish a dungeon room while the lower-level character gains a level.
   Neither client disconnects; both receive individual results and, after
   returning from the result, advance to the next room with its monsters.
5. Surrender one player in PvE placement and active combat. The other keeps
   the same encounter and can finish normally.
6. Challenge the two characters, Ready both, move and cast on their own
   turns, then forfeit. Both return to the world without disconnecting,
   stale-health errors or lost class decks.

No visual item above is marked complete merely because a unit test passes or
the client eventually recovers.
