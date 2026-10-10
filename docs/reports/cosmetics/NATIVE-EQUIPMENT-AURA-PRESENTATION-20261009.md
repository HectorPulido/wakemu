# Native equipment and cosmetic aura presentation

## Scope and result

Offline inspection of the installed Wakfu client found 172 item passive-effect roots with native flag `eVl.rxf` (`IS_RELIC_AURA`, numeric 35). Joining with the installed equipment rules and cosmetic action catalog separates them into **127 learnable category6 auras and 45 equippable equipment references** (172 distinct item references). All 172 use generic 400 / runner `eXE`, have empty numerical parameters, and contain a parsed `Pt` particle-system presentation instruction. Empty numerical parameters therefore establish no stat contribution, but do not establish absence of visual behavior.

This audit does not modify combat, spells, running services, or databases. The existing combat aura runners 316/338 are a separate mechanism; see `../combat-inventory/native-aura-runners-316-338-20261008.md`.

## Reproducible export

`sniffer/java/ExportRelicAuraEffects.java` exports all 172 roots and all passive effects of the selected DOFUS equipment / learnable aura references, totaling 197 rows. The private generated artifact is `.runtime/local/relic-aura-equipment-roots.json`.

Each row includes the item reference/level, effect root, generic/runner, flag35, raw installed `aNw` metadata, parsed native presentation instructions, and particle reference. The artifact records the installed client jar SHA256. Raw field `eto` contains exact criteria, `etl` contains the presentation script, `etw` contains flags, and `esN` through `esT` preserve native event arrays without speculative event-name mappings.

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-rift-native-oracle sniffer/java/ExportRelicAuraEffects.java
java -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' ExportRelicAuraEffects
```

Both commands passed on 2026-10-09. This executes the installed catalog loader and presentation parser; it does not execute graphics or prove a live server publication path.

## Native consumer evidence

`bfb.a(eVn, OY)` dispatches a `Pt` (`PARTICLE_SYSTEM`) through `Pt.aYG()` (particle reference), `Pt.aYH()`, and `Pt.aYI()` into `bfb.a(int, boolean, Py, boolean, aBn, eVn)`. That method forwards the instruction to `bge.a(beS, eVn, int, Py, aBn, boolean, boolean)`.

`bge.a(bgb, big)` checks flag35 and the `RELIC_AURA_DISPLAY` preference (`bWD.lAq`), including hidden and local-player-only settings, before creating the selected `FreeParticleSystem` through `afX.sj(particleReference)`.

The `OY` lists returned by `eVn.fKV()`, `fKW()`, and `fKY()` are presentation instructions, not gameplay event-trigger IDs. The exporter preserves both the parsed lists and the original event arrays separately.

## Examples

| Item reference | Effect root | Particle | Criteria |
| --- | --- | --- | --- |
| 24083 (Gelanillo) | 237492 | 900033 | `GetFightModel()<=0` plus absence of states 3092, 2623, 3220, 3219, 3202, 6237, 6804 |
| 29764 | 329228 | 900073 | `GetFightModel() <= 0` |
| 29789 | 329253 | 900126 | `GetFightModel() <= 0` |
| 31388 | 376146 | 900153 | `GetFightModel() <= 0` |
| 32355 | 391362 | 900169 | `GetFightModel() <= 0` |
| 33396 | 417611 | 900183 | `GetFightModel() <= 0` |

All five learnable cosmetic aura examples also carry flag35. Their metadata uses `ITEM_EQUIP` scope and particle script `start|1|end|12|type|2|data|<particle>;true|broadcast|false`. Cosmetic category6 selection and passive presentation publication must be considered separately: publishing only the selected aura reference does not by itself demonstrate that its passive root reaches the native presentation consumer.

DOFUS equipment references 20720/24110 grant state4570, 28417 grants 6731, 31361 grants 8251, 32351 grants 8784, and 33395 grants 9364 through generic304 / `eWu`. Those roots are not themselves flag35 particle instructions. Their resulting state effect trees require their own runtime support audit; do not replace their gameplay behavior with a cosmetic particle.

## Implementation implication

`equipment_stats.passive_null_marker` can correctly ignore generic400 for numerical stats while an independent presentation publication path preserves its visual metadata. The currently exported numeric equipment catalog lacks flag35 and particle scripts, so it cannot answer whether the visual system is complete. This report and exporter provide evidence for a later general implementation without changing combat or spell behavior.
