# Family 937: temporary QI absence audit

This is a source audit and test plan, not runtime admission or a deployment claim.

## Native lifecycle

Installed `eYa` extends `eZR`. Its constructor and `C(Qe)` do not decode effect parameters. `c` calls `fPL`: it requires a recipient, PN context, non-null PN.bad() QI, and a QK recipient; valid execution calls QI.g(QK). Invalid authority records the native no-execution outcome. `bbR` checks the same authorities and calls QI.f(QK) only when rEj is true. Native flags are bbz=false, bbA=true, bbB=false.

The generic `eZR.a(Qe, boolean)` calls the subclass execution, catches its exception, then sets rEj=true unconditionally before notification. Fresh/reset rEj is false; hydration reads iB.MB(). Therefore rEj is an applied-runner flag, including an execution that did not remove QI membership. It must not be reconstructed from actor life, retirement, or current membership.

## Catalog scope

Root identified Haploid profiles 2973, 3005, 3994, 4004, 4373 with spells 4250/4251. The sealed monster extraction trees contains those spell roots (4250:112219/112220; 4251:112239/112240), but no effect_class937 rows. This artifact cannot establish their 937 effect timing or flags; absence here is not proof of absence in the installed client. A fuller source catalog is required for those fields.

## Reuse and integration boundary

QI.g/QI.f are reusable primitives. Current registered-grid validation requires every live actor to remain present, so temporary absence needs a distinct, effect-owned lifecycle producer. Ordinary death or retirement cannot serve as that producer. Preserve the applied-runner flag independently of whether removal actually occurred. Revalidate target/context on restoration, and use native QI.f registration rather than assuming the old topology slot is reused. Position changes while absent and retained removal must preserve native authority.

## Focused regression plan

1. Actual QK removal changes QI membership while actor identity and combat life remain intact.
2. Unknown authority rejects before mutation; a native no-op still preserves the applied-runner distinction.
3. Retained removal restores only an applied runner and uses the current valid QK position.
4. JSON checkpoint preserves explicit absence provenance and applied flag; forged or missing provenance fails closed.
5. Overlapping absence owners, restoration conflicts, and rollback do not silently invent grid membership.

Source artifacts: `.runtime/monster-blocker-recovery-20261011/next-family-runners/eYa.txt`, `eZR250.txt`, and `.runtime/monster-combat-extraction-20261010/trees.json.gz`. No production code or original tests were changed by this audit.
