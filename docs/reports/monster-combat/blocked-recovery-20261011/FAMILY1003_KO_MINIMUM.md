# Family1003: characteristic14 minimum

Installed registry identity identifies family1003 as the same `eWV` runner used by877, with `rCk` bound to characteristic14 rather than1. The native actor characteristic catalog identifies14 as `KO_TIME_BEFORE_DEATH`: a mutable, expandable PA with current/default3, minimum0, maximum3, and hard bounds0..2147483647. This is a scalar characteristic mutation; no knockout timer or scheduler was invented.

Eight frozen inventory references depend on1003:2348,3840,3841,3960,3961,4138,4139,5799. Actual effects170709/170720 and89715 use amount1, with flags9/15;89715 additionally carries removal mask index2 `[1026]`. These dependencies do not establish full monster qualification.

## Reused native primitive

`eWV.C` computes amount and optional percent of effective maximum. `eWV.c` calls `PA.os` and stores the effective minimum delta for a fresh runner. Reapplication adds the runner delta; `bbR` subtracts it from the effective minimum. Runner serialization is inherited from eZR; no new subclass payload is needed.

The existing minimum resource handler now maps877→PC1 and1003→PC14. It preserves877 HP raw setters and bytes, while stat14 updates only its PA maps. Retained rows preserve both actual family and characteristic; removal verifies their identity before applying the stored delta.

`fff.os` delegates to `ae`: it writes raw minimum, caps it at raw maximum, and raises raw current only when not frozen. Effective current still clamps against minimum/maximum. Therefore frozen copied PA cannot use its effective current as a substitute for hidden raw current. The existing `copied_raw_current` producer validates copied actor provenance and raw/effective consistency; the stat14 snapshot and minimum setter reuse that authority. Frozen copied raw current remains unchanged and reappears on minimum removal; mutable copied current is raised when necessary.

The ordinary native stat14 producer is unfrozen. An explicitly frozen stat14 without copied raw authority remains rejected, because its hidden raw-current producer is unknown. Missing/corrupt snapshots and retained characteristic mismatches fail before mutation. No absence of data is treated as a zero resource.

New regression tests cover exact amount1 installation/removal, family/PC retention identity, HP/AP/MP preservation, mutable and frozen copied raw currents, and rejection of unaudited frozen data. Existing877 tests remain unchanged. Independent focused validation passed **11/11** (new4, original minimum4, original constructor3) with all source hashes stable; private receipt `offline-minimum-ko1003-tests.json/log` records the result.

Private source evidence: `next-family-runners/identities.jsonl`, `next-family-runners/eWV.txt`, `fff-family1003.javap`, and the native actor characteristic catalog snapshot.
