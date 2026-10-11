# Native guild lifecycle contracts — 2026-10-10

Read-only offline `javap -classpath client/lib/wakfu-client.jar -c -p CLASS` inspection. No client, service, database or migration was started. All integer fields below use Java ByteBuffer default big endian. `BV.aS` explicitly uses StandardCharsets.UTF_8; lengths count bytes.

## Client requests

All requests below extend Nx and serialize category 6; the category is transport framing, not an additional body field.

| Opcode | Native class | Body | Proven caller/meaning |
| --- | --- | --- | --- |
| 15542 | cBT | i8 UTF-8 byte length + target name | bxk.nF, dgj: invite a character by name |
| 14995 | cCb | u8 boolean (1 accept, 0 reject) | ddy.fgC accepts; fgA/fgB reject or timeout |
| 15627 | cCe | i64 target character ID | dgu passes local biB.Sn for leave; dgx passes fia.Sn for expulsion |
| 14230 | cBV | i64 target character ID + i64 rank ID | bxk.u; dgw prompts giveMasterRank/removeSelfMasterRank when master rank involved |
| 15481 | cBZ | empty | dgo disband confirmation, bxk.dPG |
| 15511 | cBU | i32 UTF-8 byte length + description | cKK.applyGuildDescription emits internal19078, dgq calls bxk.nC |
| 14890 | cBW | i32 UTF-8 byte length + guild message | cKK.applyGuildMessage emits internal17349, dgr calls bxk.nD |
| 15064 | cCd | i8 UTF-8 byte length + personal description | cKK.applyGuildPersonalDescription emits internal19305, dgs calls bxk.nE |
| 14239 | cCf | i8 language mask | dgy calls bxk.bQ |
| 14447 | cBR | i32 bonus ID | dgi sends selected dgH.bES ID; effect/service rules are not established by this request |
| 15613 | cBS | i32 bonus ID | dgl sends selected ID; dgt obtains next-level eHu.fwP().d ID |

Single-byte string encoders cast the byte count to signed Java byte; server codecs should enforce a safe range rather than permit overflow. The membership request carries a character ID, not a guild ID or account ID.

The invitation reply has **no invitation ID or guild ID**. The server must bind it to the one pending invitation belonging to the authenticated recipient/session and reject stale replies. The native UI display uses 15,000/16,000 ms notification timings; these do not establish an authoritative invitation expiry rule. Leadership transfer is represented by rank assignment to the master rank; the packet alone does not define leader demotion policy or legal rank permissions.

## Server invitation and guild chat

Invitation opcode **14954**, class cDl:

```
i32 inviter_name_utf8_byte_count
bytes inviter_name
i32 guild_name_utf8_byte_count
bytes guild_name
```

`cls` handles 14954, reads aXS()/HR(), and creates internal UI event dib16608. `ddy` displays group.guild.invitation with those two strings. 16608 is **not a network packet**.

Guild chat opcode **743**, class NV extends NQ:

```
u8 sender_name_utf8_byte_count
bytes sender_name
u8 language_mask
u8 community
i64 sender_identity
u8 boolean_flag
i16 message_utf8_byte_count
bytes message
```

`chc.b` routes743 to `aOd.ewY`, the GUILD pipe. `NQ.b` decodes the layout above and requires message length to equal all remaining bytes. There is no guild identity in the response body. This matches the common channel payload serializer already in server/wakfu_server/maps/chat_channels.py. The client stores sender_identity as aOa.ewC; its account-versus-character semantics have not been independently established by this inspection. Guild request13744 remains i64 guild ID followed by u16 text length/text (cms + cmq).

## Member snapshot scalars and remote sections

`fgL.v(fia)` maps fia.Xv() to member saveDate. `bxj.dPl` computes `(TX.bjW().bka() - fia.Xv()) / 86400000` for guild.lastConnectionDays: saveDate is a millisecond timestamp on the client clock, not seconds or days.

`fgL.v` creates exactly one byte for smiley, sex, languages and community protobuf ByteString fields. `fgL.e(jQ)` reads byteAt(0). Languages come from ML.aK(Iterable), a bit mask; community comes from UH.d(). Empty bytes are invalid for the consumer. `ownerId` maps fia.Xi() to fgE.ePn but no producer assigning its identity was established; do not infer account identity solely from the protobuf name.

Standalone actor sections:

| Section | Native component | Layout/default |
| --- | --- | --- |
| 27 GUILD_ID | qj.Uz | i64, DN()=8, clear()=0 |
| 28 GUILD_NAME | qn.UR | u8 UTF-8 byte length + name (qn.aF/aG; distinct from rV u16) |
| 29 GUILD_BLAZON | qh.UG | i64 packed blazon, DN()=8, clear()=0 |
| 30 GUILD_REMOTE_INFO | rV | i64 guild ID + i64 blazon + i16 level + u16 UTF-8 length + name |

`eHe` supplies section ordinals; `eHk.ftV/fvL` supplies qj and `ftX/fvN` supplies qh. qj and qh aF/aG use putLong/getLong. Packed emblems use the same 64-bit bit pattern as signed Java long.

## Implementation limits

These contracts establish packet shape and UI meaning. They do not establish official economic costs, initial ranks/permissions, account membership policy, progression earning, bonus effects, treasury/chest/Haven World operations, invitation expiry, or ownerId semantics. Keep unverified behaviors explicitly policy gated. Do not invent missing response/error opcodes.

## Reproduction

```sh
javap -classpath client/lib/wakfu-client.jar -c -p cBT cCb cCe cBV cBZ cBU cBW cCd cCf cBR cBS
javap -classpath client/lib/wakfu-client.jar -c -p cDl cls ddy NV NQ chc
javap -classpath client/lib/wakfu-client.jar -c -p cKK dgq dgr dgs dgw bxk
javap -classpath client/lib/wakfu-client.jar -c -p fgL bxj fgE ML qj qh qn eHe eHk
```

Installed client JAR SHA-256: `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`.

## Identity and bonus activation codecs

Additional read-only `javap -p -c cpq cpp cBR` inspection confirms:

- `cpq` / 12937: signed i32 UTF-8 byte length followed by guild name (`BV.aS`, `ayq.vF` and `ayq.dI`).
- `cpp` / 12575: packed blazon i64 (`ayq.gE`).
- `cBR` / 14447: bonus ID i32 (`ByteBuffer.putInt`).

`guild_wire.decode_request` accepts these exact layouts and rejects truncation, trailing bytes, invalid string lengths and invalid UTF-8. Codec support does not establish economic policy or authorization, which must be applied by the authenticated domain service. Personal description 15064 and language 14239 remain separate member metadata operations and must not be treated as guild renaming.
