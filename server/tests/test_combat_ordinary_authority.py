from copy import deepcopy
import unittest
import test_combat_effect_runtime as fixtures
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    native_property_catalog,
    native_block,
    native_probability,
)


class OrdinaryAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeRuntimeFactoryTests.setUpClass()

    def setUp(self):
        f = fixtures.NativeRuntimeFactoryTests()
        f.setUp()
        self.f = f
        self.preview = deepcopy(f.fight)
        self.authority = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15)},
            monsters={8: dict(id=8, ref=5525), -7: dict(id=-7, ref=5525)},
            decks={7: [6266]},
            excluded_decks={7: []},
        )

    def test_native_export_properties_and_kind(self):
        data = native_property_catalog()
        self.assertEqual(data["player"]["fight_properties"], [])
        self.assertEqual(data["npc"]["5525"]["fight_properties"], [15, 78])
        p = self.authority(self.preview, self.preview.actors[7])
        npc = self.authority(self.preview, self.preview.actors[-7])
        self.assertTrue(p.is_player)
        self.assertFalse(npc.is_player)
        self.assertEqual(p.deck_spell_ids, frozenset({6266}))
        self.assertTrue(npc.targeting["bEe"])
        self.assertFalse(npc.targeting["dTE"])
        self.assertTrue(p.targeting["baF"])
        self.assertTrue(npc.targeting["baF"])
        self.assertEqual(p.targeting["dpu_id"], 7)
        self.assertEqual(p.targeting["dpr_id"], 7)
        self.assertEqual(npc.targeting["dpu_id"], -7)
        self.assertEqual(npc.targeting["dpr_id"], -7)

    def test_selector_life_uses_owned_creation_and_departure_registration(self):
        actor = self.preview.actors[-7]
        actor.hp = 0
        self.assertIsNone(self.authority(self.preview, actor).targeting["baF"])
        self.preview.events.append(dict(kind="death", actor_id=actor.id))
        self.assertFalse(self.authority(self.preview, actor).targeting["baF"])

    def test_active_fight_target_mask_uses_native_obstacle_id_not_affiliation(self):
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        source = self.preview.actors[7]
        target = self.preview.actors[-7]
        contexts = {
            a.id: self.authority(self.preview, a).targeting for a in (source, target)
        }
        effect = dict(fixtures.definition(5, [1]))
        effect["native_target_selector"] = {"class": "fcE", "mask": 1 | (1 << 50)}
        # eGn/eGz stores pW.Uj as the obstacle byte; bcM affiliation is
        # separate. The fixture deliberately has team1 and obstacle2.
        self.assertEqual(contexts[target.id]["bcN"], target.native_obstacle_id)
        self.assertNotEqual(contexts[target.id]["bcN"], target.team)
        selected = select_native_effect_targets(
            effect, source, target.position, (target,), native_context=contexts
        )
        self.assertEqual(tuple(a.id for a in selected), (target.id,))
        target.team = -1
        with self.assertRaisesRegex(ValueError, "affiliation"):
            self.authority(self.preview, target)

    def test_explicit_live_properties_and_relationship_blocker(self):
        actor = self.preview.actors[-7]
        actor.native_fight_properties = {21, 42}
        value = self.authority(self.preview, actor)
        self.assertFalse(value.targeting["bEe"])
        self.assertTrue(value.targeting["UNTARGETTABLE_BY_OTHER"])
        actor.native_carrier_id = 7
        with self.assertRaisesRegex(ValueError, "relationships"):
            self.authority(self.preview, actor)

    def test_block_exact_inclusive_native_draw_and_sentinels(self):
        actor = self.preview.actors[-7]
        actor.effect_stats[87] = 20
        e = {"native_effect_flags": []}
        self.assertTrue(native_block(e, actor, draw_integer=lambda n: 20))
        self.assertFalse(native_block(e, actor, draw_integer=lambda n: 21))
        self.assertFalse(
            native_block({"native_effect_flags": [2]}, actor, draw_integer=lambda n: 0)
        )
        self.assertTrue(native_probability(100, draw_percent=None))
        self.assertFalse(native_probability(0, draw_percent=None))
        self.assertTrue(native_probability(50, draw_percent=lambda n: 50))
        self.assertFalse(native_probability(50, draw_percent=lambda n: 51))
        self.assertTrue(
            native_probability(
                50.5, draw_percent=lambda n: 51, random_fraction=lambda: 0.2
            )
        )

    def test_facing_matches_native_jar_probe_directions(self):
        from wakfu_server.combat_ordinary_authority import native_facing_front

        source = self.preview.actors[7]
        target = self.preview.actors[-7]
        source.position = (1, 0, 0)
        target.position = (0, 0, 0)
        native_front = (True, True, True, False, False, False, False, False)
        for direction, expected in enumerate(native_front):
            target.direction = direction
            self.assertEqual(native_facing_front(source, target), expected)
        target.direction = None
        with self.assertRaisesRegex(ValueError, "direction"):
            native_facing_front(source, target)

    def test_ordinary_cast_provider_real_effect_without_execution_callbacks(self):
        import random
        from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter

        class Timing:
            state = None
            stat = None

        # State/stat policies are unused by this native damage-only root.
        # Provider returns handlers directly, rather than fixture callbacks.
        timing = Timing()
        timing.state = lambda *a: None
        timing.stat = lambda *a: None
        self.preview.native_obstacle_cells = frozenset()
        self.preview.native_effect_uid_next = 200
        for actor in self.preview.actors.values():
            actor.effect_stats[87] = 0
        self.preview.actors[7].direction = 0
        self.preview.actors[-7].direction = 3
        self.preview.actors[8].direction = 3
        cast = ordinary_cast_authority(
            actors=self.authority, timing=timing, rng=random.Random(1), critical=False
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=self.authority, cast=cast)
        dispatcher, packets = self.f.factory(contexts=adapter.contexts())(
            self.preview, {"spell_id": 6266, "evaluation_level": 1}
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        dispatcher.execute(EffectInvocation(339526, 1, 7, -7, (1, 0, 0)))
        self.assertEqual(self.preview.actors[-7].hp, 15)
        self.assertEqual(self.preview.actors[8].hp, 33)  # BACK native multiplier.
        self.assertEqual(len(packets), 2)

    def test_ordinary_player_casts_between_both_duel_owners_have_native_facing(self):
        import random
        from wakfu_server.combat_ordinary_authority import (
            OrdinaryActorAuthority,
            ordinary_cast_authority,
        )
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        # Reclassify the fixture's opposing native actor as the second owned
        # player. Both actors begin at the exact direction encoded by their
        # own actor bootstrap, then attack each other through the ordinary
        # damage authority, which evaluates target facing.
        second = self.preview.actors[-7]
        second.controlled = True
        second.owner_id = 4
        first = self.preview.actors[7]
        first.direction = 0
        second.direction = 0
        authority = OrdinaryActorAuthority(
            characters={
                7: dict(id=7, breed=15, map_id=1134, level=1),
                -7: dict(id=-7, breed=15, map_id=1134, level=1),
            },
            monsters={8: dict(id=8, ref=5525)},
            decks={7: [6266], -7: [6266]},
            excluded_decks={7: [], -7: []},
        )

        class Timing:
            state = staticmethod(lambda *args: None)
            stat = staticmethod(lambda *args: None)

        self.preview.native_obstacle_cells = frozenset()
        self.preview.native_effect_uid_next = 200
        for actor in self.preview.actors.values():
            actor.effect_stats[87] = 0
        cast = ordinary_cast_authority(
            actors=authority,
            timing=Timing(),
            rng=random.Random(4),
            critical=False,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=authority, cast=cast)
        dispatcher, _packets = self.f.factory(contexts=adapter.contexts())(
            self.preview, {"spell_id": 6266, "evaluation_level": 1}
        )

        # Face each target toward the opposing actor using valid native
        # direction values. Both real ordinary damage invocations must pass
        # the same direction guard and apply their audited effect.
        first.direction, second.direction = 1, 5
        dispatcher.execute(EffectInvocation(339526, 1, 7, -7, (1, 0, 0)))
        second.direction, first.direction = 1, 5
        dispatcher.execute(EffectInvocation(339526, 1, -7, 7, (0, 0, 0)))
        self.assertLess(first.hp, 60)
        self.assertLess(second.hp, 20)


if __name__ == "__main__":
    unittest.main()
