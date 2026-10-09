# Move-away-cell carried actor guard

Original `eXp.fOt()` resolves the caster `bfr` as `fax`, independently of the explicit target fighter. `eXp.fOr()` requires a caster and target cell, then rejects `eXD.fOS()`, which reads that caster's `fax.buX()` (carried status). This is a native legality no-op before displacement geometry, rather than an unsupported actor exception.

The shared family331 handler now preserves this carried-caster no-op before ordinary path/property validation. It does not infer a recipient from an empty cell. Carrying actors, larger footprints, and uncertified life state remain guarded because their movement contract is separate. Ordinary-domain rejection now attaches typed actor ID, HP, radius and carry relations for offline diagnosis.

Regression `NativeDisplacementTests.test_move_away_cell_carried_caster_is_native_noop` checks no position, packet or UID mutation and forbids property/path evaluation. Compiled fixture execution is delegated to the serialized validation queue. The actual spell6468 bulk failure needs the actor diagnostic to distinguish this branch from other unsupported domains. No services were restarted.
