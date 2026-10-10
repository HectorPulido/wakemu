# Controlled summon turn latency, 2026-10-10 10:46 America/Bogota

## Confirmed server timeline

World r71, boot `bd6adff9720748b38a082c5e44306af8`, fight 159, owner actor 19, controlled summon 115, enemy -1125899906869632.

At 15:46:09.553 UTC the owner ended its turn. The request completed in 78 ms, advancing the authoritative current actor to summon 115, turn 14. Client ACK arrived at 09.657; it completed in 22 ms and released the summon turn. Runtime `awaiting_ack` was null. At 10.852 the client tried ending the summon turn; the server rejected it as `Stale turn identifier` in 48 ms. The next turn ACK arrived at 40.557, after the controlled turn expired. AI then used approximately 3.10 seconds. Thus the approximately 30-second delay was an unfinishable controlled turn, not a 30-second spell, AI calculation, or blocked socket.

The same pattern recurred at 15:45 and 15:47. Player spell requests in this window completed in 142–318 ms. The controlled summon had zero AP but remained alive; a player must still be able to end its turn immediately.

## Protocol counter correction and native evidence

The first attempted correction used native SY progress plus one. **That formula was incorrect**: it rejected the first turn of a newly created Jamjam and the owner's turn after a native recovery. Its original 14 passing tests encoded the incorrect assumption and did not establish native protocol correctness.

Actual client bytecode establishes the precise wire source. `buH.aX(big)` obtains the actor identity, then invokes `dLW().bvY.bhN()` and constructs `cpb(long, short)`. `cpb.d()` returns 12403 and its serializer writes `>qh`. In inherited `SU.bhN()`, the returned short is `brM`, the **global native timeline round**; `SU.bhP()` increments that round. Neither per-actor logical turn count nor native SY progress is this field.

Client capture confirms three discriminating cases:

| Packet body | Actor | Native round | Logical actor turns | SY progress | Wire short |
|---|---:|---:|---:|---:|---:|
| `00000000000000610001` | 97, first Jamjam turn in fight 164 | 1 | 1 | 1 | 1 |
| `00000000000000730002` | 115, later-born Jamjam in fight 159 | 2 | 1 | 2 | 2 |
| `00000000000000130002` | 19, after fight 164 recovery | 2 | 3 | 2 | 2 |

At 16:13:58 UTC, first Jamjam turn 97 sent short 1; the incorrect SY+1 implementation expected 2. At 16:15:00 UTC, owner 19 sent short 2 after recovery; SY+1 expected 3. Both were rejected immediately and waited for turn expiration, reproducing the user's continued lag.

The corrected `current_wire_turn` returns only the validated global native round. Runtime TURN_END validates that exact counter after current-owner validation, then passes the unchanged logical actor counter into the FSM. Deadline expiration uses the same wire mapping. Spell per-turn accounting retains its logical actor counter. Opcode 12403 is the only wire actor-turn consumer; movement and spell requests use their separate global turn identity. No union of counters or stale tolerance is introduced.

The regression suite now uses the actual captured raw packet bodies above, deliberately disagreeing logical/SY counters, exact other-round rejection, foreign-owner rejection, late insertion before/after current, recovery, and timeout. Combined validation is assigned to the test agent. Private bytecode evidence: `.runtime/local/diagnostics/buH-endturn.txt`, `cpb-endturn.txt`, and `.runtime/local/rift-review/SU.javap`. This report does not claim the corrected implementation has been deployed.

## Separate current-summon death failure

At 15:48:49.721 the summon cast completed after killing the current summon, advancing to enemy turn 24 with no pending ACK. Enemy processing advanced to owner turn 25 with runtime awaiting ACK 24. Client ACK was rejected at 15:48:53.002 as `Invalid/stale shared turn ACK`; its subsequent end-turn command still addressed dead actor 115 and was rejected. No further combat request arrived before abandon at 15:50:46. This requires a separate accepted-transition death/ACK closure fix, owned by the lifecycle audit agent; accepting arbitrary stale ACKs would hide the protocol error and weaken synchronization.

Private server events and continuous profiles are preserved under `.runtime/local/diagnostics/osamodas-turn-1046/`.
