# Reviewed open arenas — 2026-10-10

Offline preparation only. All 15 non-ultimate open-geometry definitions were examined. Two retain exactly one reviewed encounter with every monster identity resolved: Torre Mineral (native:133) and Guarida de Kali (native:121). Both retain three explicitly counted adds (one each) and the explicitly identified boss. Only the unknown boss quantity is filled by explicit local singleton policy. No stages are collapsed, no unknown add counts invented and no native pool expanded.

Both pass directed native arrival, six-player combat formation, encounter engagement and literal free exterior-exit validation. Boss spells, phases, timers and balance remain unverified.

Kali contains two native exterior transport objects, 27522 and 27523, both with the same unconditional destination 2628, map 1122, position (0,-70,0). This is an alias pair, not an ambiguous destination. Preparation retains both complete contracts under equivalent_native_exit_aliases and deterministically pins object 27522 for the completion witness. No existing native transport destination is changed.

| Arena | Result |
|---|---|
| Castillo del Wey Wabbit | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Cire Momore | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Fosa del Atormentador | Requires exactly one reviewed boss identity |
| Relojeros | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Arena Danzante | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| La Torre Mineral | Prepared; complete four-enemy reviewed encounter, entry, six-player formation and exterior exit proved |
| La Torre Mineral | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Torre Mineral | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Neocastillo del Wey Wabbit | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Guarida de Kali | Prepared; complete four-enemy reviewed encounter, entry, six-player formation and exterior exit proved |
| Rushu | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Santuario de Mihmol | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Teatro Intemporal | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Toross | Requires exactly one reviewed guide encounter; no inferred encounter collapse |
| Torre de las Miss Adefesio | Requires exactly one reviewed guide encounter; no inferred encounter collapse |

The other 13 definitions require real initial encounter evidence. Fosa del Atormentador has a one-room guide but no initial roster; a native species pool cannot distinguish initial enemies from summons. The remaining definitions lack a reviewed one-encounter guide. Do not infer stages from floor geometry or reuse rosters from similarly named higher-level/neo arenas.

Verification: `PYTHONPATH=server:server/tools .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p test_reviewed_open_arenas.py` — five tests passed.
