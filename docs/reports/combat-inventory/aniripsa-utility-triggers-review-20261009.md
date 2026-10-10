# Aniripsa positive utility trigger review — 2026-10-09

`server/tests/test_aniripsa_utility_triggers.py` extends the frozen eleven-test utility suite with actual consequences from three native branches. No production code, services, published catalogs or persistent combat records were modified.

| Branch | Actual producer and setup | Observed consequence |
| --- | --- | --- |
| Prohibición 1538, positive armor | A level-200 ally receives 196 armor at real Ready from two legal aptitude-36 points. Owned cast executes group367731 and leaves367732/367733. | Ally armor196→0; casterHP2150→2395 (+245); targetHP stays2150. The healing selector8194 differs from armor target selector1. |
| Gangrena 1542 | Owned cast installs3876 on ally8, then actual turn advancement ends that target's turn through production turn-end processing. No synthetic1002 injection. | Additional targetHP2045→1961 (84damage), casterHP2255→2338 (83life return after native healing/resistance rounding). |
| Colimador623 collision | Real granted Repulsión7979 pushes a target into another occupied, registered QI cell. Compare two otherwise equivalent fixtures, with/without prior Colimador. No synthetic2254 injection. | Target remains blocked in its original cell; baseline collision loses0HP, Colimador loses25HP in addition to its earlier direct cast damage. |

Validation: one native process at a time, GC disabled, normal owned spell transactions and existing read-only catalog DB. `/tmp/aniripsa_utility_triggers_r2.log`: **3tests passed,19.525seconds,exit0**. The final test file replaces diagnostic prints with assertions for these observed exact values and renames the Prohibición test to identify its actual healing recipient. The first exploratory batch passed collision and Gangrena but failed an incorrect assumption that Prohibición heals its armor target; the current assertion follows its native selector and observed caster healing.

This verifies the listed offline scenarios, not every passive interaction, critical branch, armor scale, map collision or live-client display. Manual whole-system acceptance remains separate.

The final exact-assertion file was independently rerun: **3 tests passed in
20.161 seconds**, exit0. Evidence:
`.runtime/aniripsa-implementation-20261009/utility-triggers-final.log`.
