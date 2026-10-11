# Native HasFreeSurroundingCell

Representative: Berserkermana, reference 4214, owned spell 7450; Soldadermana reference 4304 uses the same spell. The initial screening also finds the missing predicate on references 2780/2790 (spell 4025) and 1895/1827 (spell 2775). These are affected definitions, not recovered counts.

Native token 193 constructs eMp. Its constructor accepts zero, one, or two booleans. Defaults are false for the first argument and true for the second. The second boolean selects target (true) or caster (false) through eII.b. The original caster must be eGj; the fight context must expose the actual QI. The predicate checks only four cardinal neighbors of the selected actor. Each candidate first requires QI.V to be null; it then uses QI.R when the first argument is true, otherwise QI.Q. Java integer coordinate overflow is preserved. Diagonal cells, area movement-blocking heuristics, HP, and movement costs are not part of this predicate.

Bytecode is retained in `.runtime/monster-blocker-recovery-20261011/native-eMp-free-surrounding.txt`; parser dispatch is in `.runtime/local/native-condition-parser.txt`. Existing `current_registry`, its preserved ordered QK slots, and snapshot Q/R supply the required geometry. Cell arguments resolve through the existing first-QI-actor convention. Unknown fighter-kind authority and a selected area without the native actor-position contract remain explicit errors.

A small pure helper implements the cardinal checks. The condition evaluator validates literal booleans across all branches and requires an authoritative callback. The runtime adapter supplies the actual registry and selected native actor. No spell-specific overrides or mutation of the arena are introduced.

Eight focused new tests cover every cardinal direction, diagonal/origin rejection, obstacle-first evaluation, occupancy, signed overflow, actual Q versus R mask behavior, defaults, and unknown/malformed input. Original tests are untouched. Focused log: `.runtime/monster-blocker-recovery-20261011/free-surrounding-focused-tests.log`.

Representative native replay log: `.runtime/monster-blocker-recovery-20261011/free-surrounding-replay.log`. Complete owned spellbook and level validation is reserved for final verification. No services or catalog revisions were modified.
