# Native alignment predicates and static casting path

Targeted original-client bytecode: eQb/eQd, eNX/eNY, eII, fcj, Sn and QI. Sources and catalogs remain frozen during the class audit. The separate spell-effect-tree export still contains the old cwN empty-cell hint; its correction is pending, not silently applied.

## Criterion predicates

Lexer314 IsInAlignment maps to eNX; lexer315 IsInDiagonal maps to eNY. Both have exactly the empty signature and require an actual fight from context argument4 (`fbX` or eVw containing one). They resolve first/second coordinates with eII.d(false/true): actual aBn directly, or actual eHg.baM; other objects or null coordinates return native -1/false. An unavailable emulator snapshot is not proof of native null. Both ignore Z and include identical XY coordinates.

IsInAlignment returns0 iff x1==x2 OR y1==y2. IsInDiagonal is **not** absolute-displacement equality: it computes `(int)Math.pow((double)(int)(x2-x1),2.0)` separately for X/Y and compares those integer results. Subtraction wraps Java signed int; double-to-int conversion saturates at INT_MAX. Consequently unequal absolute displacements at least46,341 both saturate and return true. This contract is distinct from static casting diagonal below.

`ProbeNativeAlignmentPredicates.java` executes the original eNX/eNY methods against a constructor-free actual native fight object. It checks native null prerequisites and accepts stdin CSV `x1,y1,x2,y2`, returning native alignment/diagonal codes. Five direct rows confirm diagonal1/1 true,1/2 false,46,341/46,342 true,INT_MIN/INT_MAX true, and identical XY with different Z true. No installed spell catalog or client connection is loaded.

## Static fcj casting restriction

The five-argument overload calls the six-argument method with path option false. Normal client fcO passes selected cwN instead. Inputs come from the entire condition-selected fyP: linear b/cwM, diagonal k/cwT, and linear-path e/cwV. Ordinary static validation follows this exact order:

1. Read linear and diagonal independently. If neither, return true.
2. Initialize `linearAccepted=linear`.
3. If linear: compare target XY to caster.baM XY; accepted iff cardinal alignment. Evaluate selected linear-path flag even if alignment already failed.
4. If aligned AND linear-path: obtain Sn singleton; configure caster.bcK/bcL/bvz and QI; temporarily unregister actual target obstacle if target eGj exists; run Sn.a(caster.efR,target,pathOption), call QI.bdK restoration, then Sn.bal cleanup. A false path clears linearAccepted.
5. If no diagonal OR linearAccepted, return linearAccepted.
6. Otherwise return Math.abs(int32(target.x-caster.baM.x)) == Math.abs(int32(target.y-caster.baM.y)). Math.abs(INT_MIN) remains negative. This diagonal alternative includes same XY and ignores Z.

Thus linear and diagonal are alternatives; a failed linear path can still fall back to diagonal. A helper requiring both restrictions would be wrong. A helper skipping the linear-path getter solely because alignment failed would also change evaluation of conditional tables.

## Sn straight-line path and cwN

Sn.a(aBn,aBn,boolean) returns false for null endpoints, true for identical full aBn, false for noncardinal XY. It uses actual starting physical position efR, which must not be substituted with baM. It looks up terrain columns, source floor at source shortZ through VA.a, then walks each cardinal step using Sm.a for exact physical footprint/height transition validity. Missing column, missing floor or failed transition returns false; caught Throwable during the step loop also yields false.

After each transition check, when pathOption is true and environment is QI, it tests QI.Z on the **current** traversal cell before advancing, rejecting if true. This visits source and intermediate cells, excluding final destination. QI.Z finds the cell index and tests `(QI.biD[index] & 768) != 0`, i.e. bits256 or512; invalid index returns false. That native occupancy/flag source is independent of mandatory empty cwU and endpoint-only checks. No meaning for the bits is inferred beyond this exact consumer proof.

## Shared implementation and oracle boundary

The condition helper needs explicit current fight presence and resolved coordinate presence, with the exact Java arithmetic above. The static casting helper needs all selected flags and distinct caster.baM/efR snapshots; it can settle unrestricted, cardinal-no-path and diagonal cases without Sn. For an actual aligned linear-path case it must consume the exact native footprint/column/height/occupancy traversal producer. Unknown traversal facts remain unknown; no default clear path.

A future bulk oracle should invoke original static fcj against actual configured fyF/fyG, native fighter source, QI and terrain. It should compare all combinations of linear/diagonal/linear-path/path-option, cardinal/diagonal/nonaligned/same-XY endpoints, source baM versus efR, target obstacle exclusion/restoration, column gaps, height transitions and source/intermediate/final flag256/512 placements. The separate eNX/eNY stdin oracle already supplies exact criterion arithmetic. Runtime helper implementation and catalog correction remain deferred until the source freeze ends.

## Implementation and tree synchronization after the audit

After the audit exited normally, IsInDiagonal was added to the shared condition grammar with its native empty signature and explicit boolean authority. `combat_condition_diagonal.native_diagonal` preserves signed-int subtraction and Java squared-double integer saturation, independently of static fcj. RuntimeConditionAdapter computes it from actual caster coordinates and the actual target fighter/registered area PV, or the explicit target cell/null passed by eZR.I. A non-null unresolved target is rejected. The adapter itself represents the actual current fight; missing generic contexts remain unknown. Seven oracle coordinate rows, including wrap and saturation boundaries, were checked against original eNY. Ten lightweight diagonal/null condition tests pass.

ExportSpellEffectTrees now writes cwU in its free-cell column. Local structural hints were synchronized from the corrected native baseline: all722 class definitions checked,5 changed; all167 granted definitions checked,17 changed; the single NPC structural definition was checked with0 changes. Only metadata was edited. Exact full-object comparison after normalizing free_cell confirms every other field, all effects, roots, criteria and ordering remain identical. Backup files are under `.runtime/combat-review-20261007/trees-before-cwU/`; the checked before/after and semantic SHA256 manifest is `native-spell-tree-cwU-sync-20261007.json`. No static fcj/path approximation was implemented.
