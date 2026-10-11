# Repeated native interactive attachment: bounded publisher audit

## Confirmed cause

The current existing capture `2026-10-11T22-24-21.977363Z-7004703e`
contains15 incoming13984 records for each of IDs26842,27142,27143,31675,
and14 incoming12344 records for each. Each object's state hash remains identical.
At22:36:47,48,49UTC,13984 batches are followed immediately by per-object12344.
This is the exact `local_game_server.py::sync_scene_world` publisher fingerprint.
The periodic `publish_environment_scene` publisher emits12344 only and is not
responsible for these creation retries.

`SceneSync.arm` in `maps/world_scene_sync.py` deliberately schedules the entire
overlapping neighborhood every second during an accepted movement and its3s
tail. `sync_scene_world` sends12318 registry positioning, then13984 for every
scheduled batch, then12344 for every record. The repeated attachment is bounded
by movement schedules, not an independently infinite1s timer. Redirects or fresh
walks extend the schedule. Bootstrap `sync_static_world` also sends13984 and has
its own3 bounded retries; the matching recurring13984→12344 pairs specifically
identify movement scene synchronization.

## Original installed-client contract

Existing original-JAR bytecode proves:

| Operation | Native contract |
| --- | --- |
|13984/cwJ/cEX | Calls `bEG.b(id,state)` then `cdE.l(object)` to attach an instance into a partition; repeated attachment reaches duplicate-ID guards |
|12344/cwL/cEY | Looks up the retained instance with `cdE.mL(id)` and calls `bEG.as(state)` plus `aWA`; absent instances are silently ignored |
| Partition load/cdy.a | Registers raw definitions in `bEC` |
| Partition load/cdy.b | Instantiates and attaches only definitions whose `acq.chb` automatic flag is true |
| Partition unload/cdy.ek | Removes that partition's raw definitions through `bEC.dt`; scene residency must not be treated as permanent |

A separate bounded original `ach/aoG/acq` decode of exactly three installed527
chunks,128MiB Java, exit0 in0.041s establishes mixed requirements:

| ID | Partition | Automatic creation | Native type |
| --- | --- | --- | --- |
|26842 |(-14,-5) |false |51 |
|27142 |(-14,-5) |true |52 |
|27143 |(-13,-6) |true |52 |
|31675 |(-13,-5) |false |8 |

Consequently, periodic13984 always duplicates automatic assets after their
loader has attached them, and duplicates nonautomatic assets after a successful
initial creation. Simply deleting every13984 is unsafe: nonautomatic assets need
an initial attachment, while12344 cannot create missing or late-loaded objects.

## Minimum correction boundary, not implemented

Separate attachment from state refresh. Preserve authoritative state12344,
interaction authorization, dynamic door/seat/light state and collision rules.
Automatic assets can receive in-place state retries without recreation.
Nonautomatic assets need generation/partition-scoped creation and safe recovery
when a partition loads late or is unloaded/re-entered. A socket-send ledger alone
is not native registration acknowledgement: suppressing all subsequent creation
attempts based on send success can strand late assets. Do not introduce blanket
client delete/recreate churn; it destroys retained identity and needs separate
native teardown/collision proof.

Minimum affected source is `sync_scene_world`/`sync_static_world` attachment
policy and `SceneSync` residency scheduling; no client changes are required to
fix the proven automatic-asset duplicate path. The broader performance owner
must coordinate this policy before editing shared dispatcher/scheduler code.
No runtime correction or complete safe nonautomatic recovery is claimed here.

## Reproduction and evidence

Read-only reproduction: inspect an existing map527 accepted-walk capture,
reassemble frames with `sniffer/decode-capture.py::extract`, inspect only incoming
13984/12344 bodies, and parse their count/id/length records. Compare IDs and
state hashes at adjacent second deadlines. Existing client console reports the
same four duplicate IDs in the corresponding partitions.

Private evidence: `.runtime/local/interactive-duplicate-audit-20261011/` contains
only target packet metadata, state hashes, summary, original raw-object probe
and provenance. No chat, credentials or token payloads were emitted or saved in
these derived receipts. Original existing captures remain private.

```sh
javac -J-Xmx128m -proc:none -cp 'client/lib/*' -d .runtime/local/interactive-duplicate-audit-20261011 .runtime/local/interactive-duplicate-audit-20261011/VerifyRawTargets.java
java -Xmx128m -Djava.awt.headless=true -cp '.runtime/local/interactive-duplicate-audit-20261011:client/lib/*' VerifyRawTargets
```

This audit performs no game interaction, service operation, live attach, client
modification, database mutation or runtime source edit.
