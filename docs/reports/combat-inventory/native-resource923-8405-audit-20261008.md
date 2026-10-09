# Actual class-owned resource923 audit

Original Ready grant397463 has parameters `[2,0,3,0,8405,0,-1,0]` and requires
`not HasEffectWithActionId("caster",933)`, instance other than862 and caster
level at least36. The actual class8 granted action8405 selects root397431.
Its free-cell branch397434 requires `IsTargetCellFree()` and neither owned
area889 nor2042 at the target. Its ordered children include profile3793 creation,
area889/2042 creation and resource397441, family923, parameters `[1,0,0,0]`.
Thus a fresh legal free-cell placement can reach the original resource runner;
there is no need to forge a grant, an actor resource or a triggering effect.

`audit_class_resource923.py` runs production Ready at levels36/200 with a legal
owned class deck and selects only the actual Ready-granted8405 action through
NormalCastAudit. It preserves complete native permission, target and transaction
criteria, observes before/after AP/MP/WP, actual ordinary spell costs, new domain
events and emitted packet opcodes, and attempts a private representative commit.
Missing grant, rejected legal geometry, absent923 execution and a failed commit
remain explicit report outcomes. Compilation passed; runtime results are pending
Luna's isolated snapshot validation.
