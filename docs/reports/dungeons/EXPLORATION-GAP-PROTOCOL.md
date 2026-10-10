# Exploration gaps, climbing, clouds and swimming

## Native authority

These abilities affect ordinary native terrain pathfinding. They are not a `Door` or a generic interactive-element action, and require no new 12870 interaction handler.

| World property | Native actor check | Pathfinder flag | Native terrain test |
|---|---|---|---|
| 85, `eHQ.pTH` | `beS.dgu()` → `bjo.i(pTH)` | `Sp.bpJ` | `Vy.bmg()` = `bLF & 8`, with landing `bmj()` = `bLF & 16` |
| 105, `eHQ.pUa` | `beS.dgv()` → `bjo.i(pUa)` | `Sp.bpK` | `Vy.bmh()` = `bLF & 64` |
| 117, `eHQ.pUm` | `beS.dgw()` → `bjo.i(pUm)` | `Sp.bpL` | `Vy.bmi()` = `bLF & 128` |
| 118, `eHQ.pUn` | `beS.dgx()` → `bjo.i(pUn)` | `Sp.bpM` | `Sn.a(Vy,Vy,boolean)` tests `bmk()` = `bLF & 256` and `bml()` = `bLF & 512` |

`beO.i(boolean,boolean)` assigns these four actor checks to the corresponding `Sp` flags. `Sn` evaluates them during native path expansion. Giving the artifact item alone is insufficient: the source items have no implicit effects granting these properties. The exploration inventory/bootstrap implementation must supply the appropriate world properties separately. No combat properties are implied.

## Existing wire and dispatcher

`beO.dgy()` creates `cnl`, sets the packed `aAT` route and native movement mode, and submits it through the normal connection. `cnl.d()` is **13331**. Its body is an i32 mode, i32 x, i32 y, i16 z, u8 step count and packed step bytes. Each step preserves direction and signed five-bit height delta.

The existing loaded-world 13331 branch already validates the route against its previously approved origin, saves the resulting position and relays the exact packed route as **13852**, replacing the mode prefix with the actor identity. The sender animates its route locally and does not receive an echoed route. Invalid origins receive **13530**, the authoritative position correction. Jump/climb paths therefore use existing movement handling; routing them through unsupported interactive-element actions would implement the wrong protocol.

The installed `cnl` encoder successfully reproduced an exact 13331 body containing native Tofu stair deltas `-4` and `-2` (`VerifyCapturedEncoders`: one match, zero unresolved skips). This is a synthetic wire fixture checked against the real installed encoder, not an official gameplay capture of an artifact gap.

## Distinguish ordinary stairs from artifact abilities

Tofu map 1087 contains no surfaces with jump-source, landing, climb or cloud flags (8, 16, 64, 128). Its four-height entrance stair transition is ordinary player movement capacity, documented in [TOFU-NATIVE-FLOW.md](TOFU-NATIVE-FLOW.md). Granting exploration secrets should unlock flagged paths elsewhere; it does not replace the separate player/combat movement-profile distinction found in Tofu.

## Reproduce native proof

```sh
javap -classpath client/lib/wakfu-client.jar -c -p beS
javap -classpath client/lib/wakfu-client.jar -c -p beO
javap -classpath client/lib/wakfu-client.jar -c -p Sn
javap -classpath client/lib/wakfu-client.jar -c -p Vy
javap -classpath client/lib/wakfu-client.jar -c -p cnl
```

Relevant methods are listed above. Regression tests in `server/tests/test_exploration_movement_wire.py` cover stair height preservation, signed climb/descent, approved-origin enforcement and malformed packed paths. Client acceptance remains necessary after the future complete build/bootstrap deployment; no running services were changed for this review.

## Exact manual jump location in Astrub

A native artifact-gated jump is available on ordinary outdoor map **527 (Astrub)**. The all-chunk native exporter verified 521 chunks, 65,283 walkable cells and 231,685 directed edges. This concrete crossing is independent of any dungeon gate or ordinary height-four stair.

1. Outside combat, enter `!teleport 527 -212 -2 0`.
2. Click the solid landing across the short gap, two cells toward the lower left: native destination `(-212,0,0)`, across `(-212,-1,0)`.
3. The character should jump across. Enter `!position`; the destination should be map 527, x -212, y 0, z 0.
4. Click the original landing to return; both directions are native-valid.

The exact terrain masks are 16 at the starting landing, 11 at the gap (includes jump bit 8), and 18 at the destination (includes landing bit 16). The installed `Sn` pathfinder rejects entry into the gap unless `Sp.bpJ` is enabled by world property **85**; landing-to-gap and gap-to-landing native `Sm(6,0,4,true)` edges are present in both directions. [EXPLORATION-MANUAL-JUMP.json](EXPLORATION-MANUAL-JUMP.json) preserves the exact decoded surfaces, edges and client/topology hashes. These are verified offline facts; the visible avatar animation still needs Hector's acceptance after the prepared secrets changes are deployed.
