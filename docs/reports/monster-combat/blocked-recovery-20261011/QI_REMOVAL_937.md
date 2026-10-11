# Family 937: reversible QI object removal

## Representative and reusable infrastructure

Haploide esporulador (2973, level 131) and four related definitions (3005, 3994, 4004, 4373) share books 4250/4251 and family 937 as their sole missing family in the sealed inventory. The existing `NativeQIRegistry.remove/register` primitives implement the relevant grid topology operations, but the runtime currently requires every non-retired actor to retain a QI slot.

## Installed lifecycle

The runner `eYa` accepts a target implementing `QK` and a context with a non-null grid. Application calls `QI.g(target)`. Invalid target/context/grid calls the native failure/reset path. Removal rechecks that authority and calls `QI.f(target)` only when the actual runner's `rEj` is true.

`rEj` is not an alive/dead or registration flag. Fresh `eZR` initializes it false. Generic `eZR.a(Qe, boolean)` invokes the subclass application, then sets it true before application notification; restored runners hydrate it from `iB.MB`. An actual application can therefore set this flag without changing a grid slot. Preserve the source runner's lifecycle rather than infer the flag from current occupancy.

`QI.g` first checks `bcO`, then a valid obstacle byte. It removes topology only if the slot contains the exact target object and its anchor is in bounds, clears that slot, and writes obstacle byte -1. `QI.f` checks `bcO`, reserves a fresh slot, and indexes in-bounds coordinates. `eGj.bcO` returns true; arbitrary areas still require their own typed QK proof.

## Remaining integration requirements

Add an explicit temporary-absence producer so `current_registry` accepts the owned removal while preserving combat/global actor registration. It must remain distinct from death, summon retirement, carrying, and out-of-play transitions. Restoration must use current coordinates and the native first-free allocation rule, not force the previous slot. Preserve the actual applied-runner flag in retained removal data.

Repeated removal/restoration is not automatically a reference-counted suppression: each native runner executes its own `QI.g/f` calls. Establish repeated-runner behavior, identity checks, slot exhaustion, out-of-bounds handling, relocation and rollback before generalizing. Existing strict registry invariants must not be weakened merely to accept an actor with obstacle byte -1.

Source bytecode is retained privately in `next-family-runners/eYa.txt`, `QI.txt`, `eZR.txt`, and `eGj-properties.txt`. No handler or activation is claimed by this audit.
