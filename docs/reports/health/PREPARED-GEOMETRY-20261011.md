# Persisted prepared native geometry

Hector requested a map527 prototype followed by every available game map if
equivalence and performance succeeded. The prototype and all934-map preparation passed. Independent artifact checks and
55 affected regression tests passed. Runtime hooks are ready; not yet deployed.

## Storage and authority

PostgreSQL remains authoritative. Derived files live in
`.runtime/local/prepared-geometry`, mounted in World at `/data/prepared-geometry`.
No Redis round trip or full JSON decode is needed for a prepared map. Each
artifact contains validated immutable cells, directed edges, incoming/outgoing
adjacency, and compact forced movement masks/destinations. Runtime hydrates
Python containers from a checksummed binary marshal document; this is not mmap
and does not eliminate allocation or all first-load cost. Marshal files are
trusted private build outputs, never uploaded client input.

Keys include format version, pinned catalog revision, map identity and both
authoritative document SHA256s. Missing, damaged or obsolete derivatives fall
back to the existing native catalog validation path. Atomically replaced binary
and manifest files prevent readers from accepting a partial write. A process
retains at most four prepared bundles; existing geometry and terrain caches
retain their independent bounds. A future catalog revision requires new files.

## Map527 prototype

Against active catalog `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`:

- 65,285 cells, 226,614 directed edges and 261,140 forced-movement query rows.
- All cells, edges, outgoing/incoming adjacency and forced entries match the
  original validators. The selected arena dictionary also matches exactly.
- Artifact size: approximately26MiB.
- Two paired host measurements: original in-memory JSON decode plus validators
  and unchanged arena selection3.072–3.101s; prepared checksum/load plus same
  selection0.900–0.902s, approximately3.4times faster overall.
- Loading alone2.610–2.653s→0.279–0.282s. Selection alone increased from roughly
  0.45s to0.62s in these measurements; the cause is not established. We report
  the total improvement rather than claiming every phase improved.

Both comparison inputs were already fetched; PostgreSQL/network latency is
excluded. These are host results, not live World gameplay acceptance. Actor
snapshot initialization and spell preparation are outside this change.

## Rebuild and manual acceptance

The generic tool is `server/tools/prepare_geometry_artifacts.py`. With the
normal native catalog database environment and `PYTHONPATH=server`, run:

```sh
python server/tools/prepare_geometry_artifacts.py --map 527 --output .runtime/local/prepared-geometry
python server/tools/prepare_geometry_artifacts.py --all --output .runtime/local/prepared-geometry
```

The builder reads only the pinned published catalog, verifies source hashes,
validates data, writes/reloads derived artifacts and exhaustively compares them
against an independently prepared original. It stops on any mismatch. The
current inventory has934numeric combat maps and934compact forced exports;
manifest and legacy per-height documents are not extra maps. Unsupported maps
without native exports are not invented.

After a coordinated complete World build/restart:

1. On map527, run `!monster 2 4 1` near the character and start the fight once.
2. Check placement, movement, spell range and obstacles; finish the fight.
3. Start a second fight elsewhere on that map, then a fight on another map.
4. Expected: the same placement/movement rules and no new terrain errors; first
  map entry uses the prepared path. Compare server geometry phase telemetry,
  keeping actor initialization separate from static terrain load.
5. Automatic missing/corrupt/revision tests verify fallback; do not delete live
  files during a user's fight merely to exercise it.

## Final automatic verification

All 934 available maps passed exhaustive builder equivalence against the original
validators. An independent second pass loaded all 934 files with the current
published source hashes and verified checksums, scopes and container counts:
1,748,547 cells, 5,976,680 directed edges and 6,994,188 forced query rows.
Binary data totals 714,376,540 bytes (681.3 MiB); JSON manifests are additional.

The final 55-test gate includes the seven new artifact regressions, existing
arena selection/placement/duel/preparation tests, real native forced movement
and real-map surface integration. Result: 55 passed, zero failures/errors/skips,
2.882 seconds. Read-only PostgreSQL source was configured; Redis was unavailable
from the host and native readers correctly used PostgreSQL fallback.
Receipts: `.runtime/local/diagnostics/prepared-geometry-regressions-20261011.log`
and `prepared-geometry-reconciled-20261011.json` in the same directory.

Deployment requires the explicit shared-owner acknowledgements requested as
`prepared-geometry-20261011` in WORLD_COORDINATION.md. No runtime source overlay,
service restart or claim that the currently running image has these hooks is
made by this verification. The existing /data mount already exposes the prepared
files; a complete current World image is required to consume them.

A separate read-only Python process in the existing World container read,
checksummed and decoded the map527 artifact from the actual /data mount in
492.489ms (26,900,684bytes). Counts matched65,285cells/226,614edges/261,140forced
rows. This confirms mounted storage access, not gameplay deployment or total
combat-entry timing. No running World state was modified.
