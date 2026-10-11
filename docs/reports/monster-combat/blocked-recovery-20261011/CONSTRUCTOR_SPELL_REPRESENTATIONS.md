# Inert owned state representations already listed in native initialization

Offline source audit of the808 blocked definitions. No casting guards, activation rules, ordinary AI behavior or qualification requirements changed.

## Representative2867 Caballero de Astrub

Owned spell4131 Características de Caballero de Astrub has literal native casting criterion `False`. Its only root108802 is family304 applying state2484, itself conditioned by literal `False`. No movement, target, resources or ordinary preparation can make this root or the literal casting criterion true.

Native `content.4.4131` describes it explicitly: “Este estado reagrupa la evolución de las características y la ganancia de dominio que atribuyen los hechizos del compañero.” This is companion wording from the actual native spell description, not a classification inferred from the monster name.

The native actor already lists state2484 in its initial triples `[2484, -1, 1, 2487, -1, 1]`. Spell4120 Protector de Astrub likewise has a false-conditioned family304 root108803 referencing the already-listed state2487, although its casting criterion is empty. Existing historical initialization receipts confirm both states were applied; this audit does not replace complete state-effect qualification.

The actor also owns4117 Estoque,4118 Talla and4119 Líder. Estoque and Talla have empty casting criteria and actual attack roots; Líder requires an occupied target cell. These are separate action candidates. A failure to cast4131 is not evidence that all its actual attacks are broken. Conversely, the inert entries cannot simply be removed from full spell/state coverage obligations.

## Shared exact pattern

**11 definitions** share at least one owned entry with literal castingFalse, literalFalse304 roots and matching native initial-state identity. All11 retain additional owned spells. **Zero** are proven passive-only actors by this pattern.

| Ref | Native name | Constructor representations | Other owned spells |
|---:|---|---|---|
| 2829 | Skalo | 4111, 4125 | 4098, 4099, 4102, 4100, 4101, 4097 |
| 2867 | Caballero de Astrub | 4131, 4120 | 4118, 4119, 4117 |
| 3081 | Pandora | 4328 | 4329, 4330, 4331, 4332 |
| 3084 | Chad | 4341 | 4345, 4344, 4343, 4342 |
| 3108 | Pandora | 4328 | 4329, 4330 |
| 3168 | Pandora | 4328 | 4331, 4329, 4330 |
| 3238 | Chad | 4341 | 4344, 4345, 4342, 4343 |
| 3403 | Pandora | 4328 | 4329, 4330, 4331, 4332 |
| 3404 | Chad | 4341 | 4344, 4345, 4342, 4343 |
| 3405 | Exploranciana | 4328 | 4329, 4330, 4331, 4332 |
| 4453 | Hipoliro | 6175 | 6130, 6133, 6135, 6137, 6138, 6169, 6174 |

## Reusable qualification evidence

`server/tools/audit_monster_constructor_spell_representations.py` follows actual native ownership, requires every positive/zero-level root present in the supplied spell record to be a variant0 family304 with literalFalse, no children, a constant positive state reference and that state already listed in nativecle. Mixed active roots, missing records, nonconstant state references and semantically similar expressions such as `not True` are rejected. CastingFalse is reported separately from false effect roots.

The helper emits structural hints with `constructor_execution_qualified=False` and `level_equivalence_qualified=False`. A future qualification policy would still need actual resolved-level equivalence, complete constructor-effect execution, native negative-cast behavior and ordinary AI action proof. It must not create attacks for an actor whose only owned entries are inert. No such policy or validator bypass was added here.

Five pure focused tests passed. Existing tests were untouched. Receipt: `.runtime/monster-blocker-recovery-20261011/constructor-spell-representations.json`. Reproduce with:

```sh
python3 server/tools/audit_monster_constructor_spell_representations.py \
  --bundle .runtime/monster-combat-extraction-20261010 \
  --scope .runtime/monster-blocker-recovery-20261011/scope.json \
  --output .runtime/monster-constructor-spell-representations.json
```

## Exact initialization qualification lane

A narrow implementation now handles **literalFalse casting plus a sole
literalFalse variant0 family304 root with native selectorfcE mask0**. This is
stricter than the structural audit above: spell4120, whose casting criterion is
empty, remains outside this lane.

`monster_passive_initialization.py` rederives actual native ownership and the
native spell maximum clamp, resolves the selected304 root at the actual spell
level, and uses the existing production `parameter_value` and
`interpret_state_parameters` arithmetic. Its resolved state reference and level
must match the actual native `initial_state_plan` at the descriptor level.
Merely finding the state ID somewhere in nativecle is insufficient.

The validator then constructs a real ordinary fixture and requires the existing
`initialization_proven` checks: exact reference, descriptor level, raw triple
order, resolved levels/flags, successful applications and placement carrier
proof. A SHA-256 binds the complete receipt content. The case status is
**`passive_initialization_only`**, with zero cast attempts, zero successful cast
targets and no AI/effectful-cast claim. Every owned spell stays in the complete
level matrix and native action book.

The finalizer independently reloads native ownership and casting from their
sealed, hashed source files; checks the candidate's native book and initial
triples; rederives the root, criteria, level and receipt proof; and rejects
forged labels, missing receipts or changed source. Each monster still needs at
least one ordinary effectful validated cast and its normal AI delivery proof.
A book containing only inert entries cannot be promoted through this lane.
Default normal cast/commit paths are unchanged.

Source-only checking matched all native descriptor levels for the12 qualifying
entries across11 definitions. A historical real initialization receipt for2867
also satisfies the new exact proof. This is explicitly **not current runtime
qualification or activation**: the receipt came from the prior screening run
and full current books, levels and AI commits remain pending.
Private illustration:
`.runtime/monster-blocker-recovery-20261011/passive-initialization-source-check.json`.

Focused validation: **31 tests passed**, including unchanged original
finalization, finite validation-budget and constructor-proof tests, plus nine
new passive proof/integration cases covering forged/missing receipts,
source changes, mismatched references and levels, mixed roots, changed criteria,
only-passive substitution, retained ownership and zero cast/preview calls.
No original assertions were modified. Independent focused verification also
passed31/31 with stable helper/validator/finalizer source hashes. Receipt:
`.runtime/monster-blocker-recovery-20261011/offline-passive-initialization-final-tests.json`.
Heavy monster matrices remain later.
