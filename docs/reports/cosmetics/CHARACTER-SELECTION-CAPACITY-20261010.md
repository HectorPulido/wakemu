# Native character selection capacity

Status: source implemented; deployment and manual acceptance pending. No runtime
write, deployment or restart was performed.

## Cause and native limit

The backend accepted 24 characters from Compose while `Store` independently
defaulted to five. Selection replay also forwarded the captured `23992` extra-slot
value unchanged, so the client continued displaying `1/5`.

The installed client establishes the actual representable maximum:

- `cEk.dp` / opcode `23548` reads the roster count with `ByteBuffer.get()` as a
  signed byte. A count of 127 decodes 127 entries; 128 becomes negative and decodes
  no characters. The final byte counts companion records, not additional slots.
- `cEl.dp` / opcode `23992` reads a signed extra-slot byte. `cgY` applies it through
  `biz.bl`; `bkg.b` computes `maxCharacterCount` from the native free-slot base
  `eEL.oZT` (default five) plus the adjustment. For 127 total slots this byte is
  122 (`0x7a`). The 13 purchasable slots in the shop model are not a roster codec
  limit.

Therefore the maximum coherent native roster and backend capacity is **127**.
Sending 127 extra slots would display 132 while exceeding the roster decoder.

## Implementation

`characters/selection_capacity.py` owns the shared default, validation and native
packet. Store and Compose now default to **18**, as requested by Hector. The native
upper bound remains 127. The default native extra-slot byte is 13 (`0x0d`). An explicit `WAKFU_MAX_CHARACTERS`
override remains supported for totals 1 through 127; invalid values fail early.
Values below five use a negative native adjustment, verified with the actual
client UI model. This is a runtime-wide policy and applies to existing accounts
without database migration.

Selection replay replaces captured `23992` values and sends the configured
capacity before every replayed roster `23548`, including return to selection.
Character creation continues enforcing the same Store limit while holding the
account lock. The roster encoder rejects more than 127 entries rather than
emitting a packet that the native client would misread. Creation/deletion updates
retain the capacity already established for that connection.

## Automated validation

`sniffer/java/VerifyCharacterCapacity.java` uses the installed native decoder and
selection UI model for totals 1, 5, 18, 24 and 127, and proves the signed roster
127/128 boundary:

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-rift-native-oracle sniffer/java/VerifyCharacterCapacity.java
java -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' VerifyCharacterCapacity
```

Native result: `PASS native UI capacity1/5/18/24/127 and signed roster127/128 boundary; free slots=5`.

Python regression modules: `test_character_selection_capacity`,
`test_replay_hydration`, `test_store`, `test_creation` and
`test_character_deletion`. They cover configuration precedence, malformed values,
wire overflow, stale captured slots, existing/new accounts, account isolation and
backend rejection of character 128. Database tests use isolated schemas. Luna reports 17/17 capacity, creation, deletion
and codec checks and 4/4 pure replay checks passing. The replay integration test
with real coders is not certified because its required native capture is absent.

## Manual acceptance after deployment

1. Reconnect an existing account. If it has one character, selection should show
   `1/18`; existing characters must remain listed and selectable.
2. Create enough characters to exceed five. Each should appear in selection and
   remain available after reconnect. Return from a selected character to the
   selector: the denominator must remain 18.
3. Repeat with a newly registered account. Its denominator must also be 18.
4. If testing an explicit configuration such as `WAKFU_MAX_CHARACTERS=24`, rebuild
   and deploy through the normal complete-world workflow, then reconnect. Both
   the UI denominator and backend creation limit must become 24. No account SQL
   update is necessary.

Changing configuration requires a service lifecycle operation; none was performed
as part of preparing this source change.
