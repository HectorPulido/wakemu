# Rol duende zero-range casting contract

References2199,2203 and2227 share the remaining failure in native spells3117 and3141. This is independent of missing state resistance metadata. Their other owned spells, including3137 and3144, already passed the second candidate's preview validation.

The extracted native casting metadata specifies minimum0, maximum0, no range modifier, no category-based range modifier and no casting criterion for3117/3141. Spell3117 has three roots with selector mask257: area selection plus exclusion of the caster. Spell3141's roots use mask8 (enemy) and mask140737488355584 (native fighter restriction plus exclusion of the caster). Consequently an explicit cast at the caster's cell is rejected with `twE`; a different XY cell is rejected with `twI`. Applying additional states through owned spells cannot change those unconditional range and selector contracts.

The original bytecode confirms the exclusion. `fcE.a` returns `amT.INVALID` for bit256 and the caster. `fcj.a` accepts only `VALID`, `VALID_IF_IN_AOE` and `SUBTARGET_VALID_ONLY` in its final root-selector gate; it rejects `INVALID`. The current behavior therefore does not demonstrate a Python selector defect.

There is a distinct nullable target-cell path in the native casting query. `fcO.a(eGj,fyG,aBn,boolean)` branches at347 to492 when the cell is null, then invokes `fcj.a` at557. However, the discovered actual null-cell callers perform spell availability checks: `dbl.b` calls `bPe.a` with null at560 and then opens `dbk` targeting mode; `bOS` and `bPO` likewise query menu/action eligibility. These callers do not prove that an actual NPC spell execution may discard its target cell. A generic null-cell bypass would omit native range, collision and target-selection gates for other spells and must not be introduced without an actual execution producer contract.

Evidence is retained under `.runtime/monster-remaining-20261010/`: `fcE-target-selector.txt`, `fck-target-selector.txt`, `fcO-spell-casting.txt`, `fbX-casting-wrapper.txt`, `fbX-spell-callers.txt`, `dbk-spell-targeting.txt`, and `probe-second.json`.

No production code, casting definitions or existing tests were changed for this investigation. The next useful evidence is an original NPC execution/action contract for self-centered area casts, or a captured native combat showing3117/3141 execution. Reclassifying the spells or replacing their metadata without that evidence would conceal the unresolved producer.
