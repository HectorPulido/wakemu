# Occupied free-cell diagnostics do not imply a casting defect

3573Grala and3720Edith Pioaf share spell4871. Historical native`twT` diagnostics
were casts on the occupied enemy identity7: rejecting them is correct. Each
monster also had three accepted empty-cell casts with no selected effects.
Thus occupancy rejection alone does not explain their pending status.

All four installed roots use native`anJ`, `t inv-barre:0-pied:4`: the empty
centre is followed by four cells extending away from the caster. Both actors
have native physical radius0. An adjacent enemy cannot be hit by casting on
an orthogonal adjacent empty cell. A distance2 enemy can be hit by casting on
the intervening distance1 empty cell.

The historical eight-attempt receipt covers only adjacent enemy placements.
Existing per-scene target-class budgeting and the existing native area envelope
(maximum1 plus extent4) already allow later placements through distance5.
No additional runtime change, resource/state injection or ordering exception is
justified. The registered-empty-footprint fix prevents false empty labels but
is not the main explanation for these radius0 historical cases.

Two NEW cheap tests pass using actual Actor objects and existing native geometry:
adjacent accepted empty casts cannot select the enemy; distance2 makes the first
existing ordered empty candidate cover it. This proves a geometric candidate,
not a full transaction or activated monster. Full3573/3720 replays remain pending.
Private exact root/source receipt: `free-cell-directional-witness-observation.json`.
