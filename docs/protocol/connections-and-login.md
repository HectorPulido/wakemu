# Connections and login

[Protocol home](README.md) · Next: [Binary messages](binary-messages.md)

## More than one protocol

The client does not log in and play over a single HTTP connection. Wakemu supplies several interfaces with different jobs:

| Endpoint | Default | Protocol and role |
| --- | --- | --- |
| Local account API | `18081` | HTTP/JSON for registration, login, and token issuance. |
| Launcher bridge | An ephemeral loopback port | A small Thrift TBinaryProtocol RPC interface expected by the launcher integration. |
| Dispatcher | `15558` | TLS plus the game's binary framing; authenticates and lists realms. |
| World | `15556` | TLS plus the game's binary framing; selects characters and handles gameplay. |
| Intergame | `16337` | TLS/Spin with JSON authentication and protobuf requests for supported messaging. |

These are the emulator's defaults. Compose bindings and the address advertised in the realm list are separate settings. A reachable dispatcher does not guarantee that the world address it returns is reachable.

## From account credentials to a world ticket

The local login dialog sends credentials to the account API. Its private login file holds token-based access. The launcher bridge serves the limited RPC calls needed by the client and obtains a game token through `/game-token`; it does not need official account credentials.

The dispatcher then follows this main exchange:

| Client request | Server response or action |
| --- | --- |
| `33`: version information | `23`: accepted flag plus supplied version bytes; `309`: seed. |
| `574`: authentication challenge request | `400`: challenge value and public key. |
| `584`: encrypted authentication | Decrypt and validate the challenge; consume the game token; respond with adapted account information (`472`). |
| `402`: realm-list request | `453`: local realm information with the configured name, host, and port. |
| `575`: select realm | Validate realm `10`; issue a session-bound ticket in `466`. |

This is a local compatibility implementation. For example, its version handler acknowledges the submitted bytes; that is not proof of negotiation with arbitrary client versions. The supported installation remains 1.93.1+79. Challenge and seed values are currently fixed in this implementation rather than being a description of an official production handshake.

Authentication inside the TLS session also uses RSA PKCS#1 v1.5 decryption. The decrypted payload contains a challenge and a length-prefixed token. Encryption is only one check: the token must have the right purpose and be consumable by the local account store.

## Entering world

The client opens the world connection and submits `426`, containing the ticket and machine identifier. World consumes the ticket and verifies its realm and session generation. It publishes the character-selection bootstrap and related account state.

Selecting a character uses `23664`: a character ID plus name. World loads the owned character, checks the name, reconciles relevant dungeon or fight recovery, and builds the character's scene. Character creation has a separate request (`22296`); it is not a variation of selection.

A new account session receives a new generation. Old sockets and old tickets must not continue acting as that account. Replacement therefore includes flushing pending position work and retiring the previous connection.

## The separate messaging connection

Intergame uses Spin framing, not dispatcher/world framing. The client sends availability control kind `1`; the server responds with kind `2`. A data frame then carries JSON authentication with `clientType: 2` and a token. Subsequent data frames contain protobuf `transport.Frame` requests, with correlation IDs matching responses. Kind `3` is a control heartbeat whose session must still be active.

Sources: [game sessions and listeners](../../server/local_game_server.py), [launcher bridge](../../client-tools/runtime/local-launcher-bridge.py), [launcher token renewal](../../client-tools/runtime/local_launcher_auth.py), [intergame transport](../../server/wakfu_server/intergame_transport.py).
