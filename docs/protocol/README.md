# Protocol and server internals

[Main wiki](../README.md)

This section explains how Wakemu communicates with the **Wakfu 1.93.1+79** client and turns binary requests into game behavior. It documents this emulator's implementation, not Ankama's private server architecture or a complete specification of every Wakfu message.

You do not need to understand every byte before reading. Start with the connection journey, then follow one request through decoding, validation, execution, and delivery.

## Reading order

| Guide | Main question |
| --- | --- |
| [Connections and login](connections-and-login.md) | Which connections exist, and how does a player enter the world? |
| [Binary messages](binary-messages.md) | How are frames, numbers, strings, paths, and nested bodies encoded? |
| [Request lifecycle](request-lifecycle.md) | What happens between receiving a packet and changing game state? |
| [World synchronization](world-synchronization.md) | How does the client learn about characters, maps, and interactive objects? |
| [Combat synchronization](combat-synchronization.md) | How do spell transactions, action sequences, and acknowledgements fit together? |
| [Investigation and testing](investigation-and-testing.md) | How can you understand an unfamiliar packet without guessing? |

## Four layers to keep separate

1. **Transport:** TCP and TLS carry bytes between endpoints.
2. **Framing:** a length and header identify each message inside the byte stream.
3. **Serialization:** the body describes fields, nested entities, or protocol-specific envelopes.
4. **Gameplay:** the server decides whether the requested action is legal and what should happen.

A valid frame may contain an invalid body. A correctly decoded body may request an illegal action. A successful state change may still look broken if the client receives the wrong sequence of updates. Most protocol debugging is about finding which of those boundaries failed.

## Scope and evidence

The guides link to the relevant source modules rather than reproducing internal research logs. `agents_docs/` retains the detailed investigations. Names and opcode meanings below are limited to what the implementation establishes; unused fields and incomplete behaviors are called out rather than assigned invented meanings.

The source checkout can change before images are rebuilt. The current bootstrap loader reads verified records from PostgreSQL; older builds used a private capture-file mount. Source behavior and deployed behavior must be checked separately.
