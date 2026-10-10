# Aniripsa utility and air runtime review — 2026-10-09

Scope: owned spell transactions for623,627,782,1532,1533,1538,1540,1541,1542. This work adds only `server/tests/test_aniripsa_utility_pipeline.py` and this report; no production module, service or catalog is modified. It uses existing native fixtures, legal decks, actual snapshot builders and published definitions. This is automatic runtime evidence, not manual client acceptance.

## Observed native consequences

Initial observations use level200, no equipped passives, caster injury300, ordinary native resources and owned allied actors. Target enemy is native Wonejo5525 at a clear legal position. Normal branches unless specified.

| Spell | Observed consequence beyond generic acceptance |
|---|---|
| Colimador623 | Enemy HP−50 and Colisiones dolorosas8019 at level25; allied target HP−62 with the same state. |
| Desfase627 | Target actual AP becomes0, state3896 level1 and lock3897 level1. Self targeting is legal; native cost1AP/2WP remains separate from the target AP reduction. |
| Juventud782 | Self state3870 at level600, MP+2 and native maximum-HP consequences. Nonself requests reject. |
| Infusión1532 | Wounded ally heals31 with received-healing resistance32+2; hostile target takes100 damage. |
| Vivificación1533 | Wounded ally heals33, received-healing resistance32+2 and resistance characteristic8+40; hostile target takes54 damage. |
| Prohibición1538 | Natural mode applies Frágil6624 level5, without immediate HP change on an unarmored enemy. Contra Natura's Incurable alternative is checked by an actual mode-toggle cast in the regression. |
| Psicosis1540 | Requires native minimum range3; the original range2 probe correctly rejected. Legal-range normal/critical tests pass: enemy damage69/86, FINAL_DMG_IN_PERCENT48−20 and FEROCITY9−20. |
| Aletargamiento1541 | High-health caster branch damages enemy189. Low-health branch is checked against its native135 base output and actual HP threshold. |
| Matraz Infectado1542 | Enemy HP−84 and Gangrena3876 at level84; allied target HP−105. |

These numbers belong to the stated fixture. They are not universal tooltips or equipped-player damage claims.

## Regression contracts

The new test module checks native normal/critical Colimador outputs, Juventud's scaled state/MP bonus, bounded Infusión/Vivificación healing, native healing-resistance rounding and resistance buff, exact-once payment and unchanged source snapshots, Desfase native repeat rejection with unchanged snapshot/RNG, real Contra Natura mode-dependent Prohibición selection, Matraz damage/state level, Aletargamiento HP-threshold branch, and Colimador duration through actual RuntimeMessages/turn/ACK/expiration progression. Rejected self targets also preserve snapshot and RNG.

Remaining independent contexts include Colimador's actual collision trigger, Prohibición's positive armored-target branch, Gangrena's qualifying activation event, and comprehensive normal/critical/cap/expiry permutations. Absence of those scenarios does not establish missing production code.

Follow-up: the first three named contexts now have passing actual-trigger tests
in [the utility trigger review](aniripsa-utility-triggers-review-20261009.md).
The remaining permutations are not implied by either gate.

## Execution status

Initial27-scenario observational probe completed. Final regression execution passed **11/11 methods in66.351s**, exit0, with normal/critical Psicosis, HP threshold, capped healing, native mode selection, real turn expiration and atomic rejection checked. Final log: `/tmp/aniripsa_utility_final_r2.log`. Initial exploratory logs are retained separately; redundant cold processes were stopped before the final sole batch.

Command uses the existing local verification environment, `PYTHONPATH=server:server/tests:server/tools`, `WAKFU_TEST_GRANTEDCAST=1` and `python3 -m unittest test_aniripsa_utility_pipeline -v`, with existing local database credentials supplied through the password-file setting. Secrets are not printed. The missing Redis environment falls back to read-only PostgreSQL catalog reads; native prewarm is consequently slow.

First regression pass:10 methods ran in86.230s; seven passed, and three fixture expectation errors were corrected (native repeat casting gate and1HP healing-resistance rounding). These were not production defects. Final11-method run, including legal-range Psicosis damage and debuffs, passed under a GC-disabled verification wrapper that flushes output and exits with the unittest result. No production runtime behavior is patched by the wrapper.

Regression source SHA256: `e351271be9faede677a7765e8a650c7e1482f9ad958ba952e0f22d18546e6ba6`.

No concrete production defect was established in these validated paths. The remaining collision/armored-target/Gangrena-event scenarios above are explicitly outside this passing gate; no all-spell or live-client certification is claimed.
