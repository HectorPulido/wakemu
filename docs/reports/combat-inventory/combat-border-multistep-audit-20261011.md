# Combat border and generic movement audit

The observed one-loss behavior across multiple border cells is consistent with the authored border guard. It does not establish that movement callbacks are missing. A separate live movement timing defect is under regression qualification. No production change or deployment is included in this report.

## Authored border contract

Installed template46 has entry masks10000/10001/10008. Native root152027 checks `not HasEffectWithSpecificId("target",152028)` before MP-loss3641 and marker152028. The marker is family400 with duration1, not an unsupported effect. The private native dump `.runtime/local/border46-effect152027.txt` records the exact criterion at line48 and the marker definition from line133 (`esW=1`, `esr=true`). Current timing export separately records actualaZT/aZU clock routing; actual timer boundary is to be included in the focused regression before further expiry claims. The existing dispatcher test proves that a second10000 call does not remove additional MP while152028 exists.

One faP bootstrap PV owns the entire QI.P border footprint. Visible cells are not independent area objects. `combat_battleground_border.install_battleground_border` constructs one row/UID whose `native_cells_xy` contains all selected border cells. Marker lookup is by target/effect reference, not by visual cell. Re-entering a border cell while the marker exists therefore must not bypass the authored guard.

3641 requests2MP. `combat_resource_loss.resolve_resource_loss` follows eVZ arithmetic: stochastic rounding of `requested*0.5*(1+casterWillpower/100-targetWillpower/100)`, clamped to requested. The faP source has no PA willpower characteristic and uses nativezero for that absent characteristic; target willpower remains authoritative. Requested2 is not a promise of actual2. The existing production-dispatcher fixture has MP3→2 and installs actual5227/152028.

## Generic step delivery

`combat_effect_area_events.movement` freezes lists for10001 (outside→inside),10008 (inside→inside),10002 (inside→outside) for each call. `prepare_area_movement` loops every supplied path cell and calls that movement method. Other glyphs therefore depend on their own entry masks, criteria and child retention. Border once-only behavior must not be generalized to every glyph. Prototype910, for example, also subscribes10008 but guards its own152453 range modifier and removes it on10002.

## Independent live timing risk

The current `combat_movement_runtime._with_areas` first runs the complete paid move and only afterward calls the area provider with its path. Every cell callback can run, yet a resource-loss callback arrives after all steps have already been paid/executed. This differs from existing `combat_sequential_movement.execute_steps`, which pays one scheduled step, delivers its callback and checks remaining resources before the next step. The AI native oracle already uses this sequential callback path; the live client wrapper currently does not.

A runtime-only replacement candidate reuses execute_steps, calls the existing provider after each actual step, preserves actor identity using adopt_fight, and encodes the executed truncated path and final resources. Ordinary no-area serializer validation remains before mutation; outer runtime adoption remains atomic. Candidate `.runtime/border-movement-review-20261011/combat_movement_runtime.py`, SHAa5dd1eca3744b7d96b43417cebb9a8ea43c6ccfacdee5551de59da23448e8645. A separate live-wrapper baseline counterexample and candidate regression are delegated to Luna; neither has yet qualified this candidate. The authored border guard is unchanged.

## Integrated actual-source qualification

The movement runtime candidate `a5dd1eca` and six permanent `test_combat_border_multistep` regressions are integrated. The actual checkout passed all 77 movement/border selectors without overlays on catalog `677…`; receipt: `.runtime/full-regression-20261011/border-movement-integrated-actual-source-77/result.json`. The global guard reported concurrent drift in three unrelated source/test paths, so this is scoped qualification, not full-tree acceptance. No service deployment has occurred.
