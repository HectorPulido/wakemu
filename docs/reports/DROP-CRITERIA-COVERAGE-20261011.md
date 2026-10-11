# Drop criteria coverage — read-only audit, 2026-10-11

The current runtime native catalog contains 2,874 monster species and 16,138
direct combat-drop rows. Its SHA-256 is
`db31e2b205370fc73771573d33f374085ab1a27d222ef0601199eedf90792d36`.
This audit only read installed data and source. It did not edit `server/`, change
the client, write runtime settings, run a build or operate services. The Systems
`monsters-bulk-1297` source-freeze acknowledgement remains in force.

## Implementation follow-up — same-day scope change

The read-only inventory below records the earlier source-freeze state. That freeze
was subsequently released for Hector's requested implementation. Migration125
and `dungeon_difficulty.encounter_context` now supply frozen Stasis, competitive
entitlement (including exactly-at-cap actors) and the native declared reward
rate to settlement. The focused PostgreSQL lifecycle gate passed30/30, including
lowering Stasis between settled encounters while preserving past receipts and
profiles. [The difficulty report](DUNGEON-DIFFICULTY-AUTHORITY-20261011.md)
records the qualified combat scaling policy and integration limits.

The remaining unavailable simple-authority population is the union of Stele
and score rows, **902 direct rows** (634 + 268, with no overlap in this catalog).
Ninety-seven Stele rows also require Stasis; supplying Stasis does not authorize
Stele. Three score rows additionally require competitive entitlement. No current
server map or encounter producer provides accredited Stele or score values.
These rows remain closed rather than treating missing values as zero or false.
The686 opaque-complex rows remain disabled by explicit user instruction.

The rollMax investigation remains a documented missing native lottery consumer,
not an established global cap: the installed full123-JAR search and secondary
consumer scan expose storage/getter/UI uses only. Neither `rollMax=1` nor an
item-table coincidence proves per-team/per-player cap semantics. No safe general
implementation can be derived from those data alone.

## Actual evaluator and production reachability

`storage/combat_drops.py::_condition_matches` recognizes every simple enum/value
combination present in the current direct catalog. **No current direct condition
is rejected because of an unknown enum or malformed value.** The gap is not an
incomplete list of parser cases.

Production `combat_reward_context.build_drop_context` emits only `downscaled`
and, with a trusted origin, `in_dungeon` and `in_infinite_waves`. It never emits
`stasis_level`, `stele_loot_enabled` or `score`. Although the evaluator supports
these three fields syntactically, production cannot currently authorize their
rows. Missing authority fails closed.

| Direct condition population | Rows | Species | Items | Actual limitation |
|---|---:|---:|---:|---|
| MIN_STASIS_LEVEL | 3,069 | 463 | 1,722 | No frozen authoritative Stasis level; 5 rows also opaque-complex |
| CAN_BE_LOOTED_IN_STELE | 634 | 35 | 420 | No frozen authoritative Stele loot context; 97 also require Stasis |
| MIN_SCORE | 268 | 4 | 170 | No authoritative encounter score; 3 also require downscaling |
| Opaque complex flag | 686 | — | — | Expression is not supplied by the exported raw monster model |

The **union of simple rows missing one of the three production authorities is
3,869**. This is disjoint from the 686 opaque-complex rows, so 4,555 direct rows
are unavailable for these two distinct reasons. Do not sum condition counts:
97 Stele/Stasis rows overlap, and the 5 complex/Stasis rows remain complex even
if a Stasis field is later supplied.

Stasis thresholds are 2 (182 rows), 3 (2,861), 4 (16), and 5 (10). Score thresholds
range from 15,000 to 15,000,000. These are catalog populations, not live encounter
frequencies, missing awarded item counts, or probabilities of receiving loot.

Examples preserving source row identity:

- Monster42 row0 → item14126, `MIN_STASIS_LEVEL=2`.
- Monster42 row1 → item26567, `MIN_STASIS_LEVEL=3`.
- Monster2556 row5 → item18382, Stele flag.
- Monster4378 row0 → item24019, score threshold.

