# Native QI selected surfaces: offline bulk export

QI.i(x,y,z) first checks exact arena bounds, then selects the surface index from the serialized cell mask's low six bits (`mask & 63`). It scans actual VD/VB chunks, selects the first matching chunk, obtains its ordered Vy array, and returns null immediately if the chosen index is outside its count or the chosen surface's bbl differs from requested z. It does not search another surface with matching altitude. QI.j returns false for a null selection and otherwise tests `bLD != -1`. Signed negative values other than -1 must not be replaced by a generic `bLD >= 0` walkability test. Mask blocked bit 256 does not by itself reject j.

The existing movement exporter `ExportAllCombatMaps` emits walkable coordinates and transitions; it discards blocked surfaces and surface index order. The LOS exporter `ExportNativeLOSTopology` emits Vz columns for Sf and different field semantics. Neither is an adequate producer for this QI.i/j contract.

## General exporter

`ExportNativeQISurfaces.java` accepts either one installed map archive or the native topology directory and a staging output directory. It decodes each actual topology chunk through aoG/VC/VB, preserving ZIP chunk order and native Vy surface order. Each nonempty column stores `[x,y,[[bbl,bLD],...]]`, including all signed flags and bLD=-1. Chunk bounds are retained, so omitted columns within those bounds are known empty rather than unknown missing input. Overlapping chunk bounds reject; no order is invented to resolve an ambiguous map.

The gzip output is separate from movement geometry, LOS and gameplay catalogs. The bulk manifest includes each map's topology hash, output hash and counts, plus all 123 client library hashes and the exporter source hash. Failures retain topology provenance and native stack traces with chunk identity where decoding fails. No monsters, running client, Python production or local catalogs were used.

## Actual client oracle on map 1134

`ProbeNativeQISurfaces.java` constructs a real QI with VD-wrapped installed VB chunks and invokes actual i/j. It verifies all selected native surfaces, wrong-altitude requests, out-of-count index requests, out-of-bounds coordinates, and masks including blocked bit 256. Results:

- 37,157 selections pass native j.
- 161,788 selections have bLD=-1 and fail native j.
- 198,945 wrong-altitude requests return null/false.
- 196,020 out-of-count index requests return null/false.

All checks pass. Private proof: `.runtime/combat-review-20261007/qi-surfaces/map1134/native-proof.txt`.

## Bulk result and limitations

Of 961 installed topology archives, 934 export successfully: 29,729 chunks, 9,632,196 nonempty columns and 9,869,586 ordered Vy surfaces. Twenty-seven archives fail in native decoding: 25 BufferUnderflowException and two native array-bound errors. Those maps remain unknown; no replacement geometry is synthesized. The exporter exits nonzero to preserve these failures.

Private output: `.runtime/combat-review-20261007/qi-surfaces/all-maps/`. Manifest SHA-256: `bc9f7f77141961543853388526201c29c147cc72c97ce953060cd68de63156ee`. The second complete export retained error hashes/traces; counts and failure groups matched the initial run.

Integration remains pending. A runtime QI surface lookup must combine the exact stored arena masks with this map's ordered columns, preserve absent/empty distinctions, selected index and exact requested signed-short altitude, and reject missing or stale map provenance. No existing gameplay catalog was imported or overwritten. The actual oracle proves map 1134 calls; export success alone is not independent j verification for every other map.

Compile: `javac -proc:none -cp 'client/lib/*' -d .runtime/combat-review-20261007/qi-surfaces/classes sniffer/java/ExportNativeQISurfaces.java sniffer/java/ProbeNativeQISurfaces.java`.

Probe: `java -cp '.runtime/combat-review-20261007/qi-surfaces/classes:client/lib/*' ProbeNativeQISurfaces client/contents/maps/tplg/1134.jar`.

Bulk: `java -Xmx1024m -cp '.runtime/combat-review-20261007/qi-surfaces/classes:client/lib/*' ExportNativeQISurfaces client/contents/maps/tplg .runtime/combat-review-20261007/qi-surfaces/all-maps`.
