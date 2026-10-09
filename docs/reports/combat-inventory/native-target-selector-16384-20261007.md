# Native target selector flag 16384

The installed `fcE` predicate uses target argument `aload_1` for this flag. In `.runtime/combat-review-20261007/fcE-current.javap`, offsets 620–659 test bit 16384, require the target to be an `eGj`, call `eGj.baG()`, and return invalid when that value is false. A true `baG()` continues to the remaining selector predicates. The check is independent of the nearby bit 4096 branch, which reads `dTE()`, `dpu()`, `baG()` and `baK()` for its own target condition.

`ProbeNativeTargetLifeSelectors.java` now exercises bit 16384 against the actual client predicate with otherwise identical targets whose `baG()` values are false and true. It also compares both values with the flag absent and verifies that a non-`eGj` implementation of `amP` is rejected. The offline probe passes:

```text
fcE16384 baG=false mask=0 -> VALID
fcE16384 baG=false mask=16384 -> INVALID
fcE16384 baG=true mask=0 -> VALID
fcE16384 baG=true mask=16384 -> VALID
fcE16384 non-eGj baseline=VALID
fcE16384 non-eGj -> INVALID
PASS fcE16 positive identity; fcE40 baF; fcE16384 target eGj.baG; fdy sax only
```

The existing ordinary target authority already carries an explicit `baG` fact. A future runtime change should add 16384 as a target-lifecycle predicate requiring `baG is True`, while keeping `baF` (in-play) and `baK` (out-of-play) independent. Missing `baG` must remain unknown and reject rather than infer a value from HP, actor identity, or `baF`.

Pending regression coverage before runtime integration:

- A target with `baG=True` passes bit 16384; `baG=False` and missing `baG` do not.
- An object without `eGj` authority passes the unflagged baseline, then fails bit 16384 even though its `amP.bEe()` eligibility method returns true.
- Combining 16384 with another selector requires both predicates and preserves their independent target fields.
- The resolver rejects before dispatch when the selected actor snapshot lacks `baG`, and does not substitute the caster or a registered area for the target.

Only the Java probe and proof documents changed during the audit window. No Python source, tests, runtime service or protocol catalog was modified for this investigation.
