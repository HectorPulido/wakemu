# Native symbiot creation predicate

Original lexer token344 (`IsSummonedFromSymbiot`) constructs `eOU` in `eQd`.
Its declared signature is exactly one STRING. The constructor compares that
string with `target` ignoring case: only that value selects the target; every
other string selects the caster. This is not the generic actor-alias selector.

`eOU.a` obtains an actual `eHg` through `eII.b`, then returns native true0 iff
that object is non-null and `dTC()` is true. `eGj.dTC` delegates to the actor's
actual `eGZ` implementation. Summon profile, breed, player identity, controller
and the independent `dTE()` summon flag do not establish this value.

The condition adapter now forwards the optional typed
`NativeActorAuthority.native_summoned_from_symbiot` into its selected actor
snapshot. The evaluator consumes that boolean, preserves missing authority as
unknown, and supports ordinary native negation. This route applies to detached
initialization actors as well as registered actors through the existing native
actor lookup. Creation sources must separately attest the field.

The non-eHg `eII.b` fallback consults execution-context `ePy.fyI`, then native
cell lookup where applicable. The new direct-eHg route does not invent that
fallback authority when it is absent.

Offline validation: original `ProbeNativeSymbiotCondition` passed20 direct-eHg
selector/boolean combinations plus null target. Python
`test_combat_symbiot_condition test_combat_controller_predicates` passed8 tests,
including incorrect arity/types, unknown creation source and negation. No
services or world process were started or restarted.