## Opaque criteria: inspected raw data, not just a boolean

All 686 flagged rows were joined back to `monster.raw_native.csr[row_index]`.
All have raw native class `aMf` and `csH=true`. Their exported raw keys are
`aAi, cmY, cqA, cqy, cqz, csD, csE, csF, csG, csH, native_class`.
There is **no expression string payload** among these 686 raw objects: 681 have
empty `csG`, and 5 expose only the separate Stasis pair array. For example,
monster1 rows5/6/7 point to items2027/2021/2022 with opaque criteria.

Installed `ble.z(int[])` converts pairs through `blo.DU(id)` into `blc` objects;
`ble.gq(boolean)` carries the opaque-complex marker. The inspected native model
and exporter do not supply the missing expression. Adding a generic expression
parser to the boolean would not recover the rule. This is an explicit data/
contract gap. It requires a richer authoritative source or an accredited join;
item identity or coincident table contents do not establish that join.

## Downscaling: concrete contract mismatch candidate, still unproven

There are **160 rows across 138 species and 27 items** with
`ONLY_WHEN_DOWNSCALED` (native ID7, value−1). Of these, 157 also require
`ONLY_IN_DUNGEON`; the other 3 require `MIN_SCORE`. There are no standalone
ONLY_WHEN_DOWNSCALED rows in the current catalog.

The native `blo` constructor embeds this exact description:

> Ne peut être obtenu que dans un donjon en mode compétitif (modulé / à niveau)

This identifies the intended dungeon competitive/modulated-or-at-level concept.
The production adapter currently supplies `actor.effective_level < real_level`,
which establishes a numerical reduction, not a competitive dungeon mode. That
comparison cannot prove eligibility at the dungeon's own level, or whether a
modulated dungeon is actually competitive. The description itself is not an
executable eligibility consumer: the static search found the `blo.iuR` field in
its declaration/initialization, not an authoritative reward evaluator.

Concrete probes after the freeze releases should use a trusted dungeon run:
monster42 row16 → item29851 requires dungeon plus downscaling. The three
score-bearing rows are monster4378 row67, monster5306 row47, and monster5806
row92, all item29851 with score minima1,000,000/3,000,000/1,000,000 respectively.
Do not label an ordinary world-level reduction as full competitive-dungeon
acceptance. A future correction must pin an authoritative competitive/at-level
contract to the durable encounter and receipt. No gameplay change is justified
solely by the human-readable label.

## Detached external tables: real data, no proved direct-combat link

The same catalog includes **2,204 external tables containing 14,328 rows**:
12,674 leaf item rows and 1,654 nested table rows targeting 822 table IDs, with
no dangling nested target. Of those rows, 2,215 have nonempty `fFe.czk`
expressions and 12,113 have none. All exported `gBO` pair arrays are empty.
`IsNeoServer()` appears in 546 rows; ranch/monster-attribute expressions also
occur. Table621, for example, includes item32725 with `IsNeoServer()` and an
unconditional item2355 row. Table637 contains resource-satisfaction expressions.

**Every one of the 16,138 direct monster rows has `is_loot_table=false`.** There
are zero direct table-reference edges into this external graph. Therefore the
14,328 table rows are not an additional measured combat-drop deficit. The
client `bat` loader proves their separate native data model; it does not prove
that combat settlement uses them. Reusing the dungeon `IsNeoServer` parser
would neither establish that missing link nor support ranch predicates.

## Bounded profile comparison

These counts apply only the current condition/opaque-criteria gates across the
whole catalog. They are **condition-eligible**, not final item validation,
delivery eligibility, or drop probability. They do not validate quantity/
probability bounds, template support or participant ownership. Current native
minimum prospection is zero in all rows, but the metric is still deliberately
limited to condition coverage.

