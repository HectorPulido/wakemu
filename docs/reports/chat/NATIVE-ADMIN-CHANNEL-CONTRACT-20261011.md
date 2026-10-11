# Installed native administrative chat contract

Read-only evidence from the installed `client/lib/wakfu-client.jar`, inspected with `javap -p -c`. No client assets or services were changed.

## Commands

The installed `ChatCommandDescriptorSet.xml` registers `/a`, `/A`, and `/admin` as `AdminMessageCommand`. `/d` and `/D` register `IntergameMessageCommand`, a separate Ankama intergame protobuf connection. They must not be aliased to administrative chat on the world server. `/b` registers `BattlegroundMessageCommand`; its eligibility is the native world-definition `cdI.lVs` flag through `fAh.gvX().mP(actor.arM()).eyc()`, not an established individual combat-participation predicate.

## Narrow administrative permission

`AdminMessageCommand` reads `actor.dtz().cXd()` and calls `eDE.b(rights, eDF.oSX)`. Enum `eDF.oSX` is `ADMIN_CHAT`, ordinal 110, with no subordinate permissions. `eDE.c(int[],short)` tests `rights[ordinal / 32] & (1 << (ordinal % 32))`. Consequently the required permission is word index 3, bit 14 (`0x4000`). This does not justify granting broader moderation or game-master privileges.

Entity section `ACCOUNT_INFORMATION` is enum `eHe` ordinal 48. `eHd.a(eHe)` selects `ftI()`, which `eHk` implements by returning `fvp()`, an `oJ` serializer. Its first bytes encode an unsigned 16-bit rights-word count followed by that many big-endian 32-bit words. Remaining fields follow this variable-length prefix and must be preserved byte-for-byte. During local actor hydration, `biB` constructs `biD(actor, oJ)`; `biD` calls `actor.dtz().b(oJ)`, and `eDv.b(oJ)` assigns `oJ.RI` to the actor rights array.

A server implementation should publish this one permission only for its independently authorized administrative accounts, preserve other independently authorized rights, and clear any inherited fixture administrative rights for ordinary accounts. This report does not authorize altering account roles.

## Channel subscription

`aOd.ADMIN` has channel ID 10 and subscription permission `eEY.ADMIN_CHANNEL`, ID 0. `aNT.a(eEY)` sends `NN` through the chat connection. `NN` has opcode 649 and a four-byte big-endian permission ID body. Subscription and the actor permission check are distinct requirements. Native `AdminMessageCommand` sends the world request `cmn` only after passing the permission check.

The default chat view in `data.jar!chat.xml` includes channel 10 and political channel 8. An earlier investigation incorrectly described channel 8 as excluded; the actual pipe list includes it.

## Reproduction evidence

Disassemblies in `.runtime/chat-native-20261011/`:

- `rights-authorization.txt`: `eDE` bit-test arithmetic.
- `admin-permission-enum.txt`: `eDF.ADMIN_CHAT` ordinal.
- `rights-storage.txt`: `eDv` setters and hydration.
- `rights-consumers.txt`: `biB`/`biD` receiving actor hydration.
- `admin-wire-model.txt`: `oJ` rights serialization and `NN` opcode/body.
- `entity-section-descriptor.txt`: section ordinal-to-serializer dispatch.
- `native-channel-commands.txt`: installed administrative, battlefield, political command behavior.
- `intergame-command.txt`: separate intergame connection and protobuf send.

These establish native contracts. They do not constitute a live server acceptance test.
