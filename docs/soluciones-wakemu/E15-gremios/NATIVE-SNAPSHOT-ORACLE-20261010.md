# Native snapshot oracle (2026-10-10)

The repository helper `sniffer/java/VerifyGuildSnapshot.java` was compiled against the installed `client/lib/*` and executed offline. No GUI, network session, services, migration or database was started.

Python `guild_wire.serialize_guild` generated a snapshot with guild 456, two ranks (100/101), one member (999), Unicode name, owner 7 and all required fields. `replace_local_entity` embedded it in format22. The fixture was synthetic; owner 7 does not establish the real account ownership semantics.

The installed native classes verified:

- `jU.bt` accepts the protobuf and reports it initialized.
- `fgL.fK` produces a guild model with the expected guild identity, two ranks and one member; identities can be looked up.
- `cyo.dp` accepts the 15548 i64 actor ID/u16 entity length carrier.
- `qH.aG` decodes the nonempty local guild section from offset 32 and leaves exactly eight trailing nation-money bytes.
- Native `qH.aF` reproduces the section bytes exactly, including its float32 factor.

Observed result: `PASS native protobuf + fgL member/rank model + cyo15548 + qH nonempty format22; protobuf=112 entity=158`.

Commands (fixture files remain private runtime data):

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/e15-snapshot-oracle sniffer/java/VerifyGuildSnapshot.java
java -cp 'client/lib/*:.runtime/e15-snapshot-oracle' VerifyGuildSnapshot .runtime/e15-snapshot-oracle/guild.pb .runtime/e15-snapshot-oracle/entity.bin
```

Read-only `javap -p -c fgL` also established that its member consumer calls `ByteString.byteAt(0)` for **smiley, sex, serializedLanguages and accountCommunityId**. Empty required byte strings satisfy protobuf presence but crash the member consumer. The server serializer therefore requires exactly one byte for these fields and the fixture uses `00`. This proves consumable default bytes; it does not establish every valid enum value or account/community identity policy.

This oracle validates the native parser and local section carrier, not login ordering, actor UI installation, invitation state or real membership. Live acceptance remains pending by instruction. The existing hero fade-completion oracle covers empty format22; nonempty snapshot application through a fully initialized selected actor still requires the combined acceptance test.

## Narrow remote update and protobuf deltas

Further native inspection established `eHf.values()[12]` / `FOR_REMOTE_UPDATE_CHARACTER_INFORMATION`: exactly `NATION_ID`, `NATION_SYNCHRO`, `GUILD_REMOTE_INFO`. There are no fighter, combat, characteristic or appearance sections. `remote_actor_update` emits this format through the verified 15548 carrier. It includes authoritative nation state (default neutral ID and 27 zero synchronization bytes, matching the existing server policy), so callers must override that state if the nation policy changes.

The Java oracle accepts an optional third fixture path and verifies the exact native format12 section enum names, `cyo` carrier and `rV` remote guild decoder with no trailing bytes. Observed: `PASS native format12 only nation identity/synchronization + guild remote info; bytes=73`. This is a parser oracle, not a claim of live nameplate repaint.

Read-only native `javap -p -c fhi fhJ fhh fhI` establishes:

- ADD_RANK (6) and MODIFY_RANK (8) serialize via `fgL.l`, decode via `fgL.fL`: raw rank protobuf.
- ADD_MEMBER (0) and MODIFY_MEMBER (2) serialize via `fgL.u`, decode via `fgL.fN`: raw member protobuf.

The helpers `rank_delta` and `member_delta` return these verified kind/payload pairs for `delta_envelope`. MODIFY_RANK's native application changes name and authorizations; it does not reorder positions, which require the separately established MOVE_RANK operation. Full snapshots remain available for complete reconciliation.
