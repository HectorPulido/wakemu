# Native fishing resource review

Fishing is native profession **75**. The active PostgreSQL gameplay catalog contains 52 non-monster resources with 103 fishing actions: stages 2 and 3, 100 actions lasting 6000 ms and three lasting 5000 ms. There are no profession-75 seed actions. Fishing resources should therefore use a fixed depletion/respawn lifecycle rather than planting.

## Native approach authority

Installed-client `fyk.aaa(75)` returns 3; mining returns 1. `fyk.gE(distance,75)` accepts distances up to 3, and `fyk.a(height,sourceZ,targetZ,75)` always accepts the height. The exact usable surface list must come from native `VF.a(target,1,fyk.aaa(75),false,predicate)` and walkable player exploration surfaces. Cardinal adjacency and mining height validation are not valid replacements. The bytecode evidence is saved in `native-fyk-approach.javap`.

The dedicated exporters are `client-tools/inspection/ExportFishingSurfaces.java`, `ExportFishingNavigation.java` and `export-fishing-surfaces.py`. They preserve native ground suitability and call the profession-75 approach functions; they do not change mining, combat, running services or the gameplay catalog. Runtime exports live under `.runtime/local/fishing/`.

## Coverage limits

The installed terrain assets yield 3,823 suitable candidate surfaces across 41 maps, covering 32 resource references. Terrain suitability is not evidence of official spawn coordinates. The following 20 references have no suitable exported terrain: 291, 306, 412, 413, 414, 416, 417, 418, 419, 420, 422, 423, 424, 425, 426, 427, 428, 429, 561, 563. References 291 and 306 have families 19 and 21; the others have family 22.

Twelve references have only nonterminal (`cvF=1`) actions: 563, 561, 420, 428, 423, 422, 306, 291, 429, 425, 424, 426. Reference 306 additionally has item_reference 0, products 8111 and 9599, and nonzero native `bwX=4718188`; its behavior requires separate interpretation. Do not silently claim these are ordinary terminal fishing nodes. Common fish have `cvF=0`; multiple candidate products do not by themselves establish native selection weights.

## Concrete acceptance location

Resource 369 has level-0 stage-2 action 1670, fixed product 8105, duration 6000 ms. Map 527 has a suitable target at (-8,20,-4) with the native approach (-9,20,-3). Once installed at that target, `!teleport 527 -9 20 -3` puts a character on its verified approach. Stage 3 uses action 1470 and product 18788.

## Complete offline navigation result

All 41 candidate maps exported successfully: 3,823 resource target surfaces, 3,813 with at least one native walkable approach, covering 32 native-compatible references. Navigation decoding reported zero errors. Native approach counts include 4,620 distance-1, 1,772 distance-2, and 1,411 distance-3 entries. The broader terrain scan reports partial installed-asset decode failures separately; it does not silently infer missing topology.

## Prepared distribution and immutable authority

The explicit local full-coverage plan is `.runtime/local/fishing/plan.json`: 3,377 spots across 40 maps, 51 supported species, 19 marked local fishing ground fallbacks, zero occupied-position collisions with current plants and mining slots. It excludes 436 ambiguous-height surfaces and ten unreachable surfaces. Map 1264 contributes 398 surfaces at 199 XY positions, all ambiguous, so it remains excluded. Opaque resource 306 remains excluded.

Compact navigation release `20f2731c921701c025af2d8416696e5b01c7346fc9393408b47533c092cab5fa` was staged without global activation: 41 documents, 514,480 bytes. Documents retain native approaches, only their source-cell membership, installed-client provenance and SHA256 of the complete source export. Set `WAKFU_FISHING_CATALOG_REVISION` to this release for the dedicated reader. The earlier unused full-export release is not the deployment authority.

The dedicated planner uses resource UID range [2^61,2^62), separate from mining [2^62,2^63), and queries existing resources before allocating positions. Five native navigation regression tests pass using `PYTHONPATH=server .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p test_fishing_navigation.py`.
