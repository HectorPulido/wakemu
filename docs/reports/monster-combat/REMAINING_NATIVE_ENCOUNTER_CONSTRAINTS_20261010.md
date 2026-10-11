# Remaining native encounter constraints — 2026-10-10

This report describes five references whose complete spell books still require original encounter or lifecycle prerequisites. It does not activate them and does not classify them as fully functional. The separately authorized seven trainer/racing exceptions are outside this five-reference group.

## Exact remaining cases

| Reference | Monster | Passing owned spells | Remaining spell | Authoritative prerequisite | Classification supported by evidence |
|---|---|---|---|---|---|
| 3217 | Jugador | 4535, 4537, 4536 | 4538 | `IsSpecificArea(769) or IsSpecificArea(770) or IsSpecificArea(771)` | Native encounter object dependency; deferring until encounter support is justified. A particular mission identity has not been established. |
| 3949 | Infiltrado | 5624, 5626 | 5625 | `IsOnSpecificEffectArea("caster", 1039)` | Native encounter glyph dependency; deferring until encounter support is justified. A particular mission identity has not been established. |
| 3261 | Esqueleto de arquera | 2325, 2326 | 2390 | `HasState(546, "caster") and IsEnnemy()` | Missing native lifecycle producer; a mission-only exception is not established. |
| 3263 | Esqueleto de lancera | 2363, 2364 | 2390 | `HasState(546, "caster") and IsEnnemy()` | Same lifecycle dependency as3261. |
| 3276 | Esqueleto de soldado | 1237 | 2390 | `HasState(546, "caster") and IsEnnemy()` | Same lifecycle dependency as3261. |

Passing entries describe effectful native preview cases in the certified receipt. They are not permission to publish partially validated monster books. The pending cases were rejected by the actual native casting criterion (`twV`); range failures (`twI`) were retained separately.

## Jugador: actual fake-fighter area targets

`IsSpecificArea` tests the target PV's native effect-area identity. It does not test a map identifier. The installed definitions769,770 and771 are `bcQ`, native type15, `FAKE_FIGHTER`, with point geometry (`anD`), maximumlevel0, no effect roots or properties, and visuals8423,8421 and8422. The owned book is Macerar4535, Tomar4538, Guarnición4537 and Hornear4536. Its state branches include Tomates3046, Queso3047 and Pimientos3048. These original names support a cooking encounter/minigame classification; no particular mission ID is established. An ordinary player or empty cell cannot satisfy spell4538's original condition.

The shared runtime already supports native fake-fighter area objects. What remains is the original encounter placement/ownership producer and validator selection of actual registered area PV targets. Constructing an invented spell, changing a player's identity, substituting a map ID or disabling the criterion would not establish the native encounter.

## Infiltrado: actual glyph under the caster

Area1039 is an original `bcT` point glyph, native type0, maximumlevel0, without effect roots or properties, using visual800307. Sangre Fría5625 requires this registered area under the caster and applies native4095 (*Camuflado*). Ordinary map1134 fights do not produce it.

A reusable solution is original encounter-area placement, followed by ordinary movement onto the resulting glyph and execution through unchanged casting guards. The original placement source has not been recovered from the extracted owned spell/state graph or installed client Lua scripts.

## Three skeletons: second-phase state lifecycle

Their shared spell2390 requires caster state546 (*Duro de Pelar*) and an enemy target. Initial state545 (*Inmortal*) contains the following original dependency chain:

1. Root25902 listens for KO1010.
2. Its descendants include retained kill runner25904 and listener25907.
3. Listener25907 subscribes to1026 in maskindex2, corresponding to lifecycle channel4.
4. Its children are restoration196 runner25905, removal of545 by25908, and application of546 by25909. Runner25909 additionally requires `GetInstanceId() <> 1035`.

The1026 source is unresolved. Publishing it after restoration would be circular: the listener waiting for1026 is what performs that restoration. The temporary experiment was removed; no such publisher was deployed.

The complete installed client class audit found1026 constants, packet/error identifiers and generic event-consumer tables, but no authoritative skeleton lifecycle publisher. Broader1026 consumers include wisdom/prospecting potions, EnergyVital healing/removal and undead-servant cleanup. These suggest a combat boundary, but do not prove its identity or ordering. The client fight-end enum audit did not establish a connection to1026. A guessed fight-end, turn or resurrection event must not be presented as recovered native behavior.

The general next task is recovery of the original producer, or a separately documented consumer-backed server lifecycle policy with actual KO/restoration/replay and class regression proof. These skeletons should remain pending; the current evidence does not justify silently assigning them to a mission-only exception.

## Evidence and limits

Private machine-readable evidence: `.runtime/monster-pending-activation-20261010/pending-scene-constraints.json`, including source hashes, exact casting criteria, ranges, root IDs and complete required area definitions. Native audits are `native-1026-proof.txt`, `native-1026-instructions.txt` and `native-fight-end-proof.txt`. Installed-script search is `.runtime/monster-remaining-20261010/encounter-client-script-search.json`; its numeric matches were unrelated animations or event IDs, not encounter placement.

The per-case preview evidence is `.runtime/monster-remaining-20261010/validation-certified.json`. Later publication reports must use the final completed receipt for overall totals. This report intentionally makes no deployment claim and does not count partial spell coverage as monster activation.
