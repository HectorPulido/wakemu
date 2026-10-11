# Complete native protector placement recovery

The installed native protector definitions and world library yield **101 exact
protector placements across57 maps**, with four additional definitions whose
territories are absent from the installed world registry. This expands the
original placement evidence without guessing conversational breed identities.

`ExportNativeProtectorPositions.java` loads `worlds.lib` through native
`cdH.bla()/dW`, which constructs `cdI` worlds and registers their `bMh`
territories with `fxf`. It then reads all105 native `aMD` definitions and joins
`aMD.ctH()` to `fxf.Zp(territoryId).arM()` for the world/map identity. XYZ comes
from `aMD.ctJ()/ctK()/cki()`, the same fields consumed by `bLU.If` into
`bLO.a(X,Y,Z)`. Definitions are snapshotted inside each loader callback because
the native loader reuses mutable row instances.

Native `bLO.getName` resolves localization category48 by protector ID. The
export uses that exact category for Spanish display names; no name-to-breed
inference is performed.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ExportNativeProtectorPositions.java
java -cp '.runtime/local/classes:client/lib/*' ExportNativeProtectorPositions .runtime/local/native-protector-positions.json
```

Concrete native placements include Otomai protector424 on map1385 `(20,17,1)`
and B. Toven protector303 on map527 `(-219,-46,5)`, appearance19929. These are
protector definition identities, not invented conversational breeds. Original
world publication can bind a protector to its concrete NPC actor through
`wW.aiS.ajf`; native `bje.dso` matches exactly that actor ID. Otomai's captured
binding is proved separately in NATIVE-OTOMAI-PROTECTOR-ACTOR-JOIN-20261011.md.
B. Toven's protector placement alone does not select action798's initial root.

Unresolved territory definitions are protector216 (territory62501),315
(65201),222 (62801), and220 (63101). Their native XYZ and raw definitions remain
in the manifest's `unresolved` collection. They are not assigned guessed maps.

This recovers exact original protector placements and a general route to join
captured actor identities. It does not certify101 conversational breeds or
initial dialogue bindings. No server, client, database or service was changed.
