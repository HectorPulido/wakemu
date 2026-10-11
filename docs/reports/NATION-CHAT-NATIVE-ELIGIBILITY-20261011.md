# Nation chat: native eligibility and authoritative membership

Status: native-input investigation reopened after Hector rejected command aliases. Earlier receiver and membership verification remain valid; native sending and graphical acceptance are pending. No client files, nation ranks, battleground memberships, combat or spell behavior are changed.

## Installed send and synchronization contracts

`PoliticMessageCommand.a(...)` checks the selected actor's `frj.etJ()` against neutral `frk.sZj` (nation0), then requires `frj.etW()` to return a nonnull `fsI`. It sends12387 only after both checks. `fsI` contains government offices, IDs1..10: governor, deputy, marshal, general, meteorologist, treasurer, challenger, spy, assassin and zoologist. There is no ordinary citizen rank that can be assigned merely to open chat.

The native27-byte `NATION_SYNCHRO` consists of rank/int64, jobs/int64, vote-date/int64, opinion/byte, candidate/byte and PvP-rank/byte. `bjI.zm()` maps its first field `rk.WO` through `fsI.uD` into `bVr.b(fsI)`, so a fabricated nonzero value grants actual government identity rather than a chat-only permission. Nation identity is a separate signed int32. The initial audit found forced neutral nation identity in ordinary and format22 bootstrap; the authoritative nation framework follow-up below corrects identity while keeping ordinary synchronization free of government privileges. The SQL chat membership introduced by migration120 is routing authority; it is not a complete citizenship/government subsystem and is not falsely serialized as one.

`BattlegroundMessageCommand.a(...)` sends13702 only if
`fAh.gvX().mP(actor.arM()).eyc()` is true. The key is the current native world
ID, not character ID. Follow-up proves `cdH` implements this lookup through
its local `cdI` world catalog. `cdI.eyc()` returns `lVs`, loaded from the
original little-endian world asset by `cdH.dW`. This is a native world-type
flag, not a player participation field or nation permission. No server
eligibility publication which changes this catalog flag was found. Giving an
ordinary map a false battleground identity would not be a legitimate chat fix.


Receive handlers are separate: `chc` dispatches758/`Oh` to Politics `aOd.exa`, and632/`NO` to Battleground `aOd.exd`. Their shared `a(NQ,aOd)` builds the native chat row and publishes it to `aNZ.d`; it contains no nation, government-rank or battleground-send gate. Normal chat-tab visibility/filter preferences still apply.

Private reproducible bytecode evidence is in `.runtime/local/native-nation-chat-eligibility-20261011.txt`, `native-nation-chat-synchro-consumer-20261011.txt`, `native-nation-chat-bjo-20261011.txt`, `chat-handler.txt` and `/tmp/wakemu-native-chat-send-gates.txt`.

## Superseding native-input requirement

Hector rejected the `!politica` / `!jcj` command workaround. The dispatcher
aliases, parser helper and alias-only tests have been removed. `!nacion` remains
the separate legitimate native nation-selection entry. Historical alias test
results do not establish acceptance of the requested native chat channels.

Installed `ChatCommandDescriptorSet.xml` establishes the actual mappings:

- `/b` invokes `BattlegroundMessageCommand` and world request13702.
- `/f` invokes `PoliticMessageCommand` and world request12387.
- `/a` or `/admin` invokes the administrative channel, world request12116.
  `AdminMessageCommand` requires the actual `eDF.oSX` / `ADMIN_CHAT` permission;
  menu permission `eEY.phm` / `ADMIN_CHANNEL` is a separate native enum.
- `/d` invokes `IntergameMessageCommand`, not the administrative channel. It
  requires a connected `aTx.cWN().bSV()` intergame transport and recipient
  roster `aOD.eAd`, then sends a protobuf message through `aYH.c(MessageLite)`; it is not a world chat opcode.

