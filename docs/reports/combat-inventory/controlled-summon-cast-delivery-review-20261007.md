# Controlled class summon cast delivery

The shared opcode13260 route now selects the connected player's source and
deck, instead of searching player sources for the requested summon actor ID.
`resolve_owned_spell_action` remains responsible for verifying the actual
active actor, registered controller ancestry and summon-owned action book.
Passing the owner deck does not make that deck available to the summon.

Registered summons serialize native fighter format2 from their actual current
characteristic snapshot and creation reference. They never call
`STORE.character(owner_id, summon_id)`. Missing registrations and changed
reference, level or controller provenance reject before serialization. The
preview fight is supplied explicitly so a summon created during this cast is
already registered when its update is prepared.

Native evidence: `bje.dpT()` returns its `eHj ijU`; `eGj.as(byte[])` invokes
`dpT().ew(byte[])`. `ProbeNativeSummonFighterStats.java` verifies that the
installed native `eHj` format2 decoder preserves positive summoned actor ID901.
The existing ordinary monster serializer's negative-ID restriction remains
unchanged. The scoped new serializer uses complete `snapshot_characteristics`,
not reconstructed NPC defaults.

Offline Java probe command:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/combat-review-20261007/summon-stats sniffer/java/ProbeNativeSummonFighterStats.java
java -cp '.runtime/combat-review-20261007/summon-stats:client/lib/*' ProbeNativeSummonFighterStats .runtime/combat-review-20261007/summon-stats/positive.bin
```

Result: PASS. Python syntax checks passed for the integration, two helpers and
two test modules. Four focused unit tests are delegated to the validation
agent. This is delivery/dispatch evidence, not proof that all summon abilities,
AI, client UI, control changes or reconnect flows work. No service, database,
container or running client was changed or restarted.
