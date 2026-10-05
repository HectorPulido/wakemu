from copy import deepcopy
import random
import unittest
import test_combat_effect_runtime as fixtures
from wakfu_server.combat_displacement import (
    cardinal_vector,
    displacement_additional,
    NativeDisplacementHandler,
)
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_effect_dispatch import (
    EffectInvocation,
    run_effect_transaction,
    UnsupportedEffectExecution,
)


class NativeDisplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeRuntimeFactoryTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.NativeRuntimeFactoryTests()
        self.fixture.setUp()
        self.preview = deepcopy(self.fixture.fight)
        self.preview.native_effect_uid_next = 200
        self.preview.walkable = {
            (x, y, 0) for x in range(-10, 11) for y in range(-10, 11)
        }
        self.preview.actors[8].position = (0, -5, 0)
        self.preview.actors[-7].position = (4, 0, 0)
        self.authority = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15)},
            monsters={8: dict(id=8, ref=5525), -7: dict(id=-7, ref=5525)},
            decks={7: []},
            excluded_decks={7: []},
        )
        self.effects = dict(self.fixture.effects)
        self.packets = []
        self.handler = NativeDisplacementHandler(
            self.preview,
            self.packets,
            action_id=1,
            allocate_uid=self.preview.allocate_effect_uid,
            authority=self.authority,
        )

    def execute(self, reference, *, target=-7, cell=(4, 0, 0), level=1):
        effect = self.effects[str(reference)]
        return self.handler(
            effect, None, EffectInvocation(reference, level, 7, target, cell)
        )

    def stair_fixture(self):
        self.preview.actors[7].position = (-15, -3, 0)
        self.preview.actors[-7].position = (-15, -5, -1)
        self.preview.actors[-7].native_los_height = 4
        self.preview.walkable = {(-15, -3, 0), (-15, -4, 0), (-15, -5, -1)}
        self.authority.monsters[-7]["map_id"] = 1134
        # Native short-form pull stops adjacent to caster (eXK/faz), unlike
        # the three-parameter direction5 fixture which deliberately pulls on.
        self.effects["326690"] = deepcopy(self.effects["326690"])
        self.effects["326690"]["parameters"] = self.effects["326690"]["parameters"][:4]
        self.effects["326690"]["parameter_count"] = 2

    def test_native_pull_climbs_verified_surface_without_flat_walk_edge(self):
        self.stair_fixture()
        self.preview.edges = frozenset()
        self.execute(326690, cell=(-15, -3, 0))
        self.assertEqual(self.preview.actors[-7].position, (-15, -4, 0))

    def test_native_height_transition_collision_preserves_position_uid_packets(self):
        self.stair_fixture()
        self.preview.actors[8].position = (-15, -4, 0)
        with self.assertRaisesRegex(ValueError, "collision"):
            self.execute(326690, cell=(-15, -3, 0))
        self.assertEqual(self.preview.actors[-7].position, (-15, -5, -1))
        self.assertEqual(self.preview.native_effect_uid_next, 200)
        self.assertEqual(self.packets, [])

    def test_later_collision_rolls_back_earlier_valid_height_transition(self):
        self.stair_fixture()
        effect = self.effects["326690"]
        effect["parameters"] += [5, 0]
        effect["parameter_count"] = 3
        with self.assertRaisesRegex(ValueError, "collision"):
            self.execute(326690, cell=(-15, -3, 0))
        self.assertEqual(self.preview.actors[-7].position, (-15, -5, -1))
        self.assertEqual(self.preview.native_effect_uid_next, 200)
        self.assertEqual(self.packets, [])

    def test_native_additional_exact_jar_bytes(self):
        self.assertEqual(
            displacement_additional(302, destination=(-2, 3, -1)).hex(),
            "7a1808feffffffffffffffff01100318ffffffffffffffffff01880201",
        )
        self.assertEqual(
            displacement_additional(300, path=[(2, 0, 0), (3, 0, 1)]).hex(),
            "b204100a060802100018000a06080310001801",
        )
        self.assertEqual(
            displacement_additional(
                422, source_original=(1, 2, 3), target_original=(4, 5, 6)
            ).hex(),
            "7a06080410051806ba0106080110021803",
        )

    def test_native_cardinal_sector_boundaries(self):
        # aBz.bp native tie (1,1) picks +X, not diagonal;2,1 likewise.
        self.assertEqual(cardinal_vector(1, 1), (1, 0))
        self.assertEqual(cardinal_vector(1, -1), (0, -1))
        self.assertEqual(cardinal_vector(-1, 1), (0, 1))

    def test_real_pull_catalog326690_direction5_toward_effect_cell(self):
        self.execute(326690, cell=(0, 0, 0))
        self.assertEqual(self.preview.actors[-7].position, (2, 0, 0))
        self.assertEqual(self.preview.actors[-7].mp, 3)
        self.assertEqual(self.packets[0][0], 12613)

    def test_real_push_catalog358000_away_caster(self):
        self.execute(358000)
        self.assertEqual(self.preview.actors[-7].position, (5, 0, 0))
        self.assertEqual(self.preview.actors[-7].ap, 6)

    def test_resolver_order_flags_preserve_displacement_and_unknown_rejection(self):
        effect = deepcopy(self.effects["358000"])
        for flag in (3, 5, 14, 26):
            with self.subTest(flag=flag):
                self.preview.actors[-7].position = (4, 0, 0)
                effect["native_effect_flags"] = [flag]
                self.handler(
                    effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0))
                )
                self.assertEqual(self.preview.actors[-7].position, (5, 0, 0))
                self.assertEqual(effect["native_effect_flags"], [flag])
        effect["native_effect_flags"] = [16]
        before = self.preview.actors[-7].position
        with self.assertRaisesRegex(ValueError, "Unhandled native displacement flags"):
            self.handler(effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0)))
        self.assertEqual(self.preview.actors[-7].position, before)

    def test_zone_preview_flag_changes_neither_geometry_nor_native_packet(self):
        results = []
        for flags in ([], [3]):
            self.setUp()
            effect = deepcopy(self.effects["358000"])
            effect["native_effect_flags"] = flags
            self.handler(effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0)))
            results.append(
                (
                    self.preview.actors[-7].position,
                    tuple(self.packets),
                    self.preview.native_effect_uid_next,
                )
            )
            self.assertEqual(effect["native_effect_flags"], flags)
        self.assertEqual(results[0], results[1])

    def test_real_caster_teleport_and_swap_without_actor_fabrication(self):
        self.execute(349548, target=None, cell=(2, 2, 0))
        self.assertEqual(self.preview.actors[7].position, (2, 2, 0))
        self.execute(349546)
        self.assertEqual(self.preview.actors[7].position, (4, 0, 0))
        self.assertEqual(self.preview.actors[-7].position, (2, 2, 0))

    def test_real_target_teleport_catalog351394(self):
        self.execute(351394, cell=(3, 3, 0))
        self.assertEqual(self.preview.actors[-7].position, (3, 3, 0))

    def test_real_move_away_catalog262489(self):
        self.execute(262489, target=7, cell=(2, 0, 0))
        self.assertEqual(self.preview.actors[7].position, (-2, 0, 0))

    def test_properties_and_collision_reject_without_mutation(self):
        actor = self.preview.actors[-7]
        actor.native_fight_properties = {11}
        self.assertFalse(self.execute(358000))
        self.assertEqual(self.packets, [])
        actor.native_fight_properties = set()
        self.preview.walkable.remove((5, 0, 0))
        with self.assertRaisesRegex(ValueError, "collision"):
            self.execute(358000)
        self.assertEqual(actor.position, (4, 0, 0))
        self.assertEqual(self.preview.native_effect_uid_next, 200)

    def test_factory_real_caster_teleport_empty_cell(self):
        cast = ordinary_cast_authority(
            actors=self.authority,
            timing=NativeEffectTimingProvider(self.fixture.states),
            rng=random.Random(1),
            critical=False,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=self.authority, cast=cast)
        factory = NativeEffectRuntimeFactory(
            effects=self.effects,
            state_catalog=self.fixture.states,
            characteristic_registry=self.fixture.registry,
            action_id=1,
            contexts=adapter.contexts(),
            displacement_authority=self.authority,
        )
        dispatcher, packets = factory(self.preview, {})
        dispatcher.execute(EffectInvocation(349548, 1, 7, None, (2, 2, 0)))
        self.assertEqual(self.preview.actors[7].position, (2, 2, 0))
        self.assertEqual(len(packets), 1)

    def test_later_unsupported_rollback_preserves_original_position_uid(self):
        effects = dict(self.effects)
        effects["900099"] = fixtures.definition(987654, [])
        cast = ordinary_cast_authority(
            actors=self.authority,
            timing=NativeEffectTimingProvider(self.fixture.states),
            rng=random.Random(1),
            critical=False,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=self.authority, cast=cast)
        factory = NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog=self.fixture.states,
            characteristic_registry=self.fixture.registry,
            action_id=1,
            contexts=adapter.contexts(),
            displacement_authority=self.authority,
        )
        with self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(
                self.preview,
                [
                    EffectInvocation(349548, 1, 7, None, (2, 2, 0)),
                    EffectInvocation(900099, 1, 7, -7, (4, 0, 0)),
                ],
                lambda p: factory(p, {})[0],
            )
        self.assertEqual(self.preview.actors[7].position, (0, 0, 0))
        self.assertEqual(self.preview.native_effect_uid_next, 200)


if __name__ == "__main__":
    unittest.main()
