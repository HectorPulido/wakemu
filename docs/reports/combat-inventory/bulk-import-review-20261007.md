# Offline bulk-import review — 2026-10-07

## Scope

Read-only inspection of installed client sources, extraction tools, protocol catalogs, and runtime consumers. No Java exporter was executed, no catalog was overwritten, and no service or database was modified. This report covers catalog sections rather than individual maps. Bulk extraction and runtime behavior verification are separate deliverables; the user will perform final manual acceptance after automatic validation.

## Existing bulk pipelines

The installed client uses `client/lib/wakfu-client.jar` and **113** `client/contents/bdata/*.jar` shards containing native binary tables. The relevant exporters read these tables through `apw` using the pattern `%d.jar!/%d.bin`. The `.dat` files found under the client are JRE/VLC resources; they are not the combat catalog source used by these tools.

| Section | Existing exporter/converter | Current imported coverage |
|---|---|---|
| Class spell identity | Native `aNr` records; `spells.json` | 722 spells belonging to18 classes |
| Class spell trees | `ExportSpellEffectTrees.java` → `convert_spell_effect_trees.py` | 722 spell trees and11,528 effects; roots and parameter evaluations at levels1–200 |
| All native casting/references | `ExportNativeSpellCasting.java`, `ExportNativeSpellReferences.java` | 4,143 casting/reference definitions |
| States | `ExportCombatStates.java` → `convert_combat_states.py` | 6,129 states and43,952 effects;200 sampled levels plus raw roots and boundary metadata |
| Granted spell closure | `build_granted_spell_references.py`, `ExportGrantedSpellEffectTrees.java`, spell-tree converter | 167 spell trees and2,589 effects; native maximum spell level used by exporter |
| Areas | `ExportNativeEffectAreas.java`, `ExportEffectAreaTrees.java` | 1,436 area definitions and3,624 area-tree effects |
| Class innates | `ExportBreedInnates.java` | 18 breeds |
| NPC identity and abilities | `ExportMonsters.java`, monster encyclopedia/growth exporters | 2,874 monsters;3,091 distinct native ability spell references |
| NPC spell trees | Spell-tree exporter; `native-npc-spell-effect-trees.json` | Only spell 7962, with one effect |
| Native actor characteristics/properties | `ExportActorCharacteristics.java`, `ExportActorProperties.java` | 2,874 NPC profiles in each catalog;92 characteristic definitions and120 properties |
| Retained metadata | `ExportRetainedEffectMetadata.java` | Metadata for 178,337 effects; metadata is not an executable tree |
| Equipment, weapons, aptitudes | Equipment effects/rules, weapon combat and aptitude exporters; weapon converter | Separate bulk catalogs already exist; must be included in coordinated source manifests and closure checks |
| Sublimations | `ExportNativeSublimations.java` | 388 item records and zero recorded export errors |
| Casting adjuncts | Native limits, elements, critical availability, conditional costs, facing, target policies, HUD resources, lifecycle subscriptions and runtime metadata exporters | Existing dedicated exporters; completeness requires per-section count and source validation rather than assuming a common manifest covers them |

The spell-tree exporter recursively follows `aKX` group children, preserves native criteria, flags, masks, timing, selectors, HMI actions and area metadata, and evaluates parameter arrays through the installed native client. This imports definitions; it does not implement criteria, family runners, event producers or client synchronization.

## Concrete missing coverage

The union of class, granted and NPC spell-tree IDs currently contains **874 distinct IDs**. The native casting catalog contains **4,143 IDs**, leaving **3,269 casting IDs without a tree in those three catalogs**. This is a catalog difference, not proof all those spells are reachable or legal player spells.

NPC identity import is broad but NPC spell-tree import is narrow: the monster catalog lists **3,091 distinct ability references**, while the dedicated NPC tree catalog contains only **7962**. A complete bulk pass should resolve all valid NPC references and record unresolved/non-spell references explicitly, rather than treating one Wonejo attack as complete NPC support.

Grant discovery follows family 649 in class/state/optional extra tables. It checks constant reference slopes and fails explicitly for a scaled reference. It filters discovered IDs against the installed casting catalog. Therefore absent-installed references need an explicit rejected-reference report, and dynamically scaled references require exhaustive native level evaluation. The documented procedure repeats discovery/export with `--extra` until no new references; final fixed-point proof should be recorded.

Native state level arrays are sampled at 1–200. Raw roots are retained even when outside that interval, and the exporter contains boundary probes, but this is not exhaustive execution metadata for all possible signed-short levels. Class-tree exports also use1–200; the granted exporter instead uses each spell's native maximum. These different level domains need an explicit policy and gap report.

The 178,337 retained-effect records do not imply178,337 imported executable effect definitions. All family references and dynamically referenced states, areas and spells need closure validation against actual tree catalogs.

## Freshness and provenance

- `content-manifest.json` lists28 catalogs. All28 recorded SHA256 values match their current files.
- That manifest excludes most combat-definition catalogs, including class/state trees, native casting/references, granted/area/NPC trees, actor snapshots and retained metadata. Its successful check therefore does not certify the full combat import.
- The `spells.json` client JAR SHA256 matches the installed `client/lib/wakfu-client.jar`.
- Its bdata SHA256 matches installed `client/contents/bdata/66.jar`.
- All four recorded granted-tree provenance hashes match: class trees, state definitions, native casting and `ExportGrantedSpellEffectTrees.java`.
- Several structural catalogs expose only a textual source declaration, without a client JAR/shard/exporter hash. Source declarations are evidence of intended origin, not freshness verification.

## Effect313166: imported but conditionally excluded

