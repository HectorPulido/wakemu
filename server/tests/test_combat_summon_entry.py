import os
import random
import struct
import unittest
from unittest.mock import patch
import test_combat_spell_transaction as fixture_module
from wakfu_server.combat_server_spell import server_runtime, prepare_server_spell
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


@patch.dict(
    os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"}
)
class NativeSummonEntryTests(unittest.TestCase):
    def test_native_granted_sphere_common_entry_and_registered_roster(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(5, 20)
        deck = encode_deck([], [])
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=1,
            critical=False,
            rng=random.Random(1),
        )
        dispatcher, _ = factory(
            fight,
            dict(
                native_retained_container=dict(
                    present=True,
                    type=3,
                    id=(6755 << 16) + 1,
                    is_spell=False,
                    protected=None,
                )
            ),
        )
        # Actual649 child of native6755 grants5345; no copied/custom ability definition.
        dispatcher.execute(EffectInvocation(313107, 1, 7, 7, (0, 0, 0)))
        before = snapshot(fight)
        body = struct.pack(">qqiih", 7, 5345, 0, 1, 0)
        cast = prepare_server_spell(
            body,
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(len(cast.fight.native_effect_areas), 13)
        self.assertEqual(
            {row["reference"] for row in cast.fight.native_effect_areas.values()},
            set(range(1546, 1559)),
        )
        self.assertEqual(len(set(cast.fight.actors) - set(fight.actors)), 1)
        classes = [
            struct.unpack_from(">i", data, 12)[0]
            for opcode, data in cast.packets
            if opcode == 13497
        ]
        self.assertEqual(classes.count(315), 13)
        self.assertEqual(classes.count(307), 1)
        self.assertEqual(
            cast.fight.actors[7].ap, fight.actors[7].ap - cast.plan["costs"]["ap"]
        )
        # Actual400 producer352198 emits2251 to a real Qq; Qq routes channel1
        # to its actual running caster. No fabricated turn or effect source.
        import copy

        source_before = snapshot(cast.fight)
        area = next(
            row
            for row in cast.fight.native_effect_areas.values()
            if row["reference"] == 1558
        )
        area_preview = copy.deepcopy(cast.fight)
        area_factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=3,
            critical=False,
            rng=random.Random(1),
        )
        area_dispatcher, area_packets = area_factory(
            area_preview, {"native_retained_container": {"present": False}}
        )
        area_dispatcher.execute(
            EffectInvocation(
                352198, 1, 7, area["uid"], area["cell"], native_explicit_target=True
            )
        )
        self.assertEqual(area_preview.actors[7].position, (0, -2, 0))
        self.assertTrue(area_packets)
        # Original843 definition317642 selects this explicit area, calls Qs.b,
        # and removes no other clock-cell UID. Reconstructing retains ownership.
        area_dispatcher.execute(
            EffectInvocation(
                317642, 1, 7, area["uid"], area["cell"], native_explicit_target=True
            )
        )
        self.assertNotIn(area["uid"], area_preview.native_effect_areas)
        self.assertEqual(len(area_preview.native_effect_areas), 12)
        self.assertTrue(
            any(
                op == 13497 and struct.unpack_from(">i", payload, 12)[0] == 843
                for op, payload in area_packets
            )
        )
        self.assertTrue(any(op == 13560 for op, _ in area_packets))
        area_factory(area_preview, {"native_retained_container": {"present": False}})
        self.assertEqual(snapshot(cast.fight), source_before)
        # Real307 root from5345 also supports a new runtime after commit.
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=2,
            critical=False,
            rng=random.Random(1),
        )
        import copy

        preview = copy.deepcopy(fight)
        dispatcher, packets = factory(preview, dict(spell_id=5345, evaluation_level=1))
        dispatcher.execute(EffectInvocation(313167, 1, 7, None, (0, 1, 0)))
        from types import SimpleNamespace

        tx = SimpleNamespace(fight=preview, packets=packets)
        added = set(tx.fight.actors) - set(fight.actors)
        self.assertEqual(len(added), 1)
        actor = tx.fight.actors[next(iter(added))]
        self.assertEqual(
            (actor.hp, actor.ap, actor.mp, actor.effective_level), (1, 0, 0, 20)
        )
        self.assertNotIn(actor.id, tx.fight.order)
        self.assertEqual(actor.position, (0, 1, 0))
        self.assertTrue(any(opcode == 13497 for opcode, _ in tx.packets))
        self.assertEqual(snapshot(fight), before)
        # A newly constructed runtime must recognize the persisted registration,
        # while an actor added without that registration remains rejected.
        _, adapter = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=3,
            critical=False,
            rng=random.Random(1),
        )
        self.assertTrue(adapter.actor_authority(tx.fight, actor).is_summon)
