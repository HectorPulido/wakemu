# Native AI control and owned-summon neighborhood predicates

`IsControlledByAI` is native parser token305, class `eNH`. Its required
literal string selects target only when equal to `target` ignoring case;
every other string selects caster. It resolves an actual `eGj` and reads
`eGj.fqL`, which delegates to the fight context's `eGZ.fqL` (`eGz.pHH`).
It does not derive AI control from player, class, controller or summon flags.

The typed producer is `native_controlled_by_ai`, with missing authority kept
unknown. Fresh snapshots initialize it from the actual existing actor bootstrap:
PC, NPC and registered-summon serializers emit `po.SX=0` after characteristics.
Original `po.aG` reads true only for byte1; `eGm.zm` applies it through
`eGj.lx` to the live context. `ProbeNativeAIControl` executes that original
decode/application/predicate chain for bytes0,1,2,-1 plus null resolution,
and all checks passed. The runtime resolves the registered or scoped detached
actor through `native_actor`. Target-cell-to-fighter resolution remains
explicitly unknown in this callback.

`native_ai_control_baseline` is a separate typed contract for native `dpR`,
used by family325 removal. Actual `bjo.dpR` returns false (`biB` inherits it),
whereas actual `bje.dpR` returns true. The ordinary authority's known serialized
source classes supply those values; live AI-control state remains independent.
Family325 implementation and any live serialization updates belong to the
collision/resource worker, not to this predicate change.

`HasSurroundingCellWithOwnSummon` is token229, `eMP` over `eMJ`. It supports
selector plus breed (default VON_NEUMANN), selector plus mode (wildcard breed
-1), and selector plus breed plus mode. Ownership always belongs to the caller,
even when the neighborhood center is the target. It scans the existing complete
`fUQ` roster, excludes the caller itself, compares direct `dpu` owner identity,
and optionally compares the native signed-short breed. No HP, off-play or
summon-flag filter is added.

MOORE uses actual `aBn.cI` and VON_NEUMANN uses `aBn.cH`; both include the
center. Signed-int wrapping at coordinate boundaries is preserved. Original
native parser signatures and 75 original cH/cI rows, including signed-int
extremes, passed the offline oracle. Regression tests compare all75 geometry
rows and check ownership, breed and shared grammar contracts. The runtime
uses `native_actor_population`, so transient native construction scopes do
not borrow an unrelated battle roster. Unit execution is delegated to offline
validation; no services, containers, databases or AI code were changed.
