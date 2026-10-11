# Selected-build runtime consumer audit — 2026-10-11

Source review and a bounded server publication correction for original17/34
and dependentE06. This report does not certify every gameplay consumer. The
correction affects world refreshes; combat and spell semantics are preserved.

## Traced authoritative paths

| Consumer | Actual source and boundary |
| --- | --- |
| Store hydration | `storage/store.py::character` reads owned build blobs, persisted selected index and revision, rejects missing selections, computes `effective_sheet_level`, then applies temporary competitive projection. |
| Build activation | `Store.activate_build` locks the lease/character, rejects active combat and temporary competitive projection, derives selected-sheet maximum HP, preserves health through `health_policy.reconfigure`, updates selection revision and reconciles mount state transactionally. |
| Equipment and aptitudes | `items/equipment_stats.py::bonuses` validates selected equipment against effective sheet level, resolves only owned UIDs, adds native mount-level parameters, shards, selected aptitudes and explicit modulation/territory stats. Unsupported effects remain explicit. |
| Joining player | `combat_session_adapter.py::player_actor` obtains fresh Store state, attaches territory bonuses, derives selected combat resources and actor effective level, then installs `build_player_snapshot`. |
| Joining hero | `combat_heroes.py::player_actor` uses the same selected resources/effective-level/snapshot pipeline. |
| Fresh combat snapshot | `combat_actor_snapshot.py::build_player_snapshot` rejects actor level disagreement with the selected sheet and checks maximum HP consistency. Native defaults plus owned contributions are installed before effects. |
| World full actor characteristics | `wire.py::owned_public_characteristics` explicitly includes every native default row, preventing a removed prior equipment contribution from surviving through an omitted row. |
| World build activation response | Actual13776 branch sends selection, mount reconciliation and `combat_lifecycle.outside_progression`. This path now completes its owned world characteristic section with the same native-default helper used by full World snapshots; `actor_stats` combat serialization remains unchanged. |

Real-level spell ownership is intentionally distinct from selected-sheet level.
`default_deck` already consumes `effective_level`; source validation using a
real level is not independently evidence of a wrong cast level. This audit does
not infer a spell-engine defect without tracing execution authority and the
original native producer contract.

## Confirmed and corrected: removed equipment contributions survived world refresh

The actual13776 build-selection response calls `outside_progression`, which
previously created a sparse format3 owned13046 refresh through `actor_stats`.
Switching from equipped native amulet2021 (mastery20 contribution9) to an empty
sheet omitted20 from the second message. The installed original consumer is
`eGo.zm` → `actor.frm().b(pl.SS)` → `ffh.b(tA)`; it updates only received rows.

The actual server payloads were decoded with original `csZ.dp` and `pl.aG` and
applied sequentially to the same original `ffh`: equipped9 → empty**9**, proving
the removed contribution survived. Applying the actual complete world snapshot
for the empty sheet to the same object reset it to0. This negative control
establishes the missing explicit reset, without a custom reconciliation helper.

The minimal correction factors existing full-world native default filling into
`wire.complete_public_characteristics`. `owned_public_characteristics` reuses
it. `outside_progression` completes only its already-serialized PC section,
preserving authoritative resources, overrides, initiative, wounds and the
remaining format3 bytes. It does not change `actor_stats`, active combat effects,
spell execution, equipment arithmetic or database state.

Regenerated actual payloads replayed through the same original consumer now
produce equipped9 → empty**0** (exit0), with the full-world negative control0.
Native critical baseline3 is preserved: equipped amulet5 → empty3. Three new
regressions and both existing equipment-return regressions pass **5/5**, including
WP/AP/MP overrides, initiative, wounds, native nonzero baseline and malformed
input rejection. Luna independently reviewed the helper scope and baseline/resource behavior;
its final focused gate passed **5/5 in0.588s** (execution session36100, exit0).
The receipt and scoped AST hashes are in `fix-review.json`; the owner original-JAR
before/after replay is recorded separately.

## Scope and reproducibility

Evidence directory: `.runtime/local/build-stat-runtime-consumers-20261011/`.
`pre-fix/` preserves original actual payloads and provenance; `oracle.log` records
the before result and `oracle-after.log` the corrected result. `provenance.json`
pins current serializers/fixtures. The Java source is private analysis only.

```sh
javac -J-Xmx128m -proc:none -cp 'client/lib/*' -d .runtime/local/build-stat-runtime-consumers-20261011 .runtime/local/build-stat-runtime-consumers-20261011/VerifyNativeSparseWorldStats.java
java -Xmx128m -Djava.awt.headless=true -cp '.runtime/local/build-stat-runtime-consumers-20261011:client/lib/*' VerifyNativeSparseWorldStats .runtime/local/build-stat-runtime-consumers-20261011/equipped_fmt3.bin .runtime/local/build-stat-runtime-consumers-20261011/empty_fmt3.bin .runtime/local/build-stat-runtime-consumers-20261011/empty_public_characteristics.bin
```

The complete actor/UI notification path is not certified by this kernel oracle.
An attempted `biB`/`eGo` UI callback reaches an unavailable offline renderer;
its failure is not gameplay evidence. Original `eGo` bytecode ties the actual
format3 section to the exact `ffh.b` consumer tested above. No client files,
services, live database state, active combat or spell semantics were changed.
Deployment and graphical acceptance remain pending.
