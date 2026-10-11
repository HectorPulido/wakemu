# Independent retrospective hybrid-structure audit — 2026-10-10

The audit inventories **109 classic ordinary definitions / 107 distinct native names**. Neo variants, ultimate bosses, rifts and arcade definitions are excluded. It compares the frozen live database snapshot with explicitly selected latest source configurations, using native XYZ terrain, literal physical gates and literal classic transport destinations. No runtime writes were made.

## What the result means

`passed` means this bounded structural audit found no issue. It does not certify official room order, boss mechanics, complete client behavior, rewards or overall combat difficulty. `needs_manual_review` separates unresolved structure or historical guide differences from confirmed failures. An omitted optional object is not automatically a broken route.

The **37 previously validated active ordinary flows have no blocked result**: 22 have no audit findings; 15 differ only from archived guide encounter counts. Their current native room metadata is compatible with the active layouts. Tofullero remains manually accepted and passes this audit. Historical guide differences do not revoke that acceptance.

The database also contains 34 other ordinary legacy configurations using older fallback policies. These are not the 37 validated native flows: 12 contain encounter anchors unreachable in the audited native hybrid graph, 21 need review and one has no finding. Their existence must not be reported as newly completed native dungeon progression.

The latest source selection contains 99 ordinary definitions: 70 have no structural finding, and 29 need review. Four simplified final arenas are audited under a separate scope and explicitly remain pending full progression; they are never counted as completed multiroom routes.

## Current source structural follow-up

| Dungeon | Current finding codes |
| --- | --- |
| Base del Susurro | configured_encounters_fewer_than_native_room_metadata |
| Castillo de Wagnar | native_internal_transport_not_bound |
| Arena Danzante | configured_encounters_fewer_than_native_room_metadata |
| Vid Vil | configured_encounters_fewer_than_native_room_metadata, native_internal_transport_not_bound, reachable_large_native_regions_omitted_from_encounter_topology |
| Ratacumbas | native_separator_door_not_bound |
| Palacio Zollo | configured_encounters_fewer_than_native_room_metadata, native_internal_transport_not_bound, native_separator_door_not_bound, reachable_large_native_regions_omitted_from_encounter_topology |

These are follow-up triggers, not automatic claims that existing accepted gameplay is broken. Room-count metadata supports a review trigger but does not itself establish official stage order. Unbound gates or transports remain review findings unless an actual unreachable anchor or runtime-accepted bypass witness establishes a stronger result.

## Resolved context

- Kokolost’s extra guide encounter is an optional archmonster branch, not a fifth mandatory room. The latest four-stage main-route configuration retains the native annex terrain. Its optional documented archmonster encounter is separate from the mandatory room count and may be restored with exact native actor evidence.
- Conohos’ exterior and mine entries are alternative routes sharing one boss. Their guide encounters must not be concatenated into one mandatory chain. The latest four-stage exterior configuration records the alternate shortcut exclusions.
- Milubo’s current selected source configuration has four stages and includes its two physical doors and internal transports. Its earlier one-arena candidate is superseded explicitly, not selected by a blind maximum-version rule.

## Counterexample and lineage safeguards

Each configuration record includes the exact selected path, canonical configuration hash, native client/topology/input hashes, per-frontier encounter-anchor reachability and issue evidence. Optional native source exclusions are recorded separately from missing bindings. Classic `not IsNeoServer()` destinations are supported; Neo-server alternatives are not treated as ordinary destinations. `DUNGEON_3_PLAYERS` never implies three rooms.

If the offline graph reaches future-room terrain, the auditor reconstructs a concrete path and submits its walking segments to the actual runtime movement validator. A runtime rejection is labelled possible invisible-boundary review, not a demonstrated exploit. A runtime-accepted path retains the actual counterexample evidence. Portal edges are limited to configured frontier-enabled bindings.

Scope limits: the start asset map is audited; cross-map unresolved paths, optional annexes and historical guide encounters need separate evidence. Large omitted regions are review candidates, not automatically combat rooms.

## Reproduce

```sh
PYTHONPATH=server .runtime/local/verification-venv/bin/python server/tools/audit_classic_dungeon_hybrid_structure.py --active-snapshot .runtime/local/post-milubo-live-configuration-snapshot-20261010.json
PYTHONPATH=server:server/tests python3 -m unittest test_classic_dungeon_hybrid_structure_audit
```

Eight focused regression tests pass. Independent testing is delegated to Luna. The report stores snapshot SHA-256 `599f1a4e10aff32dd3527e65c8a7a492357d4e85f5aad82e5c1e9b8c8e51bab9`; source-selection precedence is explicit in the JSON.
