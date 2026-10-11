# Family 982 state cleanup: source audit and bounded implementation plan

Status: source audit only. No runtime registration or monster activation is claimed.
Representatives: 3024 (Esporajardinera), 3046 (Ogrest), and 3072 (Capitan Miau).

## Installed behavior

Installed `eXW` extends `eXY`. The fresh `eXY()` constructor does not assign
`rxC`, so the Java default is zero. `fPJ()` copies that field. `C(Qe)` is a
no-op: spell parameters do not establish a different container type.

`eXY.c` requires the recipient's actual `Qf`, casts it to `eZV`, and calls
`b(rxC, true, true)`. `eZV.b(int,boolean,boolean)` traverses the real manager,
collects distinct non-null container objects whose `PL.aZY()` equals `rxC`,
and then invokes its existing container-removal operation. The container
snapshot preserves first encounter order. This is not ordinary dispel
eligibility and must not use `default_dispel_eligible` as a substitute.

Only after that first stage, `eXW.c` traverses the remaining recipient manager.
It collects actual `eZk` instances for which `fNh()` is true in a Java
`HashSet`, and invokes `bbN()` on each. A generic retained effect or a state
with a matching numeric ID is not sufficient evidence of this runner type.
The set iteration order is not proved by the manager's encounter order.

## State flag authority

`eZk.fNh()` returns the private boolean `rHz` directly. Fresh construction
sets it false; `aWr()` also resets it false. Hydration copies `ij.Me()` into
`rHz`; installed `ij.Me()` returns its `xh` boolean. `mj(boolean)` explicitly
changes the runner flag. Therefore the flag cannot be inferred from state
profile dispellability, protection, level, timer, or the existing Python
`RunningState.protected` field.

The current `RunningState` record does not carry an independent `rHz`
producer. `RetainedEffect` likewise has dispel eligibility fields but no
source-qualified `eZk.fNh` operand. No default-true or default-false fallback
is valid for an arbitrary restored or externally modified carrier.

## Reuse and remaining work

1. Reuse `NativeRetainedEffectView` for complete manager ownership and
   `NativeRetainedRemoval` for validated removal, child cleanup, and packets.
   Preserve exact recipient manager scope and prevalidate supported removals.
2. Represent actual container-object identity separately from numeric
   container ID. Snapshot matching type-zero containers before mutation and
   remove through their native grouped lifecycle.
3. Persist a typed state-runner flag with its producer. Fresh local `eZk`
   construction can prove false; hydration must preserve the actual `ij.Me`
   value, and a future native `mj` producer must update that same field.
4. After container removal, take a new state-runner snapshot. Validate the
   native HashSet iteration authority before claiming order-sensitive state
   removals are equivalent. Do not sort by UID to fabricate that order.
5. Add regression tests for two-stage selection, duplicate container objects,
   null container exclusion, manager ownership, fresh false state flags,
   hydrated true flags, unknown provenance, and cancellation/rollback. A live
   representative replay remains necessary after the implementation exists.

## Evidence

Private installed `javap` evidence is under
`.runtime/monster-blocker-recovery-20261011/next-family-runners/`:
`eXW.txt`, `eXY.txt`, `eZV.txt`, `eZk.txt`, and `ij982.txt`.
No shared combat files or existing test assertions were changed for this audit.
