# Passport status review — 2026-10-09

## Status

Open: Hector reports an Amaknian passport. This review does not establish the
root cause and does not change server or client behavior. It identifies an
incorrect acceptance assertion in earlier reports and verifies a real recent
bootstrap independently of source-only serializer tests.

## Deployed implementation

At inspection time the single world container was healthy and ran
`wakemu-world:performance-20261009-r60`, rather than the previously documented
r59. Reading `/app/wakfu_server/wire.py` inside the container confirmed that
`minimal_entity()` sets `NATION_ID` and `CHARACTER_LIST_NATION_ID` to signed
int32 zero, resets `NATION_SYNCHRO`, and includes `PASSEPORT_INFO` among the
sections replaced with native defaults. Missing deployment of these changes
alone does not explain the latest report.

## Actual visible passport binding

Offline `javap -c -p` inspection of the installed `client/lib/wakfu-client.jar`
establishes the following path:

1. `cIt` registers `passportDialog` with compiled UI class `cTg`.
2. `cTg` binds the visible citizenship text to property `localPlayer`, field
   `nation/nationName`; its stamp uses `nation/passportStampIconUrl` and its
   text color uses `nation/nationColor`.
3. `bVq.getFieldValue("nationName")` calls `aTF.a(39, bVr.Xt(), [])`.
4. The Spanish locale contains `content.39.0=Ninguna nación` and
   `content.39.30=Nación de Amakna`.

The previous assertion targeting `pvpLadderEntry.nationId` is insufficient for
the visible passport label. `ddU` does initialize that ranking model through
`bMO`, but the citizenship label has the separate binding above. Similarly,
`nation.short.0=Neutral` belongs to another localization surface; the expected
passport citizenship label for zero is **Ninguna nación**.

The native neutral nation is valid: `frk` initializes its static `sZj` instance
with ID zero and registers it in `frp`. `bjG.zm()` reads `qZ.Wi`, resolves it via
`frp.XH(id)`, and applies the nation to the actor. No automatic zero-to-Amakna
conversion was demonstrated by these consumers.

## Read-only evidence from the current local client

The existing `.runtime/local/inspector.json` points to capture
`2026-10-10T00-43-38.678175Z-b0b134a1`. This UTC timestamp is still October 9 in
Bogota. Its credentials were not printed or copied into this report.

Existing inspector requests, without installing or attaching instrumentation:

```sh
python3 client-tools/diagnostics/inspect-client.py --local position
python3 client-tools/diagnostics/inspect-client.py --local actors
```

They identify the local player as **Prueba Oficios**, actor ID **4**. The actor
list also contains **Npers**, ID **6**. These endpoints expose identity and
position, not the retained nation model.

Using the existing offline `extract()` function in `sniffer/decode-capture.py`
on that capture found login carriers `23548`, `12666`, and `13713` on two world
entries. The last `12666` arrived at `2026-10-10T00:45:51.904542Z`. Its first
length-prefixed entity block was extracted into a private temporary file and
parsed by the already compiled native probe:

```sh
java -cp '.runtime/local/classes:client/lib/*' OfflineEntityLayout /tmp/wakemu-passport-session-entity.bin
```

Relevant native output:

```text
Format FOR_LOCAL_CHARACTER_INFORMATION
ID qt 1:9
  Vc=4
NATION_ID qZ 1356:1360
  Wi=0
PASSEPORT_INFO rr 1364:1365
  Xa=false
Remaining 0
```

This verifies zero in an actual received bootstrap for actor 4, with complete
native entity consumption. It is stronger than testing a regenerated fixture,
but does not prove the nation retained by the UI after every later message.
The client console also records a missing `nation/flags/0.tga` asset and earlier
disconnect messages for nation zero. Those logs corroborate use of zero in
some client paths, without identifying the reported passport label itself.

## Exact remaining limitation and next verification

The existing `CaptureAgent` inspector has specific endpoints for position,
actors, equipment, movement, and combat. It has no generic expression or
property-model inspection endpoint. Its default `/state` response is an AWT
component tree, not the game's `localPlayer.nation` model. Network capture
objects are intentionally not reflected. The world JSONL event log records
opcodes and sizes and cannot independently establish their body values.

No client input, native replay, agent attachment, service restart, or live
state mutation was performed. The current read-only tools cannot directly
prove `localPlayer.nation.nationId`, its `nationName`, or the visible stamp in
the affected passport instance. Therefore no serializer patch is justified
from this evidence alone.

The next discriminating check is to correlate the affected character and
session with the actual visible passport and retained nation model:

- If the model is 30, locate the carrier or refresh that changes it after the
  verified neutral bootstrap.
- If the model is zero but Amakna remains visible, investigate stale binding,
  refresh, or the exact UI surface being observed.
- Acceptance requires the visible citizenship label **Ninguna nación**, the
  matching `localPlayer.nation` state, and persistence after selecting the
  character again and reconnecting. The ranking model can be checked
  separately and must not substitute for this assertion.

Territorial ownership and future selectable/persisted citizenship remain
separate work. Nothing in this review changes territorial nations.
