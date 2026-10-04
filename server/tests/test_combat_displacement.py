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