Descriptor registration is locale-independent in the verified loader:
`aNT.czG` reads `/ChatCommandDescriptorSet.xml`, and `aSW.startElement` passes
its raw `cmdPattern` into `aSU`, without localization substitution. Actual
registration through `new aSV().g(aNT.czG())` independently returned the same
four command classes. Spanish labels therefore do not turn `/d` into `/a` in
this installed catalog. Selecting a chat channel in the native UI also does
not bypass these commands: `cJq.processKeyTyped` prefixes `aNQ.czw()` when the
text has no slash, then dispatches through `dhb`.

Native send eligibility and the intergame service bootstrap are being audited.
No government office, battleground membership or administrator permission is
fabricated to expose a channel. Authoritative same-nation world routing exists,
but that alone does not make a native input channel usable.

`test_chat_channels` now exercises original12387/13702 requests directly and
retains durable nation isolation and UTF8 limits. The local dispatcher tests
retain only native nation-selection behavior. A fresh automated gate will be
required after this superseding change.

`sniffer/java/VerifyNationChatReceive.java` additionally runs the installed original `chc`758/632 dispatcher, original `aNZ` manager and native `aOb` message history. The fixture uses an actual neutral `biB`, null government rank and an explicit inactive battleground fixture. It asserts both native histories contain the decoded text and nation/rank/BG remain unchanged. This is actual native receive/manager execution, not screenshot or rendered-interface acceptance.

Reproduce from the repository root:

```sh
mkdir -p .runtime/local/nation-chat-receive
PYTHONPATH=server python3 - <<'PY'
from pathlib import Path
from wakfu_server.chat_channels import payload
body = payload(5, {"name": "Sender"}, "hola native", language_mask=6, community=4)
for name in ("political.bin", "pvp.bin"):
    Path(".runtime/local/nation-chat-receive", name).write_bytes(body)
PY
javac -proc:none -cp 'client/lib/*' -d .runtime/local/nation-chat-receive sniffer/java/VerifyNationChatReceive.java
java -Djava.awt.headless=true -cp '.runtime/local/nation-chat-receive:client/lib/*' VerifyNationChatReceive .runtime/local/nation-chat-receive/political.bin .runtime/local/nation-chat-receive/pvp.bin
```

Observed output: `PASS opcode=758 nativeChannel=POLITIC` and `PASS opcode=632 nativeChannel=BATTLEGROUND`, both with `neutral=true office=null battleground=false`. Native logging initialization warnings do not affect the assertions. Evidence: `.runtime/local/nation-chat-receive/oracle.log`.

Luna independently compiled and replayed the same harness and production fixtures; both assertions passed. Independent evidence: `.runtime/local/nation-chat-receive/independent-oracle.log`. This remains an offline native-manager result; live graphical acceptance is not claimed.


## Authoritative nation framework audit (follow-up)

The previous chat-only implementation was incomplete: migration120 had no production enrollment writer; character hydration omitted membership; ordinary native identities and hero format22 forcibly advertised nation0; company initialization and emote nation expressions also forced0; guild roster and remote refresh could discard citizenship. Routing tests alone did not verify these lifecycle paths.

The staged `characters/nation_state.py` now owns validation and the canonical migration120 membership table. Missing membership remains neutral0; the four enrollment choices are Amakna30, Bonta31, Brakmar32 and Sufokia33. Installed `frk` constants additionally recognize34; existing membership34 is preserved and routed, while this enrollment flow does not offer34. Root verified `javap -classpath client/lib/* -constants frk` constants0,30,31,32,33,34. No captured Amaknian citizenship is inherited. `Store.character` hydrates this field, including creation, selection, reconnect and owned hero loads. Company (including hero company), guild roster, guild local/remote updates, emote `GetNationId()` and chat consume that same authority. Shared native serialization and dispatcher integration are coordinated separately by the root agent.

Installed `cLs.chooseNation` emits local18979; `ddw` confirms the selection and creates network `crn`12463. Its body is exactly an int32 nation followed by two zero bytes. The installed selection panel permits only neutral characters at level1 or above. The server enrollment operation independently validates this shape, locks the authenticated selected-character session and character row, rejects existing citizenship and invalid choices, then persists membership for that individual character. An account sibling never inherits membership. This is ordinary citizenship, with no government office or battleground participation granted.

