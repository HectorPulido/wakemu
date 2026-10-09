# Registered summon flag in actor snapshots

The live fight 73 client inspector reported two live Cra beacons (actors 60/reference 3798 and 33/reference 3800) with controller 6 but `is_summon=false`. The native summon counter therefore remained zero. This is a snapshot serialization defect, independent of the casting criterion or ownership field.

Original `big` creation calls `eGj.ly(true)`. Original `eGn.zm` subsequently applies `pW.Uh` through `eGj.ly(boolean)`, which delegates to `eGz.lH`; that setter writes `pHL`, the exact field returned by `dTE`. `pW.aF/aG` serialize the common component as Ue:int, Uf:byte, Ug:byte, Uh:byte, Ui:byte, Uj:byte and Uk-presence:byte. Uh is byte offset 6 within that component.

`combat_summon_stats.registered_summon_stats` previously emitted all four booleans as zero. Every postcommit actor update thus erased the constructor's summon flag. It now emits Uh from the already validated registered authority `is_summon=True`. Independent fields and controller/group serialization are unchanged. Ordinary player and world-monster serializers retain Uh=false.

Both production `CombatSessionAdapter` paths use this serializer when the actor is in `native_summon_registrations`: initialization/postcommit stats serialization and live actor snapshots used by reconnect. The correction applies to the shared registered-summon source, including ordinary 307, captured 324 and copied-character registrations; no spell ID exception or client criterion bypass is used.

Validation: `test_combat_summon_stats` passes 2 tests. A bounded 128 MB original-client JVM probe invokes actual `pW.aF/aG` for ordinary and summon values and confirms field order, decoded Uh and byte offset 6. Probe source is private at `.runtime/combat-review-20261008/summon-flag/ProbeSummonFlag.java`. Existing live actors are not modified by this offline validation; deployment and a new/current actor update are required before claiming the client counter is repaired in gameplay.

Follow-up validation exposed a separate selector43 issue when the new faP border participates in the actual PV population: a proven NULL Qq owner was rejected as missing authority. Native own-area identity comparison must simply return false for that NULL pointer. `combat_effect_targets` now distinguishes a present NULL owner from an absent/invalid field, matching the existing selector46 contract. All 14 effect-target tests pass, including known NULL, matching owner and unknown/invalid owner cases.
