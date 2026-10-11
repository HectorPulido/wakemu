# Prepared native static LOS columns

The runtime can reuse a local binary derivative of the published
`native-Sf-Vz-columns-v1` topology. Original column coordinates, surface order,
altitude, height, transparency, duplicate-column overwrite behavior and value
sharing remain unchanged. Walkability geometry cannot replace these columns:
LOS and movement describe different native properties.

The original Sf integer raster program and all live actor blockers are unchanged.
No actor state, resources, spell eligibility or dynamic visibility is persisted.

Artifacts are trusted local build outputs, scoped to the pinned catalog revision,
map identity and authoritative source SHA256. A checksummed manifest binds the
marshal payload. Missing, damaged or stale artifacts fall back to the catalog.
The runtime cache retains at most four prepared column maps. Binary loading still
allocates Python containers; this is not mmap or zero-allocation storage.

The serial CLI acquires both a common `.prepared-static-build.lock` in the output
parent and an output-specific `.build.lock`. It runs one isolated map worker at a
time with a sampled 512 MiB RSS guard, stops on first failure, and releases each
worker's memory at exit. Matching existing artifacts are verified and reused;
source geometry and native catalogs are never regenerated or changed.

## Prototype

Actual published revision:
`bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`.
Map 527 contained 168,804 columns. Every prepared column matched the original
source conversion. Host baseline JSON parsing plus column preparation took
0.62495 seconds; checksum plus binary load took 0.02304 seconds, approximately
27 times faster. PostgreSQL fetch is excluded from both measurements. The
artifact is approximately 2.8 MiB. These measurements do not establish total
combat speed or eliminate unrelated first-use costs.

## Operation

With the existing read-only catalog connection environment, run:

```sh
PYTHONPATH=server .runtime/local/verification-venv/bin/python \
  server/tools/prepare_los_artifacts.py --map 527 \
  --output .runtime/local/prepared-los
```

Use `--all` instead of `--map 527` for all published numeric map documents.
Each worker compares every prepared column against the original conversion.
The default runtime directory is `$WAKFU_RUNTIME/prepared-los` (`/data/prepared-los`
when WAKFU_RUNTIME is absent), overridable with `WAKFU_PREPARED_LOS_DIR`.
No service operations are part of preparation.

## Complete inventory qualification

The serial coordinator exited successfully after all 934 published numeric map
exports. All 9,632,196 ordered columns matched the source conversion. Binary
artifacts total 165,883,053 bytes. The existing map527 artifact was reused;
933 missing artifacts were prepared. Existing prepared movement geometry was
untouched. An independent streaming checksum reconciliation matched every
artifact against the active inventory scope and qualified per-map receipt.

Private receipts:
`.runtime/local/diagnostics/prepared-los-all-20261011.jsonl` and
`.runtime/local/diagnostics/prepared-los-reconciled-20261011.json`.

Tiny tests cover surface order and duplicate-column behavior, immutable output,
missing/stale/corrupt fallback, published revision reuse, exact native raster
results and live actor blockers evaluated afresh. The shared preparation safety
suite passed 5 tests. No service restart or deployment was performed here.

The final focused gate passed 12 tests: 7 LOS artifact/ray/CLI tests and 5 build
safety tests. CLI regressions explicitly prove that a matching artifact keeps
its binary and manifest bytes and modification times unchanged, and that a
corrupt artifact triggers exactly one LOS rebuild without invoking geometry
preparation. Final gate: 0.252 seconds on the host verification interpreter.