Installed `rr` proves PASSEPORT_INFO is exactly one active byte. Installed `qT` proves CITIZEN_POINT contains uint16 score count followed by `(int32 nation,int32 score)` rows, then uint16 offense count followed by `(int32 nation,int32 value,int64 timestamp)` rows. These contracts alone do not establish gameplay permission to activate a passport or award citizenship scores; no such state is fabricated.

New focused tests cover native IDs and exact malformed enrollment packets, persistence after reopen/reconnect, neutral defaults, account-sibling isolation, wrong selected character, stale session, repeated enrollment and company identity. Automated integrated execution is delegated to Luna; this follow-up is not yet deployed or graphically accepted.


Luna's expanded nation/wire/guild/emote gate covered120 tests:119 passed initially and one old guild fixture failed during reconnect hydration. The fixture inserted characters directly and omitted the production-created account Haven Bag and build-selection rows. It now reproduces those required initialization rows; all invitation lease replacement, cancellation, pending invitation and final membership assertions remain intact. The focused retry passed1/1 with unchanged source hashes, completing120/120 behavior coverage. Evidence: `.runtime/local/verification-nation-wire-20261011/guild-invitation-retry2.log` and the coordinated gate logs in that directory.

The installed chooser `ddw` checks current `biB.drm()` level and `biB.Xt()` nation: level below1 or existing nonzero citizenship disables selection; a neutral level1 character has no disabled message. Passport activation is not a chooser prerequisite. Government and battleground send eligibility remain the independent native gates documented above.


## Public native enrollment entry

The staged public local-chat command `/l !nacion` opens the actual installed nation-selection panel through14006. Arguments are rejected with `Uso: !nacion`; this command does not accept a client-supplied membership or require administrator/test-console access. The authenticated selected character must still be neutral and level1 or above. Each four-choice native row contains nation, empty treasury/governor/territory/diplomacy state and a population fraction calculated from durable citizenship of nondeleted characters. Existing nation34 membership participates in total population but is not an enrollment choice. Empty government state agrees with the current public regional initialization; no governor or political powers are fabricated.

After deployment, connect two ordinary neutral characters A/B and a third C. Run `/l !nacion` on A/B, choose the same nation in the native panel and confirm; choose another nation on C. Native chat acceptance must use the original slash channels; the removed aliases are not an accepted route. Same-nation delivery across maps must exclude C once legitimate native sending is available. Reopen the passport to inspect current citizenship without claiming passport activation, government office or battleground membership. Reconnect, switch to an account sibling and back: the enrolled character retains citizenship; the sibling stays independently neutral until explicitly enrolled. A second `/l !nacion` on an enrolled character must give the existing-membership error. Graphical chooser rendering and these live outcomes remain pending.


`sniffer/java/VerifyNationSelection.java` passed the production chooser body through the original installed `cyB`14006 parser, checking exact native IDs, population fractions, empty government fields and absence of trailing bytes or nation34. Reproduce offline:

```sh
mkdir -p .runtime/local/nation-selection
PYTHONPATH=server python3 - <<'PYFIXTURE'
from pathlib import Path
from wakfu_server.characters.nation_state import selection_packet
opcode, body = selection_packet({30: 1, 31: 2, 32: 3, 33: 4})
assert opcode == 14006
Path('.runtime/local/nation-selection/body.bin').write_bytes(body)
PYFIXTURE
javac -cp 'client/lib/*' -d .runtime/local/nation-selection sniffer/java/VerifyNationSelection.java
java -cp '.runtime/local/nation-selection:client/lib/*' VerifyNationSelection .runtime/local/nation-selection/body.bin 0.1 0.2 0.3 0.4
```

This verifies the installed native packet parser; live chooser rendering remains pending.

## Original command registration and world-catalog oracle

