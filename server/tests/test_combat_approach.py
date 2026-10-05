import unittest
from types import SimpleNamespace
from pathlib import Path
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_displacement import (
    NativeDisplacementHandler,
    displacement_geometry,
    displacement_additional,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation


def definition(parameters):
    return dict(
        effect_class=305,
        parameters=[v for p in parameters for v in (p, 0)],
        parameter_count=len(parameters),
        native_effect_flags=[17],
        native_execution_mode=2,
        native_definition_class="eVy",
        native_timing_definition=dict(ryE=0, ryF=0, ryH=0, ryI=0),
    )


class Authority:
    def __init__(self, props=()):
        self.props = set(props)

    def __call__(self, f, a):
        return SimpleNamespace(is_carried=False, native_instance_id=None)

    def properties(self, f, a):
        return self.props


class ApproachTests(unittest.TestCase):
    def fixture(self, props=(), obstacle=4):
        source = Actor(7, 0, (0, 0, 0), 50, 6, 3, 10, 1, 9, True)
        target = Actor(-7, 1, (obstacle, 0, 0), 20, 3, 3, 1, 1)
        source.physical_radius = target.physical_radius = 0
        fight = Fight(
            1,
            [source, target],
            {(x, 0, 0) for x in range(7)},
            {0: {source.position}, 1: {target.position}},
        )
        fight.ready(9)
        packets = []
        handler = NativeDisplacementHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 9,
            authority=Authority(props),
        )
        return fight, packets, handler

    def test_explicit_and_manhattan_geometry_matches_original(self):
        f, _, _ = self.fixture()
        for params, distance in [((), 4), ((3,), 3)]:
            geometry = displacement_geometry(
                definition(params), 1, source=f.actors[7], target=None, cell=(4, 0, 9)
            )
            self.assertEqual(
                (
                    geometry["actor"].id,
                    geometry["distance"],
                    geometry["vector"],
                    geometry["stop"],
                    geometry["loss_ap"],
                ),
                (7, distance, (1, 0), (4, 0), False),
            )

    def test_moves_until_occupied_target_without_collision_ap_loss(self):
        fight, packets, handler = self.fixture()
        self.assertTrue(
            handler(
                definition((4,)), None, EffectInvocation(123, 1, 7, None, (4, 0, 0))
            )
        )
        self.assertEqual(fight.actors[7].position, (3, 0, 0))
        self.assertEqual(fight.actors[7].ap, 6)
        self.assertEqual(len(packets), 1)
        self.assertEqual(fight.events[-1]["path"], [(1, 0, 0), (2, 0, 0), (3, 0, 0)])

    def test_stops_at_empty_target_without_overshoot(self):
        fight, packets, handler = self.fixture(obstacle=6)
        handler(definition((4,)), None, EffectInvocation(123, 1, 7, None, (2, 0, 9)))
        self.assertEqual(fight.actors[7].position, (2, 0, 0))

    def test_property71_blocks_without_mutation_or_packet(self):
        fight, packets, handler = self.fixture(props=(71,))
        self.assertFalse(
            handler(
                definition((4,)), None, EffectInvocation(123, 1, 7, None, (4, 0, 0))
            )
        )
        self.assertEqual(fight.actors[7].position, (0, 0, 0))
        self.assertEqual(packets, [])

    def test_inherited_native_path_codec(self):
        self.assertEqual(
            displacement_additional(305, path=[(1, 0, 0), (2, 0, 1)]).hex(),
            "b204100a060801100018000a06080210001801",
        )

    def test_common_authority_routes_and_accepts_native_cell_branch(self):
        import random
        from wakfu_server.combat_ordinary_authority import ordinary_cast_authority

        authority = ordinary_cast_authority(
            actors=SimpleNamespace(),
            timing=SimpleNamespace(state=None),
            rng=random.Random(0),
            critical=False,
        )
        invocation = EffectInvocation(123, 1, 7, None, (4, 0, 0))
        effect = definition((4,))
        self.assertEqual(
            authority.resolution(None, {}, effect, invocation).selection, "cell"
        )
        self.assertTrue(authority.cell_eligible(None, {}, effect, invocation))
