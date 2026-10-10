# Osamodas capture client property serialization

## Finding

Invocation 7348's installed casting criterion includes `IsEnemy() and HasFightProperty("target",40) and GetStateCountInRange(-1,"caster",7128,"caster") < 1`. Native ordinary NPC profile 4 supplies property 40 (`CAN_BE_SEDUCED`); profile 5525 instead supplies 15/78. The server authority already exposed the correct breed properties, but its ordinary NPC actor payload sent a null fight-property component to the client. This explains a client-side unavailable capture target without a server cast rejection. It establishes a concrete eligibility defect; live screenshot acceptance remains pending.

The shipped client format2 (`eHf.pMq`) consumes, in order: POSITION, FIGHT, FIGHT_CHARACTERISTICS, FIGHT_PROPERTIES, BREED, CONTROLLED_BY_AI, PUBLIC_CHARACTERISTICS, ID, IDENTITY, HERO, DOWNSCALE_INFO. The Python serializer put `_ai_control_byte` in the FIGHT_PROPERTIES position, followed by a breed and hardcoded 1 in the actual AI position. Thus a false AI value decoded as null `rK.XP`; true values could incorrectly announce a populated property component without its data.

Native `eGp.zm` explicitly sets `eGj.pGH=null` when this component is null. When populated it reads `rK/rN/wU`, then calls `eHN.b(wU)` to replace the complete property population. Breed metadata alone does not repair the transmitted null component.

## Change

`combat_property_wire.py` encodes the complete native signed-byte property counters (`01`, unsigned-short count, signed-byte ID/count pairs). Fresh ordinary NPCs use their installed profile filtered through the existing property registry. Runtime ordinary NPC refreshes preserve actual live counters, including removals, multiplicity, negative byte values and empty populations; a live set without counters rejects instead of reconstructing multiplicity.

`combat_actor.py` sends this component after fight characteristics, then breed and the actual AI byte. It preserves all other fields and leaves player and summoned-actor serializers unchanged. No property 40 or spell 7348 special case was added.

## Verification

Focused Python command, with the existing local database/password-file environment:

```sh
PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_monster_property_wire test_combat_actor
```

Result: 8 tests passed in 0.028 seconds. Cases cover actual published profile 4, noncapturable 5525, live removed/added signed counters, empty population, malformed counters, and ordinary actor resource/identity serialization.

`sniffer/java/ProbeNativeMonsterFightProperties.java` independently deserializes every format2 section with the shipped client's actual `gp.aG`, asserts exact end of input, repeats the actual `eHj.ew` path, loads the decoded property component through native `eHN.b`, and evaluates native presence of `ffe.Ua(40)`.

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/osa-property-probe sniffer/java/ProbeNativeMonsterFightProperties.java
java -cp '/tmp/osa-property-probe:client/lib/*' ProbeNativeMonsterFightProperties /tmp/osa-property-probe/4.bin true
java -cp '/tmp/osa-property-probe:client/lib/*' ProbeNativeMonsterFightProperties /tmp/osa-property-probe/5525.bin false
java -cp '/tmp/osa-property-probe:client/lib/*' ProbeNativeMonsterFightProperties /tmp/osa-property-probe/refreshed.bin false
java -cp '/tmp/osa-property-probe:client/lib/*' ProbeNativeMonsterFightProperties /tmp/osa-property-probe/empty.bin false
```

All four passed with complete section consumption. Binary inputs were generated from the actual Python serializers: fresh profile 4, fresh5525, actual profile 4 refresh with `{28:2,65:-128}` and actual profile 4 refresh with an empty population. Generated binaries remain under `/tmp`, outside version control.

## Manual acceptance after coordinated deployment

Outside combat, create `!mob 4 8 1`, start combat with an Osamodas, and reach its actual turn. With no other target carrying that caster's capture state 7128, select Invocation and target the living adjacent creature within native range/LOS. The tile must be eligible and the capture mark must apply. Kill the marked creature normally, verify one persistent roster entry, reconnect outside combat, invoke it, play its own turn, retire it and reuse the slot. Then verify an ordinary noncapturable enemy does not acquire capture eligibility, and ordinary monster turns continue normally.

This work performed no restart or deployment. Full client capture-to-roster lifecycle acceptance is still required; the native probe certifies the repaired wire layout and property gate, not every Osamodas mechanic.
