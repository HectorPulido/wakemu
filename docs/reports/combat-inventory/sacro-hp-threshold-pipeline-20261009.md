# Sacrier HP and threshold pipeline regression — 2026-10-09

Scope: SAC-07, local/offline, current authoritative PostgreSQL native catalog. No server restart or deployment. This supplements the class catalog audit with actual spell previews, not manually installed passive or granted-spell carriers.

## Implemented regression coverage

`server/tests/test_sacrier_threshold_pipeline.py` initializes real breed11, level200, native map1134 QI geometry, owned player snapshot, current native innates and validated player decks. HP boundary setup uses the actual raw/effective HP setter; changing `actor.hp` alone would violate the runtime HP authority. The player begins full so the once-only below50% marker is not inherited from the fixture's originally injured actor. Spells cast using actual owned UIDs; Corazón Sanguíneo6065 is obtained through the native innate grant book. Every cast asserts the original fight snapshot remains unchanged.

| Scenario | Verified native behavior |
|---|---|
| Blood5028 ends at20%-1 /20% /20%+1, with/without Refusal5052 | Only the below20% crossing with the passive installs3633 and armor. Equal ending20% does not. |
| Blood5028 starts already below20% with5052 | No false crossing, no3633, no Refusal armor. |
| Refusal activation followed by real granted6065 | The live healing runner changes through353211→353212→353213→353214; native constant1 ends at20%+1. Stored4840 is consumed. |
| Native turn-start at50%-1 /50% /50%+1 | Below50% marker9315 is strict: equal50% does not install it. |
| Punishment5032 at20/50/100% HP with no passive /5052 /7216 | Real HP-scaled damage, stored4840 levels, self-loss HP floor, and Refusal crossing armor all complete atomically. |
| Repeated Blood after Refusal activation | Self-loss reduces HP while preserving existing armor;3633 remains one carrier. |

At level200 this fixture has maximum HP2850. Blood5028 subtracts142 HP (`floor(maxHP*.05)`). Refusal adds570 armor through353208→353209. A569HP Sacrier healing through6065 ends at571HP, because353213 contains constant1; treating that result as an off-by-one bug would contradict the current native definition.

Punishment current results are:

| Starting HP | Ending HP | Enemy damage | Stored4840 level |
|---:|---:|---:|---:|
|570|1|413|100|
|1425|571|347|80|
|2850|1996|205|30|

These results are asserted with all three passive configurations. Refusal5052 adds570 armor only to the20% start crossing. Burning Armor7216 does not alter these particular nonzero HP results. Punishment's native float32 percentage path subtracts854 from a full2850HP actor; Python decimal arithmetic suggesting855 is not an oracle for that path.

## Verification

```
PYTHONPATH=server:server/tests \
WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' \
WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password" \
/tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_sacrier_threshold_pipeline -v
```

Result: **6 tests passed**,149.272seconds. Raw local log: `/tmp/sacro-threshold-tests.log`. `git diff --check` passed for the added test and SAC-01 state absence changes. No additional gameplay fix was justified by these results; this closes concrete missing pipeline coverage rather than inventing class-specific special cases.

## Limits

This focused matrix does not certify every passive, incoming NPC/PvP hit with armor-only absorption, all maximum-HP overflow branches, all end-turn/expiration combinations, or manual client presentation. The separate Columnata/armor and Sacrifice suites cover their own paths. The complete class status must retain those distinctions and must not be promoted to manually validated3/18 from this automated result alone.