`sniffer/java/VerifyNativeChatAliases.java` executes the original SAX command
registration and validates `/b`, `/d`, `/a`, `/admin` and `/f` against their
actual native command classes. It also loads the original `worlds.lib` through
`cdH`, verifies ordinary world1134 has `eyc()==false`, and requires actual
battleground worlds to exist. The observed catalog contains720 worlds and7
battleground definitions. No world flag, native class or actor is modified.

```sh
mkdir -p .runtime/local/native-chat-aliases
javac -proc:none -cp 'client/lib/*' -d .runtime/local/native-chat-aliases \
  sniffer/java/VerifyNativeChatAliases.java
java -cp '.runtime/local/native-chat-aliases:client/lib/*' VerifyNativeChatAliases \
  'jar:file:/Users/hectorpulido/Documents/wakfu-experiment/client/contents/maps/data.jar!/worlds.lib'
```

Worker and independent Luna replay: PASS. Evidence:
`.runtime/local/native-chat-aliases/oracle.log`. Full actor command
execution in a separate headless probe failed during native actor setup with
exit134; this is not counted as a passing outbound suppression test. The
ordinary-world send gate is proven by original command bytecode plus actual
catalog lookup, not by a live graphical send. No alternate selected-channel
route avoiding that gate was found. No intergame service implementation was
found under `server/`; `/d` requires its own genuine connection and protocol
rather than an invented world-channel handler.

## Exhaustive installed battlefield flag audit

A full ASM field/call-site scan of the installed client JAR finds exactly two
writes to `cdI.lVs`, both constructors, and three reads, all inside `cdI`.
The field is final. Constructor callers are the local catalog parser
`cdH.dW(ByteBuffer)` and the `cdI.a` clone. The clone is used only by
`cdH.mN` for the negative-world fallback and preserves the source flag.
The parser is invoked only by startup `aGZ.cfV` using `worldInfoFile`.
The catalog map accessor is used only by lookup enumeration, not mutation.
No incoming handler directly or indirectly replaces that flag was found.
Evidence: `.runtime/chat-native-20261011/wakemu-cdI-bgflag.txt` and
`wakemu-world-catalog-bootstrap.txt`.

Consequently canonical same-nation routing of13702 is implemented, but
ordinary-world native `/b` entry remains blocked before network send.
No supported server-only override has been established; spoofing a battlefield
world or changing client assets would violate this session's constraints.

## Real intergame transport requirements

Native `/d` uses TLS and Spin framing on its own connection, not a World
request. The installed initializer uses a big-endian32-bit total frame length
including the length prefix and a one-byte Spin type. Client sends Spin1,
server availability is Spin2, then native HAAPI requests a game99 token.
Authentication JSON carries `token`, `clientType`, `osType`, `deviceType`,
`deviceId`, and `customApplicationData`; its response is `success`/`errCode`.
Only genuine token authentication can authorize a successful response.

After authentication the client installs its original protobuf envelope
decoder and sends account subscription/presence messages. `/d` sends original
`channel.CreateChannelMessageCmd` with `channel_id`(1),
`author_user_id`(2), and `content`(3). Its channel lookup uses the native friend
directory. The original descriptors were extracted directly from generated
classes, without inventing a World opcode or alias. Evidence lives in
`.runtime/chat-native-20261011/intergame-{transport,handshake,envelope,descriptors}.txt`.
The current backend has neither the16337 listener nor HAAPI
`Account/CreateToken` support; it must implement the real authenticated service
and directory/message protocol before `/d` can be claimed operational.

The separate legitimate `/a` permission helper projects only native
ADMIN_CHAT ordinal110 from a trusted account role. Original `eDE.b` execution
confirms word3 mask0x4000; this grants no other rights. Wire integration and
live administrative-channel acceptance remain separate requirements.

The seven original installed battleground world IDs are1161,1203,1217,1218,
1219,1277,1279. All seven have catalog `lVo=-1`, so this audit does not invent
translated names or walkable coordinates. Use existing legitimate battlefield
entry and inspect the current native world before testing `/b`; do not
teleport to guessed heights or reclassify ordinary maps.
