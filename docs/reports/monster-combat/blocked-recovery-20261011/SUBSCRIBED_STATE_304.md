# Subscribed state application: native family304

Offline recovery only. No services or catalogs changed.

## Representative and source proof

The bounded screening reported state application children52091 (4073/4960) and51309 (3763). Family304 uses native `eWu`; family310 uses `eZk` and must remain distinct. `eWu` extends `eXh`/`eZR`, and fresh registration through `Qe.d` stores a listener before state calculation. The subscription runner allowlist previously omitted304, so normal state execution ran too early instead of waiting for its native event.

The installed client bytecode (`.runtime/local/current-eWu.txt`) proves that the fresh constructor leaves `kFB=0`, sets `rBo=-1`, and `b(iP)` writes AdditionalDatas `il.el(kFB)` and `il.en(rBo)`. The installed Java probe `.runtime/monster-blocker-recovery-20261011/subscribed304/ProbeNativeDeferredRunner304.java` produced:

```
eWu proto=08850710a00618d8b21520002a06080410051800300738f9ffffffffffffffff01420d580070ffffffffffffffffff015a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800
```

This is fresh value0/status-1/unexecuted, with AdditionalDatas fields11=0 and14=-1. It is not a created state carrier or a calculated state level.

## General correction

Register304 as an audited deferred runner and emit its actual fresh AdditionalDatas. Existing subscription masks, retained manager checks, timers, event replay and state handler remain authoritative. Ordinary unsubscribed304 execution remains unchanged; no native condition is bypassed.

Two NEW regression tests cover the installed wire and deferred dispatch without premature criteria, probability or state execution. Existing subscription tests remain unchanged. TimeDatas protobuf field ordering differs between encoders; tests compare its parsed fields, following the existing subscription suite.

## Validation limits

Installed Java probe and exact pure production encoder comparison pass. Syntax compilation passes. Full runtime tests require the native catalog; this worker's sandbox denies PostgreSQL loopback access. Independent local catalog harness and affected monster replays are coordinated separately. This document does not assert activation readiness or full-book qualification.
