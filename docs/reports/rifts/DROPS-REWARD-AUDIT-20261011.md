# Combat drops and rift reward audit — 2026-10-11

## Current runtime evidence

A read-only check inside the running `world` validated the actual configured
`rift_reward_policy` using its deployed policy and native-item validators.
Validation passed for equipment (3 references), shards (1), sublimations (4),
and costumes (3). The configured rift survival budget is 40 complete timeline
rounds. Root's runtime query found no rift settlement or item reward receipts;
there is no completed settlement available to establish a missing payout.

A cleared wave does not settle the run. The current explicit local policy pays
only survivors when the 40-round budget finishes. Surrender, defeat and capacity
closure do not pay. At least one cleared wave is required. A successful run with
one cleared wave guarantees 2–5 physical shards per eligible member; equipment
starts at two waves, sublimations at four, costumes at five. XP and kamas remain
zero by explicit dispatcher policy. These are local experiment rules, not
recovered official rift formulas.

No client files were changed. No deployment, restart, runtime setting write or
runtime reward grant was performed by this audit.

## Combat drop findings

The installed native catalog has 2,874 species and 16,138 combat-drop rows.
There are no external-table rows in this catalog. There are 686 rows with complex
criteria, 1,343 with positive native `rollMax`, and these condition occurrences:

| Condition | Occurrences |
|---|---:|
| NOT_IN_DUNGEON | 177 |
| ONLY_IN_DUNGEON | 212 |
| NOT_IN_INFINITE_WAVES | 134 |
| MIN_STASIS_LEVEL | 3,069 |
| CAN_BE_LOOTED_IN_STELE | 634 |
| MIN_SCORE | 268 |
| ONLY_WHEN_DOWNSCALED | 160 |

The ordinary shared dispatcher did not supply an authoritative encounter kind.
That omitted context denied both dungeon-only and non-dungeon-only rows. The
context adapter now accepts explicit ordinary-world, dungeon and rift origins.
The caller must freeze the origin from its trusted encounter creation route;
map IDs and combat terrain do not prove encounter type. The shared dispatcher now resolves this origin through durable dungeon fight bindings or the trusted public-instance group key. Unknown private contexts remain unknown; no map-based inference is used. Stasis, Stele and score still require authoritative subsystem input.
Complex criteria remain denied. Native `rollMax` remains recorded but is not
interpreted as an invented per-fight or per-player cap; its semantics require
native evidence before a general correction.

## Optional native item selector

`rift_reward_policy.pools[*].source = "native_rift_monsters"` is an opt-in source
for an ordinary item pool. The existing default pools and rates are unchanged.
The source resolves simple eligible native loot from the frozen rift species,
then freezes a sorted physical-item allowlist before draws. It excludes external
tables, complex criteria, prospecting gates, unproven contextual eligibility,
mounts, cosmetic learning items, unsupported templates and unsupported binding.
It fails before inventory mutation if no supported item is eligible.

The configured pool chance, wave interval and quantity remain local balance;
the selector does not convert native monster probabilities into official rift
probabilities. Existing atomic award receipts, owned recipients, overflow and
replay apply unchanged.

## Verification completed — 2026-10-11

`test_rift_rewards` includes an integrated default-policy test that advances a
real `Fight` through 40 complete rounds, verifies survival, settles the canonical
run, and verifies guaranteed shard ownership, report loot and all three native
inventory update packets. It also tests native selector filtering, empty-pool
rejection, frozen allowlists and repeated award without duplicate ownership.
`test_combat_reward_context` covers all three explicit encounter origins and
rejects unknown origins. Luna executed `test_rift_rewards` and `test_combat_reward_context` against isolated PostgreSQL with the current native catalog: **25 tests passed in12.660s**, including `test_default_survival_endpoint_delivers_loot_after_forty_complete_rounds`. Log: `.runtime/local/verification-20261011-rift-drops.log`. This proves the default survival settlement/delivery path in the automated environment; it does not establish a completed live-client payout.

## Manual acceptance

Enter a classic rift with the complete intended party and heroes. Clear at least
one wave, then finish all 40 timeline rounds while surviving. Every eligible
member must receive its own result loot and at least 2–5 shards for each cleared
wave (up to the configured roll limit). Members with full bags must retain the
same items in temporary loot after reconnecting; claiming must transfer them
once. A surrender before the survival budget must show no rewards under the
current policy. XP and kamas must remain zero until a separate explicit policy
is implemented. Definitive-rift key consumption remains outside this correction.

## Native rollMax follow-up — 2026-10-11

A complete static constant-pool reference scan covered **123 installed library
JARs and 57,562 class files**, including every subclass/implementation in the
`fpu`/`fqG`/`fqH` family and the raw `aMf`/`fFe` definitions. The installed client
JAR SHA-256 is `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`.
The scan and focused disassembly confirm these consumers:

