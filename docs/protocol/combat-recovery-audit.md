# Own combat timeline recovery

Client `coX` opcode13332 requests recovery using exactly an i32 fight ID. `buH.dLS` pauses the native timeline before sending it. Server `cvn` opcode12053 contains i32fightID, i16 envelope length, and a native `fg` fields envelope. `cjv` clears pending action queues and invokes `buH.dZ`, whose field0 reader loads the SU timeline and restarts its clock.

`combat_recovery.py` serializes authoritative active-fight data. The SU header is i16 round, i32 started-turn counter, byteON_FIGHTER_TURN, i64 deadline. Both SX arrays use the authoritative surviving actor order: the first governs the current round, the second the next round. The cursor points at the current fighter. SY entries retain insertion-round zero for the fixed roster. Dead fighters are excluded from SX but retained in fem removal records with their original timeline position. feN entries represent bonus-point state, not actor turn counts; the local no-offers policy starts these at zero.

`RuntimeMessages.recover(account_id, request_body, now_ms=...)` validates account/fight and packet serialization before replacing stale pending ACK presentation state. It sends12053, optional12873 current statistics, and13482 current-turn notification. It preserves the authoritative turn counter, so subsequent13510 ACKs still require the exact sequence number. PRE_TURN is deliberately omitted because recovered SU already is ON_FIGHTER_TURN.

Validation: `VerifyCombatRecovery.java` decodes own bytes with actual cvn, fg, Tc and feu classes. A two-NPC fixture after one death retains round2/turn3, current fighter-201, excludes dead-200 from the live roster, preserves its removal position2, and consumes all bytes. Python tests also verify ownership rejection leaves the existing barrier intact.

## Intermittent death race, still requiring runtime verification

Native `aTS` state2 schedules actual death removal after AnimMort, but returns at most250ms to the action sequencer. TURN_END does not use the native pending-death barrier used by fight completion. This can let the next turn advance before the dead fighter is removed. Wonejo native117402504.anm has both death variants lasting2280ms.

Failed fight190982470 sent TURN_END2.999s after the death packet, crossed a round boundary immediately, and requested recovery twice after the next NPC turn began. Successful fight72355856 waited5.279s before TURN_END and began the next NPC without crossing that boundary. User also won with Uginak using the same running code. This evidence supports an intermittent timing/order problem; it does not establish a repaired runtime. Recovery provides the native resynchronization path rather than normalizing mismatched ACKs.

Scope: fixed initial roster, stable initiative, no summons, timeline insertion/delay, resurrection, or bonus offers. Resynchronizing clients through the new API has not yet been tested in the GUI. No service was restarted for this change.
