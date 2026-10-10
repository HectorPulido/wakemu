# Dragon appearance facing capture audit

## Finding

The captured `Forma Draconica` cast does not turn the Osamodas toward a new direction. The first captured cast of spell 7349 is a self-target at the caster's own cell, and the published native cast-facing contract enables `turnCasterTowardTargetCell` with diagonals disabled. Its direction delta is therefore `(0, 0)`, for which the runtime facing mirror preserves the current direction.

The more relevant transition is combat entry. Immediately before fight 161, actor 19 moved in the world and the server recorded a final direction of 5 (WEST). The fight began about 2.4 seconds later. At the time of this capture, controlled-fighter creation explicitly initialized direction to 0 (EAST), discarding that world facing. The captured 7349 self-cast then left that initial combat direction unchanged. The subsequently added `INITIAL_PLAYER_DIRECTION = 1` and actor-direction serialization address this specific unsupported EAST bootstrap path.

The client animation selector also has a compact-direction branch: `aqj.gd` first checks `Fl.aKG()`, which is true when flag bit `0x10` is clear. In that branch it maps animation prefixes `3`, `4`, and `5` to `0`, `1`, and `5`; otherwise it leaves them untouched. Thus the `1_` prefix used by the new initial direction is stable across both branches. This audit does not claim that absent `933` metadata proves a visual gap, nor that the capture contains the client-side `AnimationNotFound` log itself.

## Capture evidence

- Capture: `.runtime/local/captures/2026-10-10T15-52-51.898203Z-cc8df813/events.jsonl`
- SHA-256: `af077700b799ef4ed9483400578cb2621d12deed030c912ad348359455bf5036`
- Offline decode: 27,238 frames; 605 outbound and 26,633 inbound; no incomplete streams.
- Fight 161 placement began at `2026-10-10T15:58:26.787079Z`; controlled actor: 19.
- The first actor 19 spell-7349 request is at `2026-10-10T15:58:35.081149Z` (capture sequence 21,454). Its decoded target cell is `[-9, -4, -1]`; the server cast diagnostics report `target_id: 19`, making it a self-target cast. The target-cell tuple is retained as reported and is not used to infer the actor's facing.
- The fight bootstrap at `2026-10-10T15:58:26.829349Z` is opcode 12847 (`cvb`). It lists actor IDs `[19, -1125899906876160]`; its first actor-data blob is the player payload for actor 19. Decoding the client's documented `FIGHTER_DATAS_WITH_XP` layout from that blob gives the position tuple `(-10, -1, -1, 1134)` followed by direction byte `0` (EAST). This is direct wire evidence that the fight bootstrap sent direction 0, rather than an inference from the pre-fight world movement.
- No actor-direction opcode 13655 appears anywhere in the capture. There is no combat movement between placement and the first 7349 cast.
- The last world movement before placement was logged at `2026-10-10T15:58:24.372195Z`: actor 19 from `(-8, -1, -1)` to `(-10, -1, -1)`, `steps: 2`, `final_direction: 5`. This is useful as the pre-fight world facing, not as evidence of the in-combat facing after bootstrap.

## Published native contract

Read-only PostgreSQL inspection returned active catalog revision `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`. The `native-cast-facing.json` document SHA-256 is `786399db4051fefdfa77bdd7614f5de2ac6f285c046d4ce8cae67a7cff1f5fad`. Its verified record for spell 7349 is:

```json
{"script_id":1002910,"status":"verified","template":1040,"turnCasterTowardTargetCell":true,"useDiags":false}
```

The runtime's cardinal cast-facing mirror returns without changing direction when the target delta is zero. That agrees with the captured self-cast.

## Bootstrap correction provenance

The capture predates the checked-out correction: the current `combat_orientation.py` and `combat_bootstrap.py` modification times are later than the captured cast. The pre-correction `combat_bootstrap.py` passed `direction=0` into the controlled fighter constructor. The current code uses `INITIAL_PLAYER_DIRECTION = 1` and `player_payload` emits `actor.direction`, keeping the runtime actor and bootstrap packet aligned. No services or database writes were used for this audit; packet decoding outputs were written only under `/tmp`.

## Limits

The network capture establishes movement, fight-entry ordering, the actual bootstrap direction, and the 7349 self-target contract. It does not contain the local client's animation error text or expose the HMI asset flag for assets 26/27. `aqj.gd`'s metadata-gated prefix behavior is confirmed from client bytecode, but the per-asset `Fl` bit for those two HMI records was not independently decoded here. A missing `933` reference is not evidence that state 7526's appearance transition is broken; its state/HMI transition chain must be assessed from its published native metadata and retained effect packets.
