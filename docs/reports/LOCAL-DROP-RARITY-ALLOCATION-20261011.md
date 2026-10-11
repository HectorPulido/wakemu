# Local rarity drop allocation — 2026-10-11

This is an explicitly authorized **local policy**, not a reconstruction of native `rollMax`. Native `native_csE` / `DropDecision.native_roll_max` remains unchanged. Allocation filters already successful planned decisions and never generates a random number, changes an accepted quantity, or enables opaque criteria. The 686 opaque rows remain disabled by the existing planner.

`drop_allocation.allocate(db, fight_id, character_id, decisions)` returns `(filtered_decisions, snapshot)`. Call it after the existing award replay check and drop planner, before award/attempt inserts, inside the same transaction as the victory award. Add its snapshot to the existing award snapshot. Any later award failure must roll back allocation too. The durable fight row serializes concurrent recipients. Existing allocation receipts return their stored decisions without inspecting a new plan, new policy or current rarity mappings.

Migration137 installs `settings.combat_drop_allocation_policy` with policy name `wakemu-local-rarity-allocation-v1`, `enabled=true` and default scope `recipient_item`. The cap is the number of **successful bundles of the same item** across all defeated actors/source rows for one recipient in one fight. An accepted bundle retains its native quantity, including quantities greater than one. Configurable scope `fight_item` shares each item cap across all recipients in a fight. Allocation uses existing plan order; fight scope prioritizes recipients in transaction lock acquisition order. This is an explicit local ordering rule, not a claim of native lottery fairness.

| Native rarity code | Name in existing inventory/pricing evidence | Default successful bundles |
| --- | --- | --- |
| 0 | UNUSUAL | Unlimited |
| 1 | COMMON | Unlimited |
| 2 | RARE | 6 |
| 3 | MYTHIC | 3 |
| 4 | LEGENDARY | 2 |
| 5 | RELIC | 1 |
| 6 | PVP_SOUVENIR | 1 |
| 7 | EPIC | 1 |
| 10 | ADMIN | 0 |

Operators may edit `enabled`, `scope` and `rarity_caps` in the setting. A JSON `null` cap means unlimited; zero rejects every successful bundle of that rarity. Policy is pinned on the first allocation for each fight, so a policy edit affects only fights without a pinned allocation policy. Receipt and policy tables reject update/delete. The optional migration-absent path returns the input unchanged with a disabled snapshot; migration137 activates the policy. An explicit disabled policy is pinned and receipted as well.

The authoritative item-to-code mapping is the accredited native `aLO.cpL` export in `docs/reports/item-shop-inventory-20261011/native-types.json`, SHA256 `ab3fb867f0aa62dfac8502948566078035fb648286f310ac8e2feceacbc4176a`, with20,230 exported references (20,229 positive references seeded; native reference0 is excluded). Migration124 independently establishes EPIC=7 and RELIC=5. Caps are local values; no numeric rarity ordering is inferred. Snapshot records actual rarity code, cap, prior count, accept/reject decision and source hash. Each successful candidate also retains its original planned success, quantity and quantity draw, including bundles rejected by allocation; final attempt fields may clear quantity while the allocation audit preserves the original random outcome. Unknown successful item references fail transactionally rather than receive a guessed rarity.

Coverage check against private monster catalog SHA256 `4c1a90bbe1092a535f0a89d6fbc52d67fa6da7e1403da7738b103b4c6d005c9a`: all16,138 direct monster rows /6,278 distinct dropped item references have a native rarity mapping; zero missing. A subsequent read-only invocation of actual `native_drop_catalog()` against published release `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`, monster document SHA256 `db31e2b205370fc73771573d33f374085ab1a27d222ef0601199eedf90792d36`, confirms the same16,138 rows /6,278 distinct references with zero missing mappings. Unique drop references by native rarity:0=60,1=337,2=1,400,3=2,617,4=1,681,5=77,6=4,7=102,10=0. Evidence: `.runtime/local/drop-rarity-live-coverage-20261011.json`. The probe used a read-only database session and bypassed Redis caching.

Dedicated validation covers quantity/draw preservation, cross-source caps, unlimited common rarities, independent item counters, invalid policies, unknown references, durable replay, atomic rollback and policy pinning across recipients. A deterministic two-connection regression additionally proves the second recipient waits on the actual PostgreSQL fight lock, then observes the committed shared cap; aggregate receipts accept exactly one bundle. Independent Luna PostgreSQL validation passed in the integrated61-case gate recorded below. Publication and graphical acceptance remain pending. No client changes or service operations were performed by this worker.

