# Duel client timeline, 2026-10-10 10:02 local

The two preserved client captures distinguish server computation, network arrival, and client presentation. Times below use America/Bogota (UTC minus five). No client or server behavior was changed during this investigation.

## Evidence

Private captures are `.runtime/local/captures/2026-10-10T14-54-22.887154Z-bca6f6ff` and `.runtime/local/captures/2026-10-10T14-54-22.883080Z-d9da17be`. Decode with `sniffer/decode-capture.py`; presentation logs are in `.runtime/local/logs/client-console.log`. Captures contain private payloads and must not be committed.

| Event | Client bca6f6ff | Client d9da17be |
| --- | --- | --- |
| Initial placement/bootstrap received | 10:02:15.027 | 10:02:15.078 |
| Placement move request, opcode 12806 | None | 10:02:41.863 |
| Updated placement roster received | 10:02:42.093 | 10:02:42.074 |
| Placement end, opcode 12233 | 10:03:18.823 | 10:03:18.834 |
| Timeline recovery, opcode 12053 | 10:03:19.074 | 10:03:18.973 |
| Turn acknowledgment sent | 10:03:34.968 | 10:03:35.236 |

The bootstrap is 11,181 bytes and contains a 39 by 39 topology, origin (-224, -65), height range 0 through 4. The server sends the same normal placement sequence to each owner: 13652, 12847, 13684, 13026. Two client `CREATION DU COMBAT` entries are consistent with two clients sharing the console log; they do not establish duplicate creation within one client.

Client creation logs occur at 10:02:16.409 and 10:02:17.884. The final actor registration appears at 10:02:24.264, up to 9.2 seconds after bootstrap arrival. The console is then quiet until effect initialization at 10:03:18.923. However, a placement move leaves the second client at 10:02:41.863 and receives a roster update 212 ms later. Therefore the quiet console interval is not proof of an uninterrupted 54-second AWT freeze.

`PROCESSING FIGHT RECOVERY` appears at 10:03:25.505 and 10:03:29.051, roughly 6.4 to 10.1 seconds after the recovery packets arrive. Native `buH.dZ(byte[])` logs this message when entering recovery processing; this text alone is not an exception or a recovery request. It calls `as(byte[])`, then starts its timeline controller. This is a measurable client presentation delay in addition to the separately measured server preparation delay.

The unhandled outgoing messages 13003 and 12010 at 10:14 are language negotiation according to `protocol_codec.py`, not surrender requests. No surrender request was identified in the inspected interval.

## Recorder assessment

`CaptureAgent.append` synchronously serializes JSON and flushes its writer for every recorded Netty boundary. Byte buffers are copied and base64 encoded, potentially at several stages. This design can introduce overhead, but the current evidence does not establish it as the cause of this incident.

Between 10:02 and 10:04 the captures contain 552 and 542 events, with about 188 KB of copied payload bytes each. Adjacent matching inbound `aTm#0` to tail-stage observations have maximum gaps of 19.0 and 23.1 ms, with summed gaps of 238.6 and 92.2 ms across 193 and 192 pairs. These stage gaps are not complete callback-duration measurements, and do not measure AWT work or every flush.

Both clients were closed at approximately 10:24; no live client AWT stack was available at 10:25. The remaining Java processes were native diagnostic probes. A recurrence should capture a client thread dump while it is visibly blocked, then correlate that with packet arrival and AWT processing. Disabling recording or changing the protocol without this evidence would be speculative.

## Conclusion

There is evidence for both cold server geometry preparation and delayed client presentation. There is no evidence here of a 60-second inbound transport blockage, and no demonstrated malformed duel bootstrap. Keep these layers separate when validating a fix. In particular, shortening server preparation does not establish that the client presentation delay has been fixed.

## Native placement relocation audit

Native opcode 13652 is `cvq`, handled by `cla`. Its handler collects current actors, enqueues an `aUE` presentation action when necessary, enqueues an `aUs` relocation action with the immediate flag, updates `buU` placement positions, and starts the existing fight action queue. It does not instantiate `aVK` or recreate `buH`. The full roster update after a placement move is therefore not evidence that the server recreated the fight. The existing four-byte opcode 13026 is the distinct native placement-start notification.

## Live follow-up at 10:46–10:50

The new client PID 75063 was available during the later Osamodas report. External `jcmd` attachment failed. Read-only SIGQUIT thread dumps succeeded and are retained privately as `client-sigquit-20261010-1049.txt` and `client-stack-20261010-1050-*.txt` under diagnostics. Three samples show different AWT rendering locations: CGL layer readiness, native map rendering `fQq.adf`, and `glFinish`. The animator waits for AWT, as expected when rendering runs on AWT. No CaptureAgent lock or Java deadlock was observed. These sparse samples do not establish a prolonged graphics-driver blockage.

The client capture `2026-10-10T15-32-48.690776Z-b793a5ce` provides more specific combat evidence:

- At 10:46:09.524, an end-turn request receives an ACK response cycle completed by the client at 10:46:09.627. Another end-turn request leaves at 10:46:10.815, but the following ACK leaves at 10:46:40.519, about 29.7 seconds later. This 30-second pattern also occurs at 10:46:53.703 through 10:47:23.426.
- Jamajam actor 115 casts Nova at 10:48:49.442. Effects and death presentation arrive at 10:48:49.691, and the client logs death at 10:48:51.109 and 10:48:51.713.
- Turn-end presentation 12502 arrives at 10:48:52.918. The client sends ACK 13510 for turn 23 at 10:48:52.972, then sends end-turn 12403 for actor 115, round 8, at 10:48:55.510.
- No subsequent combat delivery appears before the world reload around 10:51. Exterior world movement 13852 continues to arrive approximately every five seconds meanwhile. This follow-up needs server-side dead-actor/turn synchronization investigation; the continuing transport traffic and prompt ACK distinguish it from an entirely frozen client connection.