| Consumer | Proven operation |
|---|---|
| `bbo.a(aMb, short)` | Reads raw monster `aMf.csE(): short`, narrows to byte, writes `fqH.gF(byte)` |
| `bat` loader | Reads separate raw loot-table `fFe.csE(): short`, narrows to byte, writes the same builder |
| `fqH.gF` / `gkX` | Stores and returns the builder byte |
| `fqG` constructor / `csE` | Copies the builder byte into the model and returns it widened to short |
| `fqG.toString`, `fqH.toString`, `bld.toString` | Represent the value under the original name `m_rollMax` |
| `fpx.csE` | Alternative loot model returns constant zero |

There is no static reference to a rollMax getter from an installed lottery,
shared-loot allocator or reward settlement consumer. This is a bounded statement
about the installed libraries, not proof of the absent official server's behavior
or of arbitrary reflection paths.

Current native catalog SHA-256:
`db31e2b205370fc73771573d33f374085ab1a27d222ef0601199eedf90792d36`.
Of 16,138 rows, 14,795 store `rollMax=-1` and 1,343 store `rollMax=1`.
The latter span 466 species and 652 items: **1,214 have `roll_count=-1` and
129 have `roll_count=1`; none has `roll_count>1`**. Every native minimum
prospecting value is zero. Consequently no current positive-limit native row
proves a difference between a per-row single-attempt cap and the existing local
single-attempt planner. The unknown difference concerns sharing across owners,
monsters or duplicated source rows, together with the reset boundary.

For Kralaman2709, shard item27083 has four separate rows (indices3–6), each with
`roll_count=-1`, `rollMax=1`, probability0.05 and quantity3. Every one requires
`MIN_STASIS_LEVEL=3`; an ordinary world test cannot authorize these rows merely
to investigate rollMax. The installed UI grouping does not authorize merging them.

**No gameplay correction is justified by the available consumers.** The server
continues preserving `native_roll_max` in immutable receipts without inventing
a global cap, deduplicating native rows or altering combat/spells. A definitive
contract still needs an authoritative server consumer or official-server evidence
that discriminates two owners, two monsters, repeated rows and separate fights.

Reproducible local evidence:
`.runtime/drop-rollmax-20261011/scan.py`, `consumer-scan.json`,
`native-classes.javap.txt`, and `other-consumers.javap.txt`.
The compact scan result is retained in
[the consumer audit](../drop-rollmax-consumer-audit-20261011.json).
Existing local planner regressions describe the chosen policy, not official
semantic equivalence. No server/client source, services or runtime settings were
changed during this follow-up.

## Independent rollMax reproduction

Luna independently reran `.runtime/drop-rollmax-20261011/scan.py`: exit0,123 JARs and57,562 class entries. The family set, eight references, marker strings and installed client JAR SHA match the checked-in compact evidence structurally. Focused bytecode review confirms builder/storage/getter propagation of the signed byte, not a lottery contract. Evidence: `.runtime/drop-rollmax-20261011/independent-run-20261011.log`. This independently validates the audit scope without establishing a per-recipient, per-enemy or shared cap.


## Production allocation boundary and repeated rows

The current planner's allocation unit is recipient × defeated actor × original
source row × `roll_count` attempt. Positive `roll_count` supplies that many
attempts; nonpositive values use one. `native_csE` is validated and persisted
in each decision/receipt, but does not merge recipients, monster actors or rows.
The same native reference appearing twice in a fight remains two defeated actors.
All1343 positive `csE` rows currently store1;1214 have `roll_count=-1`,129
have `roll_count=1`, and none creates multiple attempts from `roll_count` alone.
There are28 repeated species/item groups with positive `csE`, so deduplicating
by item would alter real source rows without an accredited allocator contract.
Examples include monster2570/item31591 rows4–6 and monster2582/item27083
rows2,15–17. Machine-readable inventory:
`.runtime/drop-rollmax-20261011/production-distribution.json`.

Loader/copy/getter evidence establishes a native data field, not its allocation
scope. The safe remaining discriminator is sharing between two eligible owners,
two defeated actors of one reference, duplicate rows and a subsequent fight.
The currently implemented per-recipient decisions/receipts are explicit local
policy, with no claim that an absent native global allocator was reconstructed.

The final bounded roll-count check also distinguishes the fields mechanically:
raw `csD` (byte) → builder `gE` → `sTE` → model `giM`; raw `csE` (short)
→ narrowed-byte builder `gF` → `sTF` → model `csE`. The all-library reference
check finds `giM` consumed by the `fpx` copy constructor, while `gE` is written
by `bbo`, `bat` and `brq`. No discovered sampler or serializer establishes a
team/owner allocation scope. Evidence is `rollcount-consumers.json` and
`rollcount-wrapper.javap.txt` under the private rollMax audit directory.
This does not justify replacing `roll_count` with `rollMax` or merging rows.
