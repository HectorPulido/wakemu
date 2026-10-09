# Native empty weighted lottery boundary

The complete active batch contains two rejected self-target scenarios at levels60 and200 for effect359670, family341. They are not sufficient evidence of an incorrect RNG implementation.

Offline `javap -p -c eXR` proves that `fPC` first filters children through `t(eVn)` (level bounds and criteria), sums their probabilities using Java float/int conversions, and calls `GS.ne(total)` for each requested draw without an empty-population guard. `javap -p -c GS` proves that `ne(int)` delegates directly to `java.util.Random.nextInt(int)`, which rejects nonpositive bounds. Evidence is saved under `.runtime/combat-review-20261007/{eXR,GS}.javap`.

The local tree359670 requests one draw and has13 children, each requiring a distinct target state7961 through7973 before additional effect/deck/turn checks. A fixture without any matching target state has no eligible child. Converting that situation to an unconditional successful no-op would diverge from the proven runner.

The shared lottery already rejects nonpositive totals explicitly and has regression checks for zero weights, exhausted draws, ordered selection and integer bounds. Further work must establish the spell's real casting preconditions and state producers, then exercise eligible populations. These two fixture failures must remain separate from unsupported handlers and missing protocol data. No service operations were performed.
