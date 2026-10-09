# Complete active class batch after shared foundations — 2026-10-07

This offline batch covers all 383 active definitions across 18 classes. It uses ordinary initialized actors, native casting baseline data, actual resources, and enabled native area/granted-cast policies. It does not certify complete spell semantics, passive synergies, GUI delivery, or the running server.

[JSON evidence](class-engine-general-review-20261007.json) and [CSV cases](class-engine-general-review-20261007.csv) record 1,704 scenarios. All 379 tracked source/data hashes remained unchanged during execution. The expanded manifest includes combat modules, character inventory producers, protocol catalogs, map1134 fixtures and audit generators. Earlier manifests tracked fewer dependencies and must not be equated with this manifest.

| Observation | Cases |
| --- | ---: |
| Actor state changed | 1427 |
| Retention changed | 20 |
| Effect packets only | 58 |
| No effect observed | 142 |
| Cast rejected | 57 |

Thirty rejected rows are speculative self candidates whose selected native range excludes zero and whose actual conditional self exception is false. The audit retains their original rejection and trace while labeling the expected candidate rejection. They do not establish a range implementation bug. The remaining 27 rows group as follows; not every rejection necessarily represents a defect (notably the zero-probability native lottery requires scenario-legality review).

| Boundary | Cases |
| --- | ---: |
| Unsupported native predicate: IsInDiagonal | 2 |
| Teleport bypass of blocking cells requires native terrain policy | 2 |
| Native GS.ne requires positive remaining probability total | 2 |
| Native displacement collision requires AP-loss/events executor | 2 |
| Missing native caster/target alignment | 2 |
| Missing native triggering maximum amount | 2 |
| Unsupported native predicate: UseGateEffect | 9 |
| Unsupported native numeric predicate: GetCharacterDirection | 2 |
| Unaudited native target selector flags: 16384 | 4 |

The previous complete batch had 1,714 scenarios and 103 rejections. All 1,704 new keys also existed previously; ten obsolete generated keys disappear under corrected native baseline eligibility. Among shared keys, 46 previously rejected cases now progress: 36 actor changes, eight no-effect observations and two retention changes. All remaining 57 rejections existed previously, with no newly rejected shared key. The raw difference 103→57 must therefore not be described as proof that 46 complete spells are fixed.

The pre-batch integrated regression suite passed 125 tests with stable observed production sources. Important foundations include exact level-zero casting/effect data, complete owned spellbook lookup, corrected cwU empty-cell metadata, area ownership and optional Qf, GATE/faX registration, closest-specific-area queries, ordinary empty carry authority, shared flag37 displacement handling, and event packet regressions.

After this checkpoint, diagonal predicates, selector16384 and captured-area affiliation are being corrected using native bytecode/probes. This report remains a checkpoint: source stability during execution does not certify later edits. Conditional states, retained effects, actual summons and their granted abilities, critical branches, multi-cast/turn sequences and all passives still require broader semantic acceptance. No services were started, restarted or deployed.

## Per-class checkpoint

Counts are scenario observations, not completed spells. This batch does not equip passives or construct every required conditional state.

| Class | Active definitions | Cases | Actor changes | Retention | Packets only | No effect | Expected range rejection | Other rejection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Feca | 21 | 118 | 104 | 4 | 2 | 6 | 2 | 0 |
| Osamodas | 21 | 118 | 88 | 0 | 2 | 0 | 28 | 0 |
| Enutrof | 21 | 88 | 86 | 0 | 0 | 2 | 0 | 0 |
| Sram | 21 | 78 | 78 | 0 | 0 | 0 | 0 | 0 |
| Xelor | 21 | 92 | 85 | 2 | 0 | 2 | 0 | 3 |
| Ecaflip | 21 | 90 | 78 | 0 | 0 | 10 | 0 | 2 |
| Eniripsa | 21 | 96 | 88 | 0 | 8 | 0 | 0 | 0 |
| Iop | 21 | 80 | 74 | 4 | 0 | 2 | 0 | 0 |
| Cra | 21 | 82 | 80 | 0 | 0 | 2 | 0 | 0 |
| Sadida | 21 | 88 | 62 | 0 | 12 | 14 | 0 | 0 |
| Sacrier | 21 | 94 | 86 | 0 | 2 | 4 | 0 | 2 |
| Pandawa | 21 | 98 | 92 | 0 | 4 | 2 | 0 | 0 |
| Rogue | 21 | 88 | 42 | 2 | 12 | 30 | 0 | 2 |
| Masqueraider | 21 | 92 | 70 | 2 | 2 | 18 | 0 | 0 |
| Ouginak | 21 | 96 | 84 | 0 | 0 | 10 | 0 | 2 |
| Foggernaut | 21 | 96 | 80 | 4 | 8 | 4 | 0 | 0 |
| Eliotrope | 21 | 92 | 49 | 0 | 2 | 32 | 0 | 9 |
| Huppermage | 26 | 118 | 101 | 2 | 4 | 4 | 0 | 7 |
