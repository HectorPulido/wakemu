# Investigating and testing the protocol

[Protocol home](README.md) · Related: [Contributing](../contributing.md)

## Start with one observable behavior

Choose a reproducible action: select a character, walk one step, use a transport, or cast one spell. Record the starting state, action, expected result, and actual result. Avoid inferring an entire subsystem from a single successful animation.

Use two independent kinds of evidence where possible: the observed exchange and the relevant serializer or decoder. A packet length alone cannot tell you whether a field is an item reference, an instance UID, or an unrelated counter.

## Follow the layers

1. **Find the connection.** Distinguish launcher RPC, dispatcher, world, and intergame traffic.
2. **Establish direction.** Client capture `out` corresponds to server log `in`.
3. **Check framing.** Confirm the total length, direction-specific header, opcode, and body boundary.
4. **Decode conservatively.** Verify widths, signedness, counts, optional branches, and complete body consumption.
5. **Find the handler.** Search the current dispatcher and domain module rather than assuming a familiar name means a complete implementation.
6. **Check authority.** Inspect account generation, character ownership, fight phase, geometry, and current resources.
7. **Follow publication.** Confirm the expected connection received registration, updates, flushes, and acknowledgements in order.

For example, a rejected walk might originate in malformed step bytes, a stale starting position, a locked dungeon door, or a map partition that never received its object state. Each requires a different fix.

## Tools already in the project

```sh
bash client-tools/client.sh check
bash client-tools/client.sh inspect --profile main state
docker compose logs --tail=100 world ai ecology
bash sniffer/build-capture-agent.sh
```

The first command checks launcher compilation and network isolation. Inspection describes a running client's observed state. Service logs describe server-side decisions. Building the capture agent prepares instrumentation; it does not itself create a game session or validate a feature.

`sniffer/decode-session.sh` orchestrates offline catalog construction, capture decoding, native encoder checks, and summaries. It needs a compatible supplied client, JDK, and a prepared capture directory. It is an advanced research workflow, not a required game-server startup step. Keep its generated artifacts and session data private.

World's detailed diagnostic stream is `.runtime/local/logs/game-server.jsonl`. Correlate connection IDs, service, opcode, and domain events. Ordinary packet log entries record metadata; they are not necessarily full captured bodies. Never copy authentication tokens into a bug report.

## Build a useful regression

A decoder test should cover a verified valid body and meaningful failures such as truncation, invalid counts, or unexpected trailing bytes. Prefer small synthetic bodies over publishing an entire session.

A behavior test should go beyond decoding: ensure a foreign actor cannot move, an unsupported later effect cannot leave earlier costs committed, or a stale acknowledgement cannot advance a replacement session's fight.

For a lightweight offline check of the codec:

```sh
PYTHONPATH=server python3 -m unittest discover -s server/tests -p 'test_protocol_codec.py'
```

Use an environment with the project's dependencies installed. Database integration tests require an explicitly isolated test database. Passing a codec test proves that layout handling works for those cases; it does not establish that all client versions or gameplay flows are supported.

## Name uncertainty

If a field's meaning is unresolved, retain its verified width and neutral name. If two client paths use different serializers, document the active caller rather than selecting the tidier-looking layout. Fixing the shared rule is preferable to patching one map or spell until a trace looks right.

Sources: [codec tests](../../server/tests/test_protocol_codec.py), [decoder implementation](../../server/protocol_codec.py), [offline pipeline](../../sniffer/decode-session.sh), [client diagnostics](../../client-tools/README.md).
