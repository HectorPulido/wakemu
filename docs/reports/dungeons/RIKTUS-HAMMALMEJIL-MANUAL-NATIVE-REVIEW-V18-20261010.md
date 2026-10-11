# Riktus Elite and Hammalmejil: individual native review

This review reads installed client data and published catalog geometry. It does
not modify client files, capture tools, combat rules, or spells. Both candidates
are offline preparations; no runtime activation or deployment is claimed here.

## Hammalmejil, native definition 68

Native map 548 contains three reachable large arenas, matching its three-room
definition. The closed-region graph is a triangle rather than a linear bridge:

| Native gate | Regions | Local encounter frontier |
| --- | --- | --- |
| 19109 | 12 ↔ 5 | Opens after encounter 1 |
| 19110 | 5 ↔ 3 | Opens after encounter 2 |
| 19112 | 12 ↔ 3 | Native return opens at frontier 3 |

Entry `[2,0,0]` belongs to region 12. The explicit local order is 12 → 5 → 3,
then walking back through native gate 19112 to exterior source 19113. Its
literal destination is map 458, `[67,-41,0]`. No replacement transport, walking
edge, or gate was introduced. Hidden native door 19111 is retained as an annex
gate. The prior bridge-only extractor rejected a valid native cyclic graph.

Clockwise encounter order and ordinary quantities are local policy. Native boss
property 43 and dungeon membership identify Bilbylmeja Nacarada, reference 2464,
as the final boss. Formation for six players and all three encounters passes,
including directed ingress, engagement, future-frontier rejection and return
to the exterior. The candidate is
`HAMMALMEJIL-NATIVE-CYCLE-CANDIDATE-V17-20261010.json`.

Public cross-check: [the dungeon index](https://methodwakfu.com/donjons/) also
lists three rooms; [Wakfu.Guide](https://wakfu.guide/donjons/81-95/) describes
its boss mechanics but does not establish precise walking order. The similarly
named Marteaux-Aigris dungeon is unrelated and was excluded from this review.

## Riktus Elite, native definition 139

The old review removed only PositionTrigger 31790's displayed center
`[-2,-65,0]`. That center is not the full native activation contract. Installed
client class `bEH` decodes a count followed by exact `i32 x, i32 y, i16 z`
coordinates into `Re.bkT`; `Re.h(aBn)` tests membership directly. Trigger 31790
contains these three activation cells:

- `[-3,-67,0]`
- `[-8,-59,0]`, coinciding with native gate 13942
- `[9,-59,0]`, coinciding with native gate 13941

These are exact activation positions, **not polygon vertices or expanded
collision footprints**. Removing the first activation cell together with the
six native Door cells splits the formerly merged 1279-cell region into a
1080-cell shared region and a 198-cell boss arena.

| Stage | Native region | Cells | Local encounter |
| --- | --- | --- | --- |
| 1 | 7 | 844 | Shared first encounter |
| 2 | 4 | 221 | Western preliminary encounter |
| 2, optional transit | 52 | 198 | Eastern alternative retained without an extra fight |
| 3 | 0 | 1080 | Shared third encounter |
| 4 | 33 | 198 | Riktus Enmascarado, reference 4538 |

Doors 13937/13938 lead from stage 1 into the western/eastern alternatives;
13939/13940 join them to stage 3. Doors 13942/13941 and the third literal
activation cell form parallel stage-3 → stage-4 lanes. All three must remain
closed before the third victory. Every original native Door is retained, and
the trigger frontier uses ordinary server movement ownership without emitting
a fabricated Door update.

The [reviewed guide](https://methodwakfu.com/pvm/donjons/donjon-riktus-elite/)
explicitly describes eastern and western routes, a larger maze, and rocks
requiring bombs before the first room. This preparation implements an honest
**fixed-west local encounter policy**: it preserves eastern walking terrain but
does not claim restored durable east/west encounter choice or bomb puzzles.
It neither adds optional enemy groups nor invents destructible rock positions.

Four encounters contain 2, 4, 6, and 8 actors, with increasing native minimum
threat 314, 628, 942, and 1272. Only the last contains boss 4538. All four
six-player formations and complete native sequence witnesses pass. Candidate:
`RIKTUS-ELITE-ACTIVATION-CANDIDATE-V18-20261010.json`.

## General validation changes

`decode_native_interactive_activation_cells.py` retains the exact native XYZ
membership contract. The structural auditor now accepts PositionTrigger and
ZoneTrigger activation cells directly from read-only native payloads, permits
one native object to bind several distinct cells, and checks directed paths
through multi-cell zones. The runtime must reject each binding before its
frontier and accept it afterward. Actual checks pass for Riktus's new cell and
all nine cells of Base del Susurro's ZoneTrigger 16538.

Shared-arena sequential configurations are validated using their strict runtime
contract before suppressing misleading future-floor overlap findings: staged
enemy spawning is the boundary, not access to another physical room. This
exception does not apply to ordinary multiroom configurations.

Manual priority remains high for both dungeons: verify premature movement is
rejected on **every alternative lane**, all party members can reach each live
encounter, the final native return works, and reentry preserves the shared run.
Boss-specific spells, balance, decorative objects, optional treasures, and
Riktus bomb puzzles remain outside the certified route behavior.

## Automated acceptance recorded

Seventeen focused unit and structural-audit tests pass, covering literal native
activation decoding, malformed payloads, multi-cell ZoneTrigger membership,
runtime frontier rejection/acceptance, and the Hammalmejil cycle contract.

The focused isolated PostgreSQL gate also passes for Riktus Elite and Base del
Susurro: two tests, six players per dungeon, four victories each. It validates
actual directed native party walking before every encounter, authoritative
database frontiers, spawn receipt deduplication, victory settlement replay,
absence of fabricated Door packets for trigger objects, native completed exits,
and final instance closure. Results are under
`activation-cycle-pg-v18-20261010/`. This gate does not certify boss AI or rewards.

The final source/historical-snapshot structure audit covers 109 ordinary native
definitions and 107 distinct names. All 109 latest prepared configurations have
no structural blocker: 81 pass without signals; 28 retain guide-count or optional
native-link context for manual review. Historical deployed configurations are
reported separately and must not be mistaken for newly deployed changes.
