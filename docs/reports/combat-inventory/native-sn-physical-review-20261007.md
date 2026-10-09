# Exact Sn physical casting path producer

`combat_sn_path.NativeSnPathAuthority` supplies the existing static casting `path_query(cwN) -> bool` contract. It uses actual physical `efR` endpoints, ordered native `VB.a(Vy[])` columns, the last source surface with the exact short altitude selected by `VA.a`, and original `Sm.a` transition ordering. The destination altitude is not rechecked after the traversal. Same XY with different Z still performs the source-floor lookup and zero transitions. The fixed native 3,072-surface path cache and 32-entry transition buffer failure boundaries are preserved.

The straight-path overload configures radius but does not read it in its `Sm.a` transition routine. Height and jump capacity affect transitions. This branch must not acquire invented radius-footprint walkability tests. Transition logic preserves signed fields, murfin bit contracts, property 64 jump exceptions, native integer ceiling arithmetic, and the asymmetric single-surface versus multiple-surface ceiling branches. One multiple-surface branch intentionally reads the destination candidate's `bLf`, as the original bytecode does; it does not substitute the overhead source surface's flag.

Selected `cwN` queries the actual `QI.Z` after each successful transition on the source/current cell, excluding the final destination. The callback must bind current QI masks, not derive them from walkability. An actual target obstacle requires an explicit unregister/restore context manager, whose exit executes on success, failure, and missing-authority exceptions. Target presence and whether the environment is QI require explicit booleans. Unknown inputs remain rejected. Fresh private traversal caches replace shared native singleton caches and disappear after each call.

The general physical exporter retains each ordered surface as `[bbl, bLD, bLE, bLF, aYX, bLf]`; the earlier two-field QI.i/j export cannot supply Sm. `NativeSnColumns` checks map identity, topology source hash, schema, signed fields, complete chunk bounds, and overlap. A known empty column is distinct from an unavailable physical dataset.

The offline bulk export attempted 961 map archives: **934 exported**, **27 native decode failures** retained with source hashes and native exception traces. It contains 9,632,196 columns and 9,869,586 ordered surfaces, totaling 26 MB compressed. The private source bulk is under `.runtime/combat-review-20261007/sn-oracle/all-maps/`; the verified catalog is published under `server/protocol/native-sn-columns/`. Failed maps are unavailable, never reconstructed from movement or LOS data. Manifest SHA256: `98c1a44bd33852da62833575c9f26da0311618fe1469e7c4c2a43044d35f28fe`.

Original-client differential probes passed **12,000 Sm transitions with zero mismatches** and **4,000 Sn paths with zero mismatches**, including actual QI masks and native synthetic VB/Vy columns. The latter observed 669 successful and 3,331 unsuccessful paths. These verify the producer across generated physical inputs; they do not certify every spell, live obstacle lifecycle, or client display. Native sources and hashes are recorded in the accompanying JSON report. No service, game client, network connection, or database was used.

Rebuild the original-client probes/exporter offline:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/combat-review-20261007/sn-oracle sniffer/java/ExportNativeSnColumns.java sniffer/java/ProbeNativeSmTransitions.java
javac -proc:none -cp '.runtime/combat-review-20261007/sn-oracle:client/lib/*' -d .runtime/combat-review-20261007/sn-oracle sniffer/java/ProbeNativeSnPath.java
java -Xmx512m -cp '.runtime/combat-review-20261007/sn-oracle:client/lib/*' ExportNativeSnColumns client/contents/maps/tplg .runtime/combat-review-20261007/sn-oracle/all-maps
```

The bulk command intentionally exits 1 when any map's original native decoding fails, while preserving successful map files and the complete manifest. **Normal casting integration remains pending a complete live QI mask and target-exclusion producer.** The static casting engine can consume this callback without approximating terrain.

`ImportNativeSnColumns` independently pinned the private manifest above, checked all original-client library hashes, all successful and failed native topology archive hashes, every compressed output hash, every signed physical field, counts and complete chunk bounds, then atomically published the catalog. `NativeSnColumns.from_published(map_id)` reads only `server/protocol/native-sn-columns/` and verifies publication/manifest/output hashes. It never discovers private `.runtime` data. Source publication does not start services or certify live target exclusion.

Publication command (the target must not already exist):

```sh
javac -proc:none -cp '.runtime/combat-review-20261007/sn-oracle:client/lib/*' -d .runtime/combat-review-20261007/sn-oracle sniffer/java/ImportNativeSnColumns.java
java -Xmx512m -cp '.runtime/combat-review-20261007/sn-oracle:client/lib/*' ImportNativeSnColumns .runtime/combat-review-20261007/sn-oracle/all-maps server/protocol/native-sn-columns client/contents/maps/tplg 98c1a44bd33852da62833575c9f26da0311618fe1469e7c4c2a43044d35f28fe
```