The reported unit failure for missing effect313166 is **not an absent bulk definition**. It exists in `granted-spell-effect-trees.json` as family 28, with criterion `IsOwnSummon(3791)`; it is absent from the class, state, area and NPC tree catalogs.

`compiled_runtime_catalog()` consumes `merged_spell_effects()`. That function merges granted trees only when `WAKFU_NATIVE_GRANTED_CAST=1`; the default is0 and returns class trees alone. The unit assertion in `test_combat_granted_cast.py` requires313166 in the compiled catalog. Investigate test configuration, cache lifetime and intentional flag behavior before attempting a re-export. Changing import data would not solve the default-disabled consumer path.

## Proposed coordinated offline staging

1. Freeze installed client JAR, all bdata shards, localization JARs and relevant exporter/converter code hashes. Generate a single section manifest recording source hash, tool hash, parameters, level domains, counts and failures.
2. Write every exporter result under a new staging directory such as `.runtime/combat-review-20261007/bulk-staging/`. Existing Java tools with hardcoded outputs need an isolated output adapter or separate safe invocation environment before running; do not overwrite protocol files during discovery.
3. Export identity/casting first, then all valid spell IDs in bulk. Export all states, all area roots, innates, NPC ability definitions, equipment/weapon/aptitude/sublimation effects and native metadata. Reuse existing native exporters rather than inferring behavior from names.
4. Iterate reference closure until stable. Record IDs discovered from family 649 and other native reference mechanisms, missing definitions, filtered IDs, level-dependent references and unresolved semantics. Validate every root and child resolves; reject conflicting identities.
5. Generate machine-readable diffs against current protocol catalogs: added/removed IDs, changed parameters/criteria/timing/flags/targets, counts by section/class/family and downstream dependencies. Keep data extraction failures separate from unsupported runtime families.
6. Run deterministic conversion, source-manifest verification, closure/schema tests and runtime catalog compatibility against staging. Explicitly exercise consumer flags and process-lifetime caches. Build legal automated spell/event scenarios after import; compare expected values, state transitions, costs and delivered packets.
7. Review the complete diff before replacing catalogs. Use a coordinated atomic release of the complete catalog set with backups and a manifest; replacing independent files sequentially risks mixed-source catalogs. The current review does not perform that integration or authorize runtime changes.
8. Verify each case automatically, then prepare one complete manual acceptance route covering the18 classes and shared mechanisms. User tests occur at the end; do not use manual probes as the bulk import process.

## Boundaries

Bulk data import can eliminate repeated per-spell extraction and identify missing definitions. It cannot automatically provide authoritative summoned-actor lifecycle, area ownership, criteria semantics, passive event ordering, or native action delivery. Keep these implementation blockers visible while importing all definitions, then validate case by case through the same production entry.

## Reproducible staging tool

`server/tools/stage_bulk_combat_import.py` now provides a safe inspection and preparation path. Run from the repository root:

```sh
python3 server/tools/stage_bulk_combat_import.py --dry-run
python3 server/tools/stage_bulk_combat_import.py --prepare --output .runtime/combat-review-20261007/bulk-staging
```

The default and `--dry-run` perform reads only. `--prepare` requires a new directory beneath repository `.runtime`; it writes all installed casting references, SHA256 manifests, structural gap counts and an exact `export-plan.sh`. It never runs Java, starts a client, modifies protocol catalogs, or claims an import completed. The plan compiles the five required exporter classes into staging and exports all spell IDs using native maximum levels, all states and all effect-area roots. It includes class/state conversions. Area TSV conversion and a post-export semantic/closure diff remain explicit follow-up work before any catalog integration. Run the generated plan only after the coordinating agent freezes competing catalog work.

Validation: `python3 -m py_compile server/tools/stage_bulk_combat_import.py` passed. `python3 server/tools/stage_bulk_combat_import.py --dry-run` passed and reported4,143 casting references,874 covered tree IDs,3,269 missing tree IDs, and zero unresolved local child references in all five current tree catalogs. This validates local group closure only; it does not validate dynamically referenced spells/states or runtime execution.

## Completed offline bulk extraction

After the coordinating agent completed the current normal-cast audit, the seven-command staging plan was executed headlessly and sequentially:

```sh
bash .runtime/combat-review-20261007/bulk-staging/export-plan.sh > /tmp/wakemu-bulk-staging-20261007.log 2>&1
```

The plan exited0. All4,143 native spell IDs were exported, including3,269 IDs missing from the previous tree union. Staged results contain34,389 spell effects,6,129 states with43,952 effects,1,436 area definitions and3,624 area effects. A staging-only converter also produced `all-area-effect-trees.json` from the area TSV.

`verification.json` records unchanged client, exporter and original catalog source hashes; zero missing or extra spell IDs; zero unresolved local group children; zero cross-catalog identity conflicts under the runtime merger's identity fields; and81,965 combined distinct effect definitions. The reproducible validation script is saved as `verify-staged-catalogs.py` in the staging directory. Logs include nonfatal compiler annotation-processing and log4j configuration warnings.

**Integration remains blocked by a metadata gap:** `range_modifiable` is absent in all 4,143 staged spell-tree records. The existing exporter/converter do not serialize this field. Recover it from authoritative casting metadata and validate the full consumer schema before any production integration. Structural closure does not establish dynamic state/spell reference closure or runtime spell behavior. No protocol catalog was replaced and no service or client was launched.

Follow-up: [the range-flag bulk import](range-review-20261007.md) recovered this field separately for all 4,143 casting definitions and800 conditional rules. A strict, verified staging merge now contains it. The spell-tree export remains an effect-tree dataset; effective range belongs to the complete casting contract. The running server still needs the common selector/calculation correction, and the staged catalog set has not been integrated.
