# Native fixed characteristic assignment: eWX

## Source contract

Original `eVi` prototypes expose twelve fixed-PC `eWX` families through the new native exporter. Families560–563 are the four elemental damage percentages; the same original class also implements566,568–574. Prototype575 has a null PC and remains explicitly outside this fixed-PC contract. No state or spell reference selects a handler.

`eWX.C` uses native parameter0 at actual `fRR()` level whenever `fKJ()>0`. With no parameter it samples `bbb().c(fixedPC)`, the actual caster characteristic. Extra parameters are ignored. The shared `eZR.n` path then applies the actual native value context before execution.

`eWX.c` dispatches only numeric PC kind0. `fNT` requires a non-null target with the selected PC; its absence sets notification suppression rather than inventing a value. The current handler requires actual registered fighters and explicit characteristic snapshots; other PV/null-PC paths remain unsupported with an explicit error.

`g(PA)` captures target `PA.aYS`, calls `PA.on(value)`, replaces mutable `Qe.aSg` with the resulting effective `PA.aYS`, and stores immutable `rCE=int32(after-before)`. Zero values and zero changes are not rejected. Frozen setters leave the effective value unchanged and produce removal delta0.

A subtle separate calculation controls characteristic events: `fNT` samples **caster** `PV.c(PC)` before and after the target setter. It appends the PC gain/loss event based on that signed difference. It does not use target `rCE`. Thus an ordinary different-target assignment normally retains event0 alone, while self-assignment adds the appropriate PC event.

`bbx` inherits event0; source `PK.aZO` event additions remain distinct. The handler allocates the running UID before L1, calculates after L1, exposes the live runner during L2, executes the setter, emits/registers the runner, and delivers L3/L4 with post-setter mutable value. The immutable removal delta survives later value observers. Retention, timing, corpse policy and executable guards come from the common authoritative context, not inferred duration or numerical HP.

`bbR` reverses only an executed runner (`rEj`) which satisfies actual `Ty()` retention and has a target PC. `h(PA)` calls `PA.on(int32(current-rCE))`: it subtracts the measured delta from the **current value at removal**, preserving intervening changes. It does not restore the original snapshot or subtract the packet's mutable value.

## Serialization and integration

The installed family identifies the fixed PC. eWX adds no AdditionalDatas override: generic owned payload carries its mutable effective value; the server checkpoint separately stores `setter_delta`. Central retained ownership must route all exported fixed families to this shared handler and `remove_set_current_characteristic`.

`NativeSetCurrentCharacteristicHandler(fight, packets, action_id=..., allocate_uid=..., context=..., rng=..., event_lifecycle=...)` exposes `prepare` and `__call__`. `FAMILIES` comes from the original fixed-PC catalog. Factory integration must attach the shared ordinary lifecycle; its standard stat context supplies executable/retained/timing facts. Central removal must dispatch `family='eWX'` to the supplied removal function.

The HP prototype574 is expandable. Its setter can retain raw current above effective maximum while `aYS` reports the maximum. The current fighter snapshot has no raw-current producer. Assignments/removals requiring this hidden value reject explicitly; ordinary bounded HP assignments use the same exact effective-value kernel. No raw current is silently discarded or fabricated.

## Verification

`ProbeNativeSetCurrentCharacteristic.java` invokes original `eWX.C`, private `g/h`, and real `fff` setters/getters. Constructor input supplies explicit hard/effective bounds; no native game catalog, server or AI runs. The C parameter callback supplies an already evaluated parameter; native parameter arithmetic itself remains covered by the existing shared parameter contract.

`verify_native_set_current_characteristic.py` compares all twelve fixed prototypes across clamp, frozen, zero, negative, Java-int overflow and intervening-change cases: **1,200 rows, zero mismatches**. This checks effective setter arithmetic, not hidden expandable raw storage or complete gameplay.

Eight focused unit tests cover actual handler lifecycle, every fixed family, caster-versus-target event differences, mutable value versus immutable removal delta, extra/missing parameters and explicit unknown expandable raw-current authority. All pass. Factory/central integration requires its own focused test after wiring; these results do not certify unconnected dispatch.
