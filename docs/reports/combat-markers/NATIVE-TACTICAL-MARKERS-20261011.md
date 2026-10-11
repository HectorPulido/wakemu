# Native combat cell reports and tactical markers

Installed-client bytecode establishes the following independent native contracts. No client assets were changed.

| Direction | Opcode/class | Body |
| --- | --- | --- |
| Client request: cell ping | 12543/coNN | `>iih`: x,y,z (10 bytes) |
| Server response: cell ping | 13788/cuT | `>iiihq`: fight ID,x,y,z,sender actor ID (22 bytes) |
| Client request: add marker | 12519/coV | `>iihB`: x,y,z,icon (11 bytes) |
| Client request: remove marker | 12597/coW | Same as add |
| Server response: marker update | 12226/cvj | `>iiihqBB`: fight ID,x,y,z,sender actor ID,icon,added flag (24 bytes) |

The inherited `cuQ` prefix is a signed i32 fight ID. Native outgoing `Nx.a(3,body)` wraps the request in its existing channel3 transport; the table describes the decoded message body, not that transport envelope.

Native `fdk` icon IDs:0 square,1 circle,2 cross,3 heart,4 flower,5 triangle,6 skull,7 moon. `cKt.reportCell` selects internal UI action17805 and temporarily disables its button for5000ms. `addFightMarker` selects18415. These are internal actions, not network opcodes. `dba` maps them to `bvP.REPORT_CELL_MODE` and `ADD_MARKER_MODE`; a subsequent valid scene click sends the corresponding request. The click branch rejects an actor with native property72 `CELL_REPORT_DISABLED`. It does not compare against the current turn actor in that branch.

Native `cjT` displays particle78900 at the reported cell for2000ms and emits a sender-dependent fight report message. It renders before looking up sender identity and performs no team filtering in this handler. Server-side participant, team, spectator, phase and cell-geometry authorization therefore remains necessary; absence of a client check does not prove original server policy.

## Independent wire oracle

`sniffer/java/VerifyCombatTacticalPackets.java` uses the actual installed client request serializers (`coNN`, `coV`, `coW`) and response decoders (`cuT`, `cvj`). Outgoing bodies are compared byte-for-byte with native serializer output; incoming fields are printed from native accessors.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/VerifyCombatTacticalPackets.java
java -cp '.runtime/local/classes:client/lib/*' VerifyCombatTacticalPackets 13788 .runtime/combat-markers-20261011/cell.bin
java -cp '.runtime/local/classes:client/lib/*' VerifyCombatTacticalPackets 12226 .runtime/combat-markers-20261011/marker-7.bin
java -cp '.runtime/local/classes:client/lib/*' VerifyCombatTacticalPackets 12543 .runtime/combat-markers-20261011/request-cell.bin
```

All five opcode smoke cases passed. An additional16/16 native decoder cases passed across all eight icons and both add/remove flags; hashes/results are retained in `.runtime/combat-markers-20261011/native-marker-oracle-results.json`. Disassembly evidence is retained alongside those fixtures. This validates wire layouts, not server integration or gameplay acceptance.
