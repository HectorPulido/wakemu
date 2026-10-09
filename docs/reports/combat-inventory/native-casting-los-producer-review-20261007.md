# Native casting visibility producer

`combat_casting_los` composes the existing original Sf/fcr raster with an exact
QI.h dynamic visibility callback and the complete owned QK registry. It does
not filter probes through walkable cells. Visibility blocking is independent
of movement blocking and obstacle IDs remain distinct from affiliations.

Native QI.h ignores z, calculates signed-int W/index bounds, checks mask256,
then iterates QI.U. An actual null slot returns false immediately; otherwise
the result is true for an actual QK.bcQ blocker absent from biO. Index bounds
are not aK rectangle bounds: some side-outside coordinates alias valid indices.
Complete current registry entries have no unresolved null indexed slots, so
iteration order cannot change the production boolean within that domain.

Native eGj.bcQ consumes complete current fight properties:
`!INVISIBLE_SUPERIOR(18) && (INVISIBLE_REVEALED(6) || !INVISIBLE(5)) && !DONT_BLOCK_LOS(54)`.
Registered actual Qq.bcQ is constantfalse, including configured faW areas;
their descriptor fTq flag is not a substitute for actual Qq.bcQ.

Native fcr includes the source obstacle in biO and clears the set via bdM
after the ray evaluation. The shared helper computes the result read-only;
the integration caller owns that cleanup. Fresh Fight explicitly captures
`native_qi_visibility_ignored_slots=[]`; missing restored authority rejects.
The target fighter is supplied by the casting context's actual QI lookup.

`ProbeNativeQIVisibility.java` verifies all65536 short masks, unused z,
W alias/bounds, actual null and non-null slots, blocking flags, exclusions and
bdM. The Python/native exhaustive mask differential had **zero mismatches**.
Four pure test methods cover masks, dynamic slots, null iteration order and
live property rules. Unit validation is delegated to the validation agent.
The existing Sf topology catalogs constrain available map evidence; absent
topology does not become a clear ray. No live services were changed.