| Production condition profile | Condition-eligible rows | Condition-rejected rows |
|---|---:|---:|
| Origin unknown, not numerically downscaled | 11,060 | 5,078 |
| Ordinary world, not numerically downscaled | 11,371 | 4,767 |
| Ordinary world, numerically downscaled | 11,371 | 4,767 |
| Dungeon, not numerically downscaled | 11,249 | 4,889 |
| Dungeon, numerically downscaled | 11,406 | 4,732 |

Trusted world origin recovers 311 rows from missing geographic classification;
trusted dungeon plus numerical downscaling admits 157 additional dungeon rows.
This does not resolve their competitive-mode semantic question.

## Next implementable work and required evidence

The largest narrow engineering gap is to freeze actual encounter Stasis/Stele/
score authority into settlement context and immutable receipts. Comparators for
Stasis>=X and score>=X are already implemented and the native enum descriptions
accredit those comparisons. What is missing is their value provider and lifecycle,
not another parser. The current local dungeon context uses `difficulty_level=2`
with difficulty changes disabled; a serialized UI value does not, by itself,
prove authoritative Stasis scaling/reward entitlement. Do not silently wire that
constant as a full Stasis implementation. A provider can be implemented after
its native context contract and encounter authority are established.

For complex criteria, no demonstrated narrow server fix exists with this raw
model. For the external tables, no demonstrated direct-combat join exists.
Issue10 remains open for these exact reasons; no speculative cap, expression,
score, Stele or competitive-mode entitlement was introduced.

## Reproduction and corroboration

Private artifacts are `.runtime/drop-criteria-20261011/current-catalog.json`,
`audit.py`, `criteria-audit.json`, `conditions.javap.txt` (under the earlier
`drop-rollmax-20261011` directory), and `condition-consumers.json`.
Run `python3 .runtime/drop-criteria-20261011/audit.py` to reproduce the inventory.
The root independently counted the same catalog SHA in
`.runtime/drop-criteria-20261011/independent-root-counts.json`; this corroborates
populations, not native eligibility semantics. No background process remains.

Independent Luna verification reproduced the audit with exit0 and checked the
3,869/686 disjoint populations,160-row partition, external nested graph and raw
opaque payloads without discrepancies. Evidence is
`.runtime/drop-criteria-20261011/verification-20261011.log`. Root rechecked both
named production-module hashes against that terminal log; they still match.
This verifies the reported coverage limits, not unresolved reward semantics.


## Final bounded Stele/score consumer check

A separate full123-library scan on the installed57,562 classes searched actual
constant-pool references to `blo.iuO` (MIN_SCORE), `blo.iuP`
(CAN_BE_LOOTED_IN_STELE) and the enum decoder. The only external consumer is
`ble`, which decodes the numeric enum and constructs `blc(enum,value)`; it does
not evaluate a fight. Neither constant has an installed evaluator consumer.
The Stele description is a permission label, not proof of an exclusive Stele
requirement, so the conservative existing rejection cannot be claimed as native
parity. No safe replacement predicate is established by this scan.

Evidence: `.runtime/drop-criteria-20261011/stele-score-consumers.json` and
`ble-criteria-model.javap.txt`. The scan exited successfully; no process remains.
The minimal remaining contracts are (1) Stele selection/reward membership and
its ordinary-loot predicate; (2) per-encounter score accumulation/finalization
for the four score-bearing species; (3) rollMax allocation scope and reset.
These cannot be replaced by UI selections, client-supplied scores or guessed
caps. The implemented Stasis/competitive and default ordinary rewards do not
depend on these unestablished contracts.


Score-bearing native species are Ogrest4378 (97 rows), Rushu5306 (72),
Neoogrest5806 (98), and Jalató Real del Amor5608 (1 row, score>=15000).
The first three native references have level230; the last has level30.
Thus267 of268 score-conditioned rows belong to those three high-level bosses,
not ordinary dungeon families. Names are retained in the installed Spanish
monster protocol snapshot; row counts come from the current catalog SHA above.
