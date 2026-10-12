# Binary messages

[Protocol home](README.md) · Next: [Request lifecycle](request-lifecycle.md)

## TCP is a byte stream

One socket read is not necessarily one packet. A header can arrive in pieces, and several complete messages can arrive together. Wakemu's `receive()` loops until it has the requested byte count; an empty read means the peer disconnected.

TLS wraps that stream. The application frame layouts below describe the decrypted bytes seen by the game handlers, not raw TLS records.

## The two game frame layouts

All fixed-width header integers below are big-endian. The length includes its own four bytes.

| Direction | Fields in order | Minimum size |
| --- | --- | --- |
| Client → server | `length:u32`, `route:u8`, `opcode:u16`, body | 7 bytes |
| Server → client | `length:u32`, `opcode:u16`, body | 6 bytes |

The route byte is present only on incoming game requests. The session loop records it, but its main dispatch uses the listener service, opcode, and current session state. It should not be treated as an authorization check or copied into replies.

Incoming lengths must be between **7 and 327670**. The batch sender validates opcode range and limits body size to `327670 - 6`. The single-packet sender constructs the same outgoing header but does not duplicate all batch validation.

For example, a client `574` request with route zero and no body is:

```text
00 00 00 07 | 00 | 02 3e
length = 7   route opcode = 574
```

Route zero here is an illustration of framing, not a claim that every message uses it.

## Numbers and strings

The Python `Reader` uses `struct` with the `>` prefix. Common format letters are:

| Format | Meaning |
| --- | --- |
| `B` / `b` | Unsigned / signed 8-bit integer. |
| `H` / `h` | Unsigned / signed 16-bit integer. |
| `I` / `i` | Unsigned / signed 32-bit integer. |
| `q` | Signed 64-bit integer, commonly used for entity IDs. |

Booleans commonly occupy one byte. Strings are UTF-8 bytes preceded by a length, but that length is not universally the same width. `Reader.text()` defaults to `u32`; some names use `u8`, and chat text commonly uses `u16`. The prefix counts encoded bytes, not displayed characters.

`take()` rejects negative or truncated lengths. `finish()` rejects trailing undecoded bytes. These checks matter: a decoder that reads a plausible prefix and ignores the rest can hide a mistaken layout.

## Example: world movement (`13331`)

The request body contains a movement mode (`i32`), starting coordinates (`x:i32`, `y:i32`, `z:i16`), a step count (`u8`), and one byte per step.

Each step packs two values into one byte:

```text
bits 7..5: direction, 0 through 7
bits 4..0: signed height delta, -16 through 15
```

The decoder calculates `direction = byte >> 5`. For height, it takes the lower five bits and subtracts 32 when bit 4 is set. Direction comes from the eight-entry `DIRECTIONS` table, which supplies horizontal coordinate deltas. Summing the deltas produces a requested endpoint; gameplay validation still decides whether the path is allowed.

Combat movement (`12161`) uses a different body: actor ID (`i64`) followed by coordinate triples of ten bytes each. Reusing the world movement decoder would corrupt the request.

## Bodies are not all fixed-width

Some messages embed protobuf fields. Others contain nested entity blobs, optional branches, explicit padding, or compressed data. For example, `12870` includes two trailing bytes in its verified layout, and the market-price decoder for `14303` uses bounded zlib decompression. Neither fact implies that all messages use padding or compression.

Intergame has another frame header: `length:u32`, `kind:u8`, payload. Its length is bounded by 1 MiB, and control kinds carry no payload. It has no game opcode field; message identity lives inside the protobuf envelope.

## Direction names can mislead

In `protocol_codec.decode_body()` and client captures, `out` means **client → server**, while `in` means **server → client**. World logs use the server's viewpoint: `in` is a received client request, and `out` is a server response. Always name the viewpoint when comparing traces.

Sources: [body decoders](../../server/protocol_codec.py), [game framing](../../server/local_game_server.py), [Spin/protobuf codec](../../server/wakfu_server/intergame_codec.py).