## Operator configuration and complete acceptance

Run these statements in the existing World PostgreSQL database. They edit only
future unpinned allocation policies; do not delete or rewrite fight receipts.

```sql
-- Inspect the current explicit local policy.
SELECT value FROM settings WHERE name='combat_drop_allocation_policy';
-- Share each item cap across all recipients of a fight.
UPDATE settings SET value=jsonb_set(value,'{scope}','"fight_item"'::jsonb)
WHERE name='combat_drop_allocation_policy';
-- Restore independent caps for every recipient.
UPDATE settings SET value=jsonb_set(value,'{scope}','"recipient_item"'::jsonb)
WHERE name='combat_drop_allocation_policy';
-- Example: allow at most six successful rare bundles of each item.
UPDATE settings SET value=jsonb_set(value,'{rarity_caps,2}','6'::jsonb)
WHERE name='combat_drop_allocation_policy';
-- Disable local allocation; native planning and criteria remain active.
UPDATE settings SET value=jsonb_set(value,'{enabled}','false'::jsonb)
WHERE name='combat_drop_allocation_policy';
-- Enable the configured local caps again.
UPDATE settings SET value=jsonb_set(value,'{enabled}','true'::jsonb)
WHERE name='combat_drop_allocation_policy';
-- Inspect configured boss windows, including the three-round Love profile.
SELECT value FROM settings WHERE name='boss_score_policy';
```

After the complete current World image is deployed and automated gates pass,
execute the existing [complete systems journey](SYSTEMS-ACCEPTANCE-20261011.md):
enter the native Jalató dungeon via its entrance, select Stasis and competitive
mode, fight with owned heroes, finish, verify inventory and return health; then
complete the classic40-round rift and verify50× its recorded ordinary baseline.
Use native Stele selection at a qualified dungeon entrance before its boss fight;
only the selected native item allowlist may authorize Stele drops. Do not expect
unselected items or guaranteed grants. Repeat with allocation disabled to verify
ordinary native planner behavior and unchanged accepted bundle quantities.

After migration140 and the complete current image deploy, use an authorized
console character in instance0 and run `!monster 5608 30 1`. Attack the adjacent
Jalató Real del Amor and deal at least15,000validated boss damage within its
three complete local challenge rounds. Armor absorption contributes; damage to
adds does not. The fight finishes after the third complete round; a legitimate earlier boss
kill also qualifies under the frozen Love-only default early-defeat flag.
An alive boss plus forced victory does not qualify early. The native
row authorizes item13717 (Traje de Cubeedo), quantity1, at native probability1,
subject to normal loot eligibility and configured rarity allocation. Reconnect
and verify no duplicate reward. Do not use `!winfight`, which skips the rounds.
This is a local standalone boss window, not reproduction of the original
Shoot'Aime waves, transformations or boss arrival at round19.

Published monster execution inventory currently enables5608 but explicitly
leaves Ogrest4378, Rushu5306 and Neoogrest5806 pending native initialization and
execution. Their score profiles are implemented, but do not prescribe spawning
or bypassing those species until the Monster owner qualifies their combat.
Their blockers are recorded in
[ALL_MONSTERS.csv](monster-combat/inventory-bulk-1297-20261011/ALL_MONSTERS.csv).

The coordinator can inspect receipts without guessing a fight identifier:

```sql
SELECT fight_id, snapshot FROM boss_score_encounters ORDER BY fight_id DESC LIMIT 5;
SELECT fight_id, score, snapshot FROM boss_score_terminal_receipts ORDER BY fight_id DESC LIMIT 5;
SELECT fight_id, character_id, snapshot->'policy' AS policy,
       snapshot->'accepted_counts' AS accepted_counts
FROM fight_drop_allocations ORDER BY fight_id DESC,character_id LIMIT 12;
SELECT fight_id,character_id,snapshot->'fight_context' AS authoritative_context,
       snapshot->'allocation'->'accepted_counts' AS accepted_counts
FROM fight_drop_awards ORDER BY fight_id DESC,character_id LIMIT 12;
```

Reconnect after settlement and confirm the same inventory and receipts. A replay
must neither draw RNG nor create another award. The686 opaque criteria remain
disabled throughout every policy configuration above.

Final integrated Luna validation:61/61PASS against migrations1–137, including
all8allocation tests and the deterministic PostgreSQL concurrency case; source
hashes unchanged. Evidence `.runtime/local/verification-drops-137-20261011/tests.log`.
The rarity seed excludes reference0, retaining20,229positive native mappings;
all6,278published combat drop references remain covered. No deployment was
performed by this worker.
