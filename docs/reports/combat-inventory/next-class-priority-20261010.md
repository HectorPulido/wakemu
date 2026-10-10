# Next class implementation priority — 2026-10-10

Current user-provisional acceptance: **6/18** — Cra, Iop, Sacrier, Eniripsa, Osamodas and Ouginak. Provisional acceptance does not certify all manual scenarios or close shared combat incidents.

This ranking estimates remaining implementation and verification effort from the [complete structural inventory](remaining-classes-20261010/README.md) and existing bounded runtime evidence. The approximate percentages below estimate reusable implementation, with roughly ±10 percentage points of uncertainty. They are not measured functional coverage or manual acceptance. Reassess after each full class audit; route registration and spell counts alone cannot establish readiness.

| Priority | Class | Estimated implementation ready | Principal remaining verification risks |
|---:|---|---:|---|
| 1 | Zobal | 85% | Masks and removal, granted actions, copied double identity/book/lifecycle; damage, healing and displacement reuse previously exercised shared systems. |
| 2 | Huppermage | 80% | Rune combinations, quadramental resource payment/recovery, Light element selection, temporary actions and Heart of Fire lifecycle. |
| 3 | Sram | 80% | Invisibility and detection, traps, double death/removal, resource and rear-position interactions. Existing bounded double lifecycle evidence helps. |
| 4 | Feca | 80% | Shield stacking/removal, glyph ownership and entry/exit, protection and ally targeting. |
| 5 | Pandawa | 75% | Carry/drop and occupied cells, barrel ownership, drunkenness transitions, death and reconnect while carrying. |
| 6 | Ecaflip | 75% | Random branches, tarot draws and replacement, streaks, fleas and summon lifecycle; deterministic branch coverage required. |
| 7 | Enutrof | 70% | Deposit production/consumption, Drheller control, transformation and restoration. |
| 8 | Steamer | 70% | Turret control, Microbot networks and rail movement, Stasis and alternate-mode lifecycle. |
| 9 | Eliotrope | 65% | Portal pairing, routed range/LOS, displacement and portal removal without stale geometry. |
| 10 | Sadida | 65% | Multiple dolls, control/books, Voodoll links, shared damage and cleanup across deaths. |
| 11 | Rogue | 60% | Bomb placement/timers, chains and walls, simultaneous deaths, ownership and event ordering. |
| 12 | Xelor | 60% | Dial and position-dependent effects, time resources, AP reactions and extra actions, turn-order interactions. |

Active workstream, requested by the user: **Zobal inventory refresh first**, then implementation of proven gaps, automated prior-class regressions, and a complete manual acceptance battery. The lower order is tentative. Zobal review and correction are now requested; deployment remains separate from local verification.
