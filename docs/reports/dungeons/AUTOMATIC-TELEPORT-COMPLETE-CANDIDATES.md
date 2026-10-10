# Native teleport candidate preparation

These configurations remain offline. Ten passed an isolated PostgreSQL lifecycle with three players; the final gate also rejected every forward transport before its room victory. No runtime activation or restart was performed.

The test uses authoritative terminal-fight fixtures with actual spawned native species and levels. It checks reward/progression rollback and replay, party hydration/outbox acknowledgement, native room transports, exterior exit, partial member rejoin, and a fresh instance after completion. It does not simulate or certify boss AI, spells, or official balance.

| Dungeon | Rooms | Preparation |
| --- | ---: | --- |
| Castillo de los Cangwejos | 4 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Mazmorra Arakna | 3 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Mazmorra Crustariscos | 2 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Mazmorra de los Cocodrails Delnilo | 3 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Mazmorra de los Trópikos | 2 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Mazmorra Gerbilinda | 3 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Mazmorra de los Güinos | 2 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Mazmorra Vandalienados | 2 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Torre Helada | 4 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |
| Sliptorium | — | unsupported: No unique free native exterior exit for room 3 |
| Fábrica Buhatrás | 3 | offline_configuration_prepared: PostgreSQL lifecycle passed; awaiting independent validation and readiness review |

## General manual acceptance after a future authorized activation

Create a party with three ordinary players. Enter together through the dungeon native entrance. Confirm every player arrives in the same instance and can see the first group. Try the forward teleporter before defeating the group: it must remain unavailable. Defeat the room, then use the forward teleporter: all active party members must arrive at the exact native next-room destination, with one next group and no early boss. Repeat through the final room. Confirm rewards are awarded once. Use the final native exit, then reenter as the same party: everyone must enter a fresh instance. Also check a nonleader can use `!exitdungeon` and rejoin without moving players still inside.

The candidate configurations and PostgreSQL report are linked from `AUTOMATIC-TELEPORT-COMPLETE-CANDIDATES.json` and `AUTOMATIC-TELEPORT-PG-LIFECYCLE-ECONOMY.json`. Sliptorium remains withheld until its final exterior exit is proved.
