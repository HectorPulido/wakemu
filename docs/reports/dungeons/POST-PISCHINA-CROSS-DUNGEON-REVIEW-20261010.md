# Cross-dungeon review after La Pischina

## Outcome

La Pischina's literal PositionTrigger frontier pattern was checked across all 109 classic dungeon definitions representing 107 distinct names. No additional full main route was recovered by this pattern. Source coverage remains 94/107 prepared main routes and 13 structurally pending. No server activation or restart was performed.

The exhaustive scan removes the earlier 80-cell discovery threshold, checks every inventoried native map with available exploration, and retains evidence for negative results. All 109 map records had native geometry. Of these, 104 have no native PositionTrigger objects. The remaining five are La Pischina, Plantiguardias (166), Riktus de Élite (139), Torre Mineral (133) and Morbax (150). Only La Pischina's literal trigger positions produce directed arena separators. Each other map has one trigger that does not separate its native walking regions. This does not rule out scripted actions or payload-defined activation zones: those mechanics are explicitly not inferred from a trigger's object position.

## Retrospective safeguards

[Updated structural audit](POST-PISCHINA-ALL-CLASSIC-STRUCTURE-AUDIT-20261010.json) includes the latest Wagnar/Ratacumbas V8 and La Pischina V10 configurations, alongside earlier configurations. Latest source selection produces 100 route configurations representing 98 names; four are already-known incomplete proposals (Base del Susurro, Arena Danzante, Vid Vil and Palacio Zollo), so that raw count is not the usable 94-name total.

Sixty-nine latest configurations pass the structural audit with no findings; 31 retain review signals. There is no demonstrated runtime-accepted premature walking path in those latest configurations. Twenty-three archived-guide count discrepancies remain review signals, not evidence that previously accepted gameplay regressed. The three raw-walk future-room paths in La Pischina are rejected by the actual room movement validator; its four trigger bindings each reject premature entry and accept entry after the corresponding frontier opens. Parallel trigger lanes are checked individually.

The audit now verifies exact native trigger identity/position, adjacent forward room ownership, exclusive destination ownership of the trigger cell, native directed crossing edges and the runtime rejection/acceptance contract. It preserves earlier frozen reports and supports versioned output paths. Native geometry and optional encounters are not rewritten to force a match.

Active configuration observations reuse the explicitly identified previous read-only database snapshot; this review does not claim a new deployment inspection. The earlier validated 37 ordinary configurations still have no blocked route in that snapshot. Separate legacy anchor configurations retain their previously documented issues.

The review also found six configurations with more encounters than the native room-count metadata: Castillo de los Cangwejos (4 versus 3), Cocodrails Delnilo (3 versus 2), Mekafábrica (3 versus 2), Torre Helada (4 versus 3), Sliptorium (3 versus 2) and Volcán Or’Hodruin (3 versus 2). The audit now reports these symmetrically as review signals. Optional rooms, alternative routes and historical metadata must be distinguished before changing a working route; these signals do not reduce the prepared count or claim a gameplay regression.

## Remaining blockers

[Combined review of all 13 remaining routes](REMAINING-13-COMBINED-NATIVE-REVIEW-20261010.md) preserves native geometry hashes, literal links and exact blocking causes. The PositionTrigger finding alone cannot solve missing native arrivals, insufficient six-player placement space, foreign or disconnected exits, absent intermediate monster-family identities, cyclic room flows, hub revisits with nonadjacent-stage authorization, or scripted encounters sharing one arena. Of the 13 pending main routes, only Riktus de Élite has a native PositionTrigger, and its literal position does not provide a separating boundary. These require their specific evidence or runtime support; they cannot be completed by inventing trigger locations.

## Validation and limits

Focused tests cover native trigger extraction, connected/disconnected parallel lanes, omitted-lane bypass, malformed native bindings and updated structural auditing. Native payload activation cells remain undecoded and are not snapped to nearby terrain. This review certifies offline structure and runtime movement checks, not graphical acceptance, original encounter scripts, optional puzzles, boss AI or rewards.

Validation command: `PYTHONPATH=server:server/tests:server/tools .runtime/local/verification-venv/bin/python -m unittest test_classic_trigger_frontier_audit test_native_position_trigger_cut_audit test_native_trigger_frontiers test_classic_dungeon_hybrid_structure_audit test_mixed_native_flow_extraction` — 30 tests passed. The independent reviewer additionally verified complete definition coverage, latest configuration precedence and matching V3 scope hashes.

The trigger inventory is frozen against the updated retrospective scope in [V3 exhaustive evidence](ALL-CLASSIC-POSITION-TRIGGER-CUTS-V3-20261010.json).
