import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_combat_qi_fight
from wakfu_server.combat_cast import _validate_target
from wakfu_server.combat_casting_context import NativeOwnedCastingContext
from wakfu_server.combat_native_los_ray import static_ray


class NativeSelfCastLosTests(unittest.TestCase):
    def setUp(self):
        fixture = test_combat_qi_fight.NativeQIFightLifecycleTests()
        self.fight, self.actor, _ = fixture.fixture(radii=(0, 0))
        fixture.initialize(self.fight)
        self.fight.ready(1)
        for actor in self.fight.actors.values():
            actor.native_los_height = 0
            actor.native_fight_properties = frozenset()
        self.rule = dict(
            minimum=0,
            maximum=2,
            linear=False,
            diagonal=False,
            linear_path=False,
            path_option=False,
            line_of_sight=True,
            free_cell=False,
            forbid_QI_P=False,
            allow_self=False,
            cast_criterion_native_present=False,
            roots=[143554],
        )
        authority = lambda f, a: SimpleNamespace(
            targeting={
                "is_eGj": True,
                "bEe": True,
                "is_Qq": False,
                "UNTARGETTABLE_BY_OTHER": False,
            },
            native_instance_id=1134,
        )
        authority.properties = lambda f, a: a.native_fight_properties
        self.adapter = SimpleNamespace(_actor=authority, actor_authority=authority)
        self.columns = {(x, y): ((0, 0, False),) for x in range(4) for y in range(4)}
        static_ray.cache_clear()
        self.addCleanup(static_ray.cache_clear)
        self.topology = patch(
            "wakfu_server.combat_native_los_ray.topology_columns",
            return_value=self.columns,
        )
        self.topology.start()
        self.addCleanup(self.topology.stop)
        self.legacy_calls = []

    def validate(self, cell):
        invocation = SimpleNamespace(caster_id=self.actor.id, cell=cell)
        casting = NativeOwnedCastingContext(
            self.adapter, self.fight, {}, invocation, None, self.rule
        )

        def query(rule, reference, level):
            casting.resolve_target_fighter()
            aligned = casting.alignment()
            return dict(
                result=casting.eligibility(),
                aligned=aligned,
                target_id=None if casting.target is None else casting.target.id,
            )

        return _validate_target(
            dict(target=cell),
            self.actor,
            self.fight,
            6,
            dict(ap=1, mp=0, wp=0),
            self.rule,
            [],
            20,
            lambda *args: self.legacy_calls.append(args) or False,
            1415,
            SimpleNamespace(native_casting_query=query),
        )

    def test_native_same_xyz_uses_shared_geometry_without_legacy_callback(self):
        self.assertEqual(self.validate(self.actor.position)["target_id"], self.actor.id)
        self.assertEqual(self.legacy_calls, [])

    def test_different_cell_requires_verified_native_qi_visibility(self):
        # The real Sf raster crosses cell1; its native mask256 blocks QI.h.
        with self.assertRaisesRegex(ValueError, "twG"):
            self.validate((2, 0, 0))
        self.fight.native_qi_snapshot["cell_masks"][1] &= ~256
        self.assertIsNone(self.validate((2, 0, 0))["target_id"])
        self.assertEqual(self.legacy_calls, [])

    def test_self_keeps_range_resources_and_free_cell_guards(self):
        self.rule["minimum"] = 1
        with self.assertRaisesRegex(ValueError, "twI"):
            self.validate(self.actor.position)
        self.rule["minimum"] = 0
        self.rule["free_cell"] = True
        with self.assertRaisesRegex(ValueError, "twT"):
            self.validate(self.actor.position)
        self.actor.ap = 0
        with self.assertRaisesRegex(ValueError, "resources"):
            self.validate(self.actor.position)
