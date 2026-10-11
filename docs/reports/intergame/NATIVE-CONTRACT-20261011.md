# Installed native intergame contract

Source: `client/lib/wakfu-client.jar`, SHA-256 `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`.

`ExportNativeIntergameDescriptors.java` exports all 41 `aj` registrations and 46 recursive protobuf message schemas, including transport envelopes, enum values, repeated fields and oneofs. Output: `server/protocol/native_intergame_descriptors.json`. The generated classes have obfuscated accessor names: calling ordinary protobuf reflective `getDescriptorForType()` fails. The exporter invokes their original static descriptor methods instead.

## Connection and authentication

Native TLS transport frames are a big-endian uint32 total length including its four bytes, followed by one type byte and payload. The maximum frame length configured by the client is 1 MiB. Native `aYP` encodes types 0 (payload), 1 (initial hello), 3 (heartbeat). The client sends type 1 with total length 5; server type 2, also total length 5, triggers HAAPI game-99 token acquisition through `aYS`. Authentication is type-0 JSON, not protobuf:

`token`, `clientType` (2), `osType` (native OS value), `deviceType` (3), `deviceId`, `customApplicationData`.

`aYQ` reads JSON `success` and `errCode`. Successful auth replaces the JSON handler with protobuf `am` and `aYL`, then requests friends and publishes endpoint properties. Single-use token authorization must bind the authenticated account independently of later protobuf author/user fields.

## Protobuf transport

`transport.Frame` oneof: request field 1, response field 2, event field 3. Payload contains `id` int32 field 1 and `data` bytes field 2. Request contains correlation ID field 1 and payload field 2. Response contains correlation ID field 1, status field 2 (`Success=1`), and payload field 3. Native `aYL` decodes only successful responses and events. IDs include negative int32 values, which native protobuf encodes with ten-byte signed varints.

Important requests: `LIST_USER_FRIENDS_CMD=-1933682604`, `UPDATE_USER_ENDPOINT_PROPERTIES_CMD=-73350898`, `CREATE_CHANNEL_MESSAGE_CMD=1835442294`. Responses/events: `FRIEND_LIST=-1150791598`, `CHANNEL_MESSAGE_CREATED_EVT=804239649`. All remaining IDs/layouts are in the generated JSON.

## Native recipient and display contract

`aYV` populates `aOD` from `FriendList`. Name lookup is case-insensitive, optionally using `name#tag`. `aOD` maps the friend to the exact channel returned by `aON.ii`: `DM_<smallerAccountId>_<largerAccountId>`, using local `aTJ.xl()` and friend user ID. A generic `UserList` response is registered as a protocol message but is not installed as the friend-directory population handler.

`aYU` consumes `ChannelMessageCreatedEvt`, reads its nested message content and author account ID, selects `aOd.exe` (intergame chat), and publishes through `aNZ`. Incoming messages display the author's name/tag. The sender echo resolves the other participant's name from the channel through `aOD.jE`. Server delivery should therefore echo the same authorized channel event to both endpoints.

## Offline verification

Compile both Java sources with `javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-intergame-oracle ...`. Running `VerifyNativeIntergameCodec` without arguments executes original `aYN/aYP` auth serialization/framing and original `aZf` auth-response JSON parsing. It passes. To verify a production-generated inbound event, supply the unframed protobuf Frame filename, expected channel, expected text, and expected author account ID. The oracle executes original `am.m`, `aYL`, and nested `l/i` parsers. It does not claim to execute UI rendering or contact a live service.

Production-codec fixtures passed the original incoming event decoder (`DM_5_6`, author 6, content `Native intergame`) and negative-ID FriendList response decoder. The latter additionally executes original `aYV` and verifies original `aOD.V("Peer", "6")` resolves `DM_5_6`. Logs: `/tmp/wakemu-intergame-event-oracle.log` and `/tmp/wakemu-intergame-friends-oracle.log`. These passes cover encoding compatibility and native directory registration, not a live authenticated TLS session or rendered chat.

## Server implementation and integration

The implementation is `intergame_codec.py`, `intergame_domain.py`, and
`intergame_transport.py`; canonical migration138 is
`138_intergame_chat.sql`. The descriptor-driven codec has no new dependency.
The HTTP adapter accepts only native GET
`/json/Ankama/v5/Account/CreateToken?game=99` with its existing APIKEY
authentication header. It verifies the real unexpired API token and matching
live game-session generation, then issues a distinct60-second, single-use
intergame token. Reconnect, expiry, consumption, and bans invalidate access.
The transport never treats a protobuf-supplied user ID as authentication.

Root integrates `make_server(Intergame(STORE), existing_server_tls_context,
host,16337)` within the existing World container. The listener runs separately
from the World wire handler. Shutdown calls `close_peers()`, `shutdown()`,
and `server_close()` before closing Store; unauthenticated TLS peers are
tracked and closed as well. Publish only localhost16337. No client files or
client settings are changed. Deployment remains pending independent gates
and the coordinated complete-image rollout.

The native directory uses the existing durable account friends/ignored
authority. Local tags are stable decimal account IDs; account names come from
authenticated account rows. Friend invitations require recipient acceptance
and can only be resolved by their legitimate participant. Direct messages
require a real friend, exact `DM_<low>_<high>` ownership, a matching author,
bounded UTF-8 text, the configured chat rate, and recipient ignore/DND/access
checks. Messages persist for bounded participant-only history and are echoed
to the two authenticated endpoints. No public or administrative privilege is
granted by connecting to intergame.

## Manual acceptance after deployment

Use two accounts controlled by the tester; do not message third parties.
Reconnect both through the original launcher so each has a live native game
session. Open the original community/friends interface and use the account
names and decimal tags published by the native directory. Existing game
friends are loaded automatically; for a new contact, send the original native
friend invitation and accept it from the second account.

1. On the first client type `/d "<second account name>#<second account ID>"
   Native intergame acceptance` using the actual directory entry.
2. Both clients must display the same intergame message; only the sender and
   intended recipient receive it. Reply from the second account through `/d`.
3. Reconnect one client and repeat after the configured rate interval. Its
   replacement session must connect, while the old transport loses authority.
4. Enable ignore or DND for the recipient through the existing native social
   interface. The blocked message must not appear at the recipient. Restore
   the original preference afterwards.
5. `/a` is tested separately using an already authorized administrative
   account. `/d` is a private intergame conversation and grants no admin role.

The installed client reports failed intergame responses through its existing
native transport/error behavior. A successful protocol oracle is not a
claim that these graphical steps have already passed.

## Automated server acceptance

Luna independently passed20/20 tests: descriptor/codec5, PostgreSQL6
including real two-account TLS/Spin authentication, directory and message
delivery, and existing shop HTTP9. The isolated database used the exact
contiguous migration snapshot1–139, including intergame138; selected source
hashes remained stable. Log:
`.runtime/local/verification-intergame-20261011/tests.log`.
Final review then tightened history cursors to positive signed64-bit IDs and
preserved aware database timestamp offsets; the six PostgreSQL tests passed again against those final two source/test
hashes. Final log: `.runtime/local/verification-intergame-postgres-final-20261011.log`. No deployment or
rendered-client success is inferred from automated transport acceptance.
