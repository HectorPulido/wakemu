# Regional ecosystem list correction

The user screenshot of Xav the Baker's ecosystem window exposed a server projection error independent of accepted issue 27 (weather). The displayed Spanish family names identify native map 1134 / region 79101: family 113 (`Plantas de los campos`) and family 219 (`Muuugresa`).

## Native contract and root cause

Installed `wakfu-client.jar` classes `bRT.dT` and `bRU.dT` parse packet 12789 lists. Each list row receives its type from `bRN.Jk(index)` (monsters) or `bRN.Jl(index)` (resources). There are exactly three slots of each kind. Additional monster rows receive a null type; `bRQ.getName()` dereferences that type. Monster names resolve translation table 38 by family ID; resource names use table 37. Icon identity also uses the monster family, not an individual breed reference.

The open planting policy previously appended every globally available monster seed family (107 families) to every region's display. This exceeded the native three-slot contract and made the same global families appear in unrelated regions. Planting permissions and ecosystem presentation had been coupled incorrectly.

The active native ecology catalog has 720 maps and 274 regions. Every native list has at most three entries and no duplicate family IDs. One region (map 1365 / region 92601) includes the empty family sentinel -1 alongside family 1106. All 105 positive monster families and all three resource families have nonempty names in all four installed locale archives (English, Spanish, French, Portuguese). The sentinel has no translation.

## Correction

`planting_context.display_families` preserves native regional order, omits empty nonpositive slots, deduplicates family IDs and rejects more than three visible families. The encoder rejects attempts to append foreign test families. `planting_cells.region_context` filters population counts to this canonical list regardless of open planting policy. Native zero-count rows remain present.

Actual population aggregation already uses monster reference `family_id`, so multiple breeds and variants belonging to the same family contribute to one family count. Counts remain scoped by instance and region; defeated monster groups and nonliving resource stages are excluded by the existing population snapshot. No population, monster catalog activation, combat, client, weather or planting authorization changes are included.

For the reported region, the packet now contains exactly `(113, local_count)` and `(219, local_count)`, plus its native resource families 1, 2 and 10. A spawn definition mentioning another family does not grant that family an additional ecosystem slot.

## Validation

Regression tests exercise exact reported-region rows and counts with open policy enabled, every native region's packet layout, sentinel omission, duplicate collapse, slot overflow rejection and foreign family rejection. Independent verification passed39/39 tests (`test_planting_context` and `test_planting_runtime`), including PostgreSQL planting behavior, all274 native regions and names in four installed locales. Source, catalog and128 migration fingerprints remained unchanged. Evidence: `.runtime/local/verification-planting-context-20261011/tests.log` and `fingerprints.json`. The runtime database was read-only for catalog access; no deployment occurred.

Read-only native disassembly evidence: `.runtime/local/ecosystem-list-native.javap.txt` and `.runtime/local/ecosystem-native-types.javap.txt` (generated/private artifacts).

## Manual acceptance

After the parent deploys the complete current server checkout, reconnect and open Xav the Baker's ecosystem panel in Campiña de Bredsburgo. Expect exactly two monster families, `Plantas de los campos` and `Muuugresa`, and three native resource families, with no long monster scroll or unnamed extra entries. Visit another region and reopen its panel: expect its own native families and local counts. Return to the first region and verify its original family list. An open-policy monster seed from another region may remain plantable according to existing local rules; it must not add global families to the ecosystem panel. Weather remains the previously accepted implementation.
