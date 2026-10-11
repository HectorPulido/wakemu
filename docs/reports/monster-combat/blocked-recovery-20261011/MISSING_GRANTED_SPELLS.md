# Missing granted spell definitions: actual source records recovered

Offline extraction only. No active catalog, ownership, exclusion or actor
statistics changed. This fixes a source-data gap, not the whole encounter.

Blocked references 5650 Protozortiempo and 5720 Caja vacía shared missing spell
records 8331 Grúa, 8337 Fuego Sagrado and 8338 Escudo de Wakfu. All three already
exist in the installed casting source with maximum level245. A bounded native
export recovered exactly three complete positive-level spell records and six
effects, with all245 casting/cost levels retained from the sealed source. The existing
Java exporter samples effect parameters at levels1–200 and preserves raw native
curves; it does not certify evaluated effect parameters201–245. That inherited
limit remains explicit for subsequent assembly and validation.

## Why the original extraction missed them

The old inventory extraction follows state304/321 and grant649 references, but
its dependency walk omits area315 and summoned-profile307 transitions. The later
full typed summon dependency walk correctly notices the resulting gaps.

Native shortest paths:

- 5650 initial state8699 -> effects390772/390773 -> area315 effects390774,
  390775,390776 -> areas1951,1952,1953 -> effects390759/390762,
  390765/390766,390769/390770 -> states8721,8727,8728 -> grant649
  effects390631,390755,390757 -> spells8331,8337,8338.
- 5720 initial8706 -> effects390357/390358 -> summon307 effect390359 ->
  native profile5650 -> the same paths.

Family649 reads logical evaluated parameter index2 as the granted spell ID;
other values in its parameter row are not spell references. The raw curve pairs
are preserved, not reinterpreted as evaluated values.

Native descriptions `content.4.8331`, `.8337` and `.8338` say using the spell
removes it from the spell list. Each actual spell graph includes family321
removing its corresponding granting state (8721/8727/8728). This supports a
single-use, dynamically granted action interpretation. It does not establish
all encounter activation or grant eligibility semantics by itself.

## General bounded source repair

`server/tools/plan_monster_spell_supplement.py` uses the existing complete typed
dependency closure to find missing spells behind states, areas and summoned
profiles. It distinguishes records present in installed casting from genuinely
absent definitions, caps export size to16, and exports only when explicitly
passed `--extract`. It writes a new private supplement and never adds these
spells to monster ownership. Source bundles, zero-level evidence and existing
catalogs remain untouched. The supplement itself needs normal append-only
catalog assembly and full semantic validation before future use.

Five pure regression tests passed: exact649 slot, area/state path, nested
summons, cycles, absent definitions, unrelated values and bounds. Existing tests
were not changed. Private artifacts:

- `.runtime/monster-blocker-recovery-20261011/missing-granted-spells/closure-paths.json`
- `.runtime/monster-blocker-recovery-20261011/missing-granted-spell-supplement/plan.json`
- `.runtime/monster-blocker-recovery-20261011/missing-granted-spell-supplement/supplement.json`
- `.runtime/monster-blocker-recovery-20261011/missing-granted-spell-supplement/source-receipt.json`

The source receipt validates three245-level definitions,245 cost rows each,
actual effect roots, namespace-qualified native text and SHA-256 provenance.
No runtime combat replay is claimed.

## Verified offline assembly integration

The final reproducible package is
`.runtime/monster-blocker-recovery-20261011/missing-granted-spell-supplement-verified-final/`.
Its receipt is produced by the planner itself, rather than a manual postprocessing
step. It pins the current client JAR, native binary archives, eight sealed
bundle components, original provenance, Java exporter and converter source,
all generated source artifacts, exact245 spell/cost rows and actual per-effect
parameter sample domains. Inputs are checked before and after export. SHA-256
reads are streamed. The Java exporter is compiled from the recorded current
source into the private output directory.

Reproduce in a fresh private output directory:

```sh
python3 server/tools/plan_monster_spell_supplement.py \
  --bundle .runtime/monster-combat-extraction-20261010 \
  --reference 5650 --reference 5720 \
  --output .runtime/monster-granted-spell-reproduction --extract
```

Read-only receipt validation:

```sh
python3 server/tools/monster_spell_supplement.py \
  --bundle .runtime/monster-combat-extraction-20261010 \
  --supplement .runtime/monster-blocker-recovery-20261011/missing-granted-spell-supplement-verified-final
```

`prepare_monster_spell_activation.py` now accepts an explicit optional
`--spell-supplement DIRECTORY` and forwards it to
`export_monster_summon_dependencies.build_documents`. The default path is
unchanged. Explicit use verifies the source receipt, appends missing typed
records, rejects conflicting existing records and then runs the existing
zero-level dependency logic. It neither rewrites the sealed extraction nor
adds granted spells to any monster's owned action book. Closure reports retain
receipt/document hashes and the unqualified-above-200 limitation.

A read-only offline planning pass with that verified package completed for both
5650 and5720: **both typed closures now have no missing definitions**.
Receipt: `.runtime/monster-blocker-recovery-20261011/missing-granted-spell-closure-verified/plan.json`.
This removes their source-definition gap; it does not certify spell execution,
AI behavior, level201–245 effect parameter evaluation or encounter readiness.

Ten pure focused tests now pass across planner and assembly modules, including
unchanged zero-level roots/references, append-only behavior, conflict rejection,
root/range/cost domain mismatch and changed source/artifact receipt rejection.
Independent local testing also passed all10 within a32-test focused gate;
relevant source hashes stayed stable. Receipt:
`.runtime/monster-blocker-recovery-20261011/offline-spell-supplement-area-uid-tests.json`.
