# Native emote authority and playback

Research only: no service restart, database mutation, or gameplay handler changes.

## Installed definitions

`ExportNativeEmotes.java` loads native `aKY` definitions, producing `.runtime/local/native-emote-definitions.json`. There are 319 definitions: 295 ordinary (`bkI=1`, `eiV=false`) and 24 targeted (`bkI=2`, `eiV=true`). Native loader `baq` rejects type0, dispatches type1 to `bdu.b`, and type2 to `bdu.c`. All 319 have corresponding `emotes/<id>.lua` in the installed scripts jar. No command contains test/admin/fx; this is an asset audit, not proof that every animation was visually exercised.

**Occupation correction:** `biB.dtg()` is the current `blH` occupation, not mount state. With an existing occupation, the native client allows a new emote only when `occupation.dwr()` is true and both `eiW` and `eiV` are false. This branch does not establish any mount restriction.

Other flags: `eiW` / `cns()` forbids playback during an existing occupation that otherwise allows emotes (`dwr()`), as does targeting flag `eiV`, and `eiX` / `cnt()` controls a local camera behavior. Native `bIw.ezG` is the emote ID directly and its duplicate check calls `bdn.AO`, which reads account knowledge.

## Account knowledge

Account component 10 (`eDS.oUu`, EMOTES) is `fbs`. Payload is `>I protobufLength` followed by protobuf `hI`: repeated field1 messages `hE`, each containing field1 INT32 emote ID. `fbs.a(long,ByteBuffer)` clears and restores its set. Repeated snapshots are idempotent. `bdn` binds this account component; the known collection belongs to the owner account, not peer actor bootstrap.

Learning acknowledgement: `cuF`, opcode12266, body `>iB emoteId,success`. Native `cgN` consumes it and refreshes the emote UI.

## Play and broadcast

Request `cnn`, opcode13498, type3, body `>iq emoteId,targetId`. Default target is -1.

Broadcast `cyN`, opcode12088:

```
>B operation (1=start, 2=stop)
>h occupationType (20=EMOTE)
>q actorId
>I payloadLength
payload
```

Ordinary payload: `>iB emoteId,parameterCount(0)`.

Targeted payload: `>iB emoteId,parameterCount(1)` then `>I keyLength(8)`, UTF8 `targetId`, and `>q targetId`.

Native `chT` occupation20 creates `blU`, calls its real `dX` decoder, then starts it. `blU.bIU` forwards the decoded parameter map to the player. `bjo.a(int,HashMap,boolean)` adds `playerId`, merges the supplied map, and invokes `emotes/<id>.lua`. Targeted installed scripts read the exact variable `targetId`. Stop operation2 clears occupation20.

## Target eligibility

Native `bds` target selector requires a player actor (`bjo`), rejects self, dead (`dsA()`), combat-associated (`dnz()`), existing occupation (`dtM()!=null`), or hidden sprite (`beS.bvX()`). The server additionally must enforce current map and instance membership before publishing a target reference. This implementation should reject combat playback until explicitly supported.

## Executed oracle

`sniffer/java/VerifyEmoteProtocol.java` passed native `fbs` restore twice, inspected real protobuf descriptors, decoded ordinary and targeted data using actual `blU.dX`, decoded `cyN` broadcast, and decoded `cuF` acknowledgement. The probe allocates the occupation without its graphics-dependent constructor and initializes its parameter map; it does not claim to run OpenGL/Lua animations.

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-rift-native-oracle sniffer/java/ExportNativeEmotes.java sniffer/java/VerifyEmoteProtocol.java
java -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' ExportNativeEmotes
java -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' VerifyEmoteProtocol
```

## Titles cross-check

Native `biB.Do(titleId)` delegates to private `dqK()`, which is exactly `bkK.c(fn.pB)`: owned cosmetic category7. `bIs.jiK` is the direct title ID. Therefore titles reuse account cosmetics ownership; they do not require an independent title collection component. Their active appearance field is the existing unsigned-short title field in `pq/tG`.

## Random criterion bounds

Native `GetRandomNumber(2)` parses to `eLb`, whose `d(...)` builds `Range.closedOpen(0, limit)`, removes optional exclusions, then selects with `GS.ne`. The valid results are exactly 0 and 1. The native oracle additionally performed 100 draws and verified this bound.
