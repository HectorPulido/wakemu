# Native spatial occupancy and captured area activation affiliation

This review is read-only during the full class audit. Python and catalogs were not changed.

## QI.U is an obstacle-index population

`QI.U(int,int)` bounds-checks the XY coordinate (offsets 8–50). Out-of-bounds returns a newly allocated empty byte set. In bounds, offsets 52–65 return `QL.oY(QI.W(x,y))`, the actual stored cell set. `QL.oY` directly returns its cell-index map entry; absent entries can be null. The contents are obstacle IDs `QK.bcN`, not fighter or area affiliation `bcM`.

`QI.f(QK)` ignores null and any object whose `bcO()` is false (offsets 0–14). It allocates a slot through `QI.j(QK)`, which scans the QK array and writes the selected byte index through `QK.M(byte)`. In-bounds objects enter `QI.b(QK,x,y)`. This adds the obstacle ID to QL at the anchor, then every in-bounds cell in the square XY footprint from `x-radius..x+radius` and `y-radius..y+radius` for positive `bcL`; no Manhattan-circle filter is applied. Radius-zero obstacles occupy the anchor only. IDs identify obstacles independently of team, HP or native PV identity.

`QI.a(QK,x,y)` removes old indexed footprint and adds the supplied new footprint. `QI.a(QK,boolean)` toggles spatial indexing for an already registered obstacle. `QI.g(QK)` checks identity against its actual slot, removes its QL membership and array slot, and writes `bcN=-1`. Single-cell removal uses `QL.V(byte)`; positive-radius removal uses `QL.W(byte)` across all cell sets. The separate `QI.b/c/d/e(QK)` methods update ignore-ID sets and do not establish the spatial population.

## Fighters and portals

Actual `eGj` implements `bcO=true` and `bcP=true`; its `bcN` and setter delegate to its eGZ backing object. Its `bcQ` depends on native properties and is not a universal occupancy flag. Base eGZ defaults `bcN=-1`, so actual registration/backing implementation is necessary before exposing an obstacle ID.

`Qq.bcO`, `bcP` and `bcQ` all return false. Neither `faX` nor concrete `bcS` overrides them in the inspected bytecode. A GATE therefore does not enter the ordinary `QI.f(QK)` spatial population. Its fbm-derived bcN constructor value does not make its cell occupied. Qs owns its separate area population and invokes Qu area callbacks; Qs presence is not proof of QI registration.

`eMT` confirms two distinct contracts: offsets 251–261 compare the GATE's captured `Qq.bcM` with the caster's `eHg.bcM`; offsets 289–301 read `QI.U` and test its actual population for emptiness. A portal's own presence does not by itself block its destination. Fighters or other registered QK obstacles can block that location.

The Python gate predicate currently names its complete occupancy callback `cell_affiliations`. This name does not describe native QI.U accurately: the returned bytes represent obstacle IDs. Emptiness is the property consumed by eMT, so the proven core decision does not require interpreting them as teams. A general snapshot producer must capture actual obstacle registration, bcN, footprint, movement/toggle/removal lifecycle and map bounds; deriving these facts from current team or HP is insufficient. Registration callers for every combat actor type and all non-fighter obstacle subclasses remain unreviewed. No complete current producer is accredited here.

## Shared activation regression: property 1

Native `fbo.rNq` is `NOT_ACTIVATED_BY_ALLIES`, with ordinal and byte property ID 1. In both `faV.a(Qe,amP)` and `faV.a(int,amP)`, offsets 0–30 first require the target to be an actual amO, then compare the area's stored `ebh` captured affiliation with `target.bcM()`. Equal affiliations return false at offsets 33–34; otherwise execution delegates to Qq. The current owner affiliation is never consulted at this gate.

`NativeAreaEventRuntime._activate` currently handles property 1 by reading the current owner actor and comparing its affiliation with the target. This differs whenever the owner's affiliation changes after creation, or when ownership is an area PV rather than a fighter. It can also reject for a missing current owner although native captured affiliation remains available.

The required general correction is to compare the area's captured native signed-byte affiliation against an explicitly typed actual amO target affiliation. Unknown captured or target authority must remain unknown; owner team inference must not replace captured ebh. Target null and actual non-amO targets bypass this specific native check. Regression tests should create a property-1 area at affiliation 0, then change its owner to 1: a target with affiliation 0 remains excluded, while a target with affiliation 1 passes this check. Also cover a non-fighter owner retaining constructor affiliation -1, a removed/missing owner, unknown typed target authority, and charge accounting after filtering. No patch was made during the audit freeze.

## Evidence locations and limits

Native bytecode evidence: `.runtime/combat-review-20261007/QI.javap`, `.runtime/combat-review-20261007/faV-current.javap`; supporting offline disassemblies `/tmp/wakemu-{QL,QK,Qs,eGj,eGZ,eMT,fbo}-occupancy.txt`. Disassemblies were obtained with `javap -classpath 'client/lib/*' -c -p CLASS`. The actual GATE constructor probe remains `.runtime/combat-review-20261007/gate-probe/native-proof.txt`.

This review establishes native method contracts and a concrete shared event-filter discrepancy. It does not prove client delivery, full spatial snapshot equivalence, every registration caller, or live combat behavior.

## Implemented captured activation filter

After the audit freeze, the shared `_activate` property-1 check was corrected to use captured area affiliation and explicit target amO authority. Actual area targets read their registered area's captured affiliation, independent of owner and Qf presence. Explicit non-amO targets bypass this filter. Typed fighter targets can use the existing bound adapter producer only after `_actor` proves both `is_amO=true` and `is_eGj=true`; other amO types require explicit affiliation and are not inferred from eGj creation semantics. Missing type, affiliation or capture provenance raises before activation-charge changes. A missing owner does not prevent the captured ally exclusion; independent downstream child-effect source requirements still apply if activation proceeds.

Six new focused regressions plus existing event and GATE tests pass: 19 tests, 0.103 seconds. Command: `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python -m unittest server.tests.test_combat_area_captured_activation server.tests.test_combat_effect_area_events server.tests.test_combat_gate_area_lifecycle`. The previous existing ally-filter fixture now supplies explicit captured affiliation and target type facts. No conditions, adapter, target resolver, catalog or service edits were needed. This validation did not capture a before/after source manifest.
