# AI inventory path ordering stall

A live incident in fight 145, turn 7 recorded approximately 45,811 ms in catalogue inventory before any HTTP catalogue request. The sampled stack ran through `_inventory_scan` → `files` → `Path.__lt__` → normalized path parts / path parsing. This differs from the preceding source-fingerprint incident; no dictionary fingerprint semantics were changed here.

## Narrow correction

Inventory previously sorted enumerated paths using `Path` objects as keys. Sorting repeatedly invokes path normalization and component comparison across O(n log n) comparisons. Every entry in one root enumeration shares the same root prefix, so the identical POSIX ordering is obtained by constructing a tuple of relative path components once per entry.

The new key is `tuple(relative_name.split('/'))`, not the slash-joined name: component order and slash-string order differ for names such as directory `a` and sibling `a!`. Owner deadline checks run while constructing keys and immediately after sorting. The complete fresh scan, source signatures, logical aliases, database catalogue release, and receiver seal are unchanged.

## Verification and limits

A regression compares the manifest against legacy `sorted(Path)` ordering using nested names chosen to distinguish component and slash-string sorting. It forbids `Path.__lt__` during inventory and verifies that a subsequent new nested file remains visible. All nine catalogue-cache tests pass, including source changes with preserved mtime, corrupt snapshot repair, and alias/removal coverage.

A synthetic 20,000-path sort produced identical order: Path-key sorting took 281.467 ms; component-key sorting took 28.564 ms in one local run. This isolates the sorting mechanism, not total live turn latency.

A helper in the running world container measured updated inventory at 484.152 ms on its first call and 92.242 ms warm, with 18,474 logical entries and 9,435 content objects. A separate controlled helper compared old and new sorting in memory over identical source roots: all four resulting full manifest digests matched (`2dc20f702c3d46367d755f2d069b0f9c5358fa22c9ddbd7baac347cbc0e8abd8`). Whole inventory timings were noisy: old 943.020 / 175.711 ms, new 201.779 / 392.688 ms. They do not establish a stable live latency improvement.

The previously measured inventory had 18,381 entries; only 93 additional entries were present here. That modest growth does not explain a 45-second stall. The live stall was not reproduced by the helper; scheduling contention, cache pressure, and concurrent preparations remain possible contributors. Deployment acceptance must verify real turn preparation and profiler captures rather than claiming the entire performance incident is solved by this change.

No service was restarted for these measurements. Helpers used the normal private preparation cache without changing game state.

## Integration and deployment

Thirty-nine focused AI context/inventory tests passed, including file changes,
new/removal detection, ordering, aliases, sealed sources and database revision
identity. Forty-five focused tests cover concurrent characteristic/effect/replay
changes included in the complete image. Broader spell transaction fixtures still
fail before their assertions when native actor LOS height is absent; this was
not reported as a green full suite.

The current world service started after the ordering patch and contains the
verified r67 game source snapshot (687 hashes). Its mounted AI source includes
the tested ordering and deadline checks. Health passed and the continuous
profiler is active with one-hour retention. Real combat latency acceptance is
still required; helper measurements did not reproduce the original 45-second
incident.
