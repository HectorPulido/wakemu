# Native surface constructor performance

## Scope and evidence

Fight 117's entry stage `arena_selected` reportedly consumed 22.351 seconds wall time and 22.225 seconds thread CPU on map 1134. The overlapping external profile identified native surface construction as a hot path. This change only reduces constructor allocations; it does not change arena selection, placement, movement, spell evaluation, or topology policy.

The published map 1134 surface document contains 196,020 columns and 198,945 surface entries, but only 212 distinct `(z, bld)` values. Previously every entry allocated a frozen dataclass instance and a generator for two integer type checks.

## Change

- Replace the two-element generator with two exact integer type checks. Booleans and floats remain rejected.
- Use a slotted frozen dataclass.
- Intern immutable surface values within one provider construction. Every input entry is still validated before lookup. No global cache is added, and raw input lists are not retained.
- Preserve chunk order, column order, surface order, duplicate altitudes, signed bounds, provenance checks, and first matching chunk behavior.

Consumers use surface value fields, not instance identity. Equal immutable values may now share an instance inside a provider.

## Validation

`PYTHONPATH=server python3 -m unittest discover -s server/tests -p 'test_combat_qi_surface*.py'`

Result: 15 passed. Added regression coverage for repeated values, immutability, raw input mutation isolation, invalid bool/float values after an equal valid value, and signed boundaries.

An isolated benchmark ran inside the existing world container, using the same published map 1134 document and reconstructing the previous constructor in memory:

| Constructor | Run 1 CPU seconds | Run 2 CPU seconds |
| --- | ---: | ---: |
| Previous | 0.4412 | 0.4357 |
| Updated | 0.2060 | 0.2125 |

This is approximately a 52% reduction in isolated constructor CPU time. It does **not** explain the entire live 22-second stage. The live-versus-isolated discrepancy remains open; deployment must not be described as resolving all entry stalls.

Differential hashes cover every chunk bound and every column and ordered surface value:

| Map | Surface entries | Identical SHA256, previous and updated |
| --- | ---: | --- |
| 1134 | 198,945 | `94983cfb1b7686665b8a9f375dcd1be15185b03a5e706ba257372bae013c7f36` |
| 527 | 174,052 | `9898ca61aa8b563d652c0b4ba27c0b8cd5068db4a88baae2e0107586d80c7e4f` |

Private raw data, benchmark harnesses, and JSON results are under `.runtime/local/diagnostics/fight117-entry/`. No restart was performed by this investigation.
