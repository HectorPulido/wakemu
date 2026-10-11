# Combat tactical signaling

Source: `server/wakfu_server/combat/combat_tactical_markers.py`. The dispatcher integration receives the three native requests through the shared participant registry and rehydrates team icons after native12847 constructor batches. No client, spell, turn primitive or service change is needed.

## Installed native contract

The installed `client/lib/wakfu-client.jar` defines these big-endian bodies after the ordinary channel3 envelope:

| Request | Native class | Body | Reply | Native class | Body |
| --- | --- | --- | --- | --- | --- |
|12543 cell report | coNN | x:i32,y:i32,z:i16 |13788 | cuT | fight:i32,x:i32,y:i32,z:i16,sender:i64 |
|12519 add icon | coV | x:i32,y:i32,z:i16,icon:u8 |12226 | cvj | fight:i32,x:i32,y:i32,z:i16,sender:i64,icon:u8,added:u8 |
|12597 remove icon | coW | x:i32,y:i32,z:i16,icon:u8 |12226 | cvj | same, with added=0 |

`fdk` defines square0, circle1, cross2, heart3, flower4, triangle5, skull6 and moon7. `ckh.a(cvj)` first removes the existing icon of that type, then adds its new position only when added=true. Therefore each team has at most eight retained icons, with replacement by type. `cjT.a(cuT)` renders native particle78900 for2000ms and native fight chat. Neither receiver performs a team filter; server routing must enforce privacy.

The native `dba` screen-picking branch rejects actor property72 (`CELL_REPORT_DISABLED`) and requires a valid picked screen element. It does not require the current actor's turn or positive HP. `cKt.reportCell` applies a5000ms UI cooldown. The server preserves those request guards, accepts placement/active phases and applies the cooldown per selected owned actor. Exact `(x,y,z)` must belong to the authoritative fight terrain. Team-only delivery is explicit server policy, preventing opponents or spectators from receiving tactical information.

## Authority and replay

`handle(registry, session, fight_id, actor_id, opcode, body)` uses a trusted caller-selected actor; requests contain no actor or fight identity. Existing live-generation membership and shared fight locking fence all operations. Main characters and heroes require explicit controlled actor ownership. Withdrawn, foreign, stale and wrong-location sessions are rejected.

The existing ordered participant outboxes carry team-private replies. No socket writes, resource changes, spell execution, turn transition or ACK release occurs in this module. Icon metadata and ping timestamps are ordinary JSON-safe fight fields and follow the existing checkpoint/deepcopy path. Identical adds and repeated removes are no-ops. A delayed remove at an old location cannot erase a newer location. Persistent icons replay to authenticated own-team late join/reconnect; transient pings do not replay.

`snapshots(registry, session, fight_id)` requires committed, connected membership. Call it after registry join/adoption, or from an already authenticated reconnect hook, before returning to ordinary gameplay. It returns only own-team native12226 packets.

## Manual system acceptance

1. Start an ordinary multiplayer fight with a main character, an owned hero and a second allied account. If testing JcJ, include the opposing account as a visibility observer.
2. During placement, use the native cell indicator toolbar action or `R R`, then click a terrain cell. Both allied clients must show the same short native cell indicator and fight message. The opponent must not receive it.
3. During another actor's turn, repeat with the owned hero selected. The sender must be that hero, with no AP/MP consumption or turn change. The native five-second cooldown must prevent rapid repeated pings.
4. Add all eight native icon types. Allies must see each icon at the selected cell. Move one icon type to another cell: exactly one instance of that icon remains. Remove it through the native remove tool: it disappears for both allies.
5. Reconnect an allied account while the fight is still live. Existing own-team icons must reappear; old transient pings must not replay. Opposing markers must remain private.
6. Finish the fight and start a different fight. No icon or cooldown state from the previous fight may leak into the new encounter. Ordinary movement, spells and end-turn/ACK behavior must continue unchanged.

Independent installed-client wire oracle: `sniffer/java/VerifyCombatTacticalPackets.java`; fixtures and bytecode evidence are private under `.runtime/combat-markers-20261011/` and `.runtime/local/tactical-marker-*.javap`. Automated results are recorded separately by the verifier; no graphical acceptance is claimed here.

## Automated verification

Delivery includes the sender's client and every connected allied account. Owned heroes share their account's socket, so each account receives one ordered event, with the selected hero's actor ID in the native payload. Enemy accounts and withdrawn participants are excluded by the server's team filter. Spectators cannot request or replay these packets; the dispatcher spectator allowlist also excludes `13788` and `12226`.

This visibility rule is enforced by the server. The installed native `cjT` cell-report consumer renders the indicator and chat message directly, without its own team filter; sending the packet to an enemy or spectator would expose it. Native `cvj`/`12226` carries all eight icon IDs, add/remove state, sender and fight identity. The independent native oracle validates every icon in both directions of state change. Current registry regressions cover sender plus ally delivery, enemy exclusion, hero attribution, all eight persistent icons, replacement-generation replay and rejection of a nonparticipant spectator. Transient cell pings are never replayed; reconnecting allies receive their team's current persistent icons.

Luna passed all7 tactical registry tests and all50 existing shared-combat tests with unchanged selected source/test fingerprints. The independent Java oracle accepted actual handler-generated13788 replies and12226 add/remove replies for all8icons, and byte-compared all3request bodies against the installed native serializers. Evidence: `.runtime/local/verification-tactical-markers-20261011/tests.log`, `native-oracle.log`, `fingerprints.json` and `packets/`. The dispatcher integration gate passed all4 new runtime/AST regressions, the existing spectator/shared suites, and the4-case external-marker module after updating its NPC-scene dependency fixture. Stable source evidence: `.runtime/local/verification-tactical-dispatch-20261011/tests.log` and `external-marker-r2.log`. Graphical acceptance and deployment remain coordinator-owned checks.

The focused expanded registry gate passed **8/8**, including all-icon sender/ally delivery, replacement-generation replay and spectator rejection, with stable fingerprints (Fast Luna, 2026-10-11). Prior native packet oracle coverage remains unchanged.
