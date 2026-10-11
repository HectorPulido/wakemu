"""eYQ keeps the actual detached SELF recipient and creator orientation."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_combat_maximum_detached_constructor as fixture
from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_stat_handler import StatExecutionContext


class DetachedAreaConstructorTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DetachedMaximumConstructorTests()
        self.f.setUp()
        self.f.actor.direction = 3
        self.f.actor.position = (5, 7, 0)
        self.invocation = replace(self.f.f.invocation, cell=(5, 7, 0))
        self.definition = dict(
            reference=1477,
            type="HOUR",
            raw_bde=-1,
            effect_ids=[],
            entry_masks=[],
            exit_masks=[],
            native_shape_class="anD",
            native_hour_contract=True,
            properties=[],
            native_fight_properties=[],
            native_area_properties=[],
            native_type_id=0,
        )
        uid = iter((901, 902))
        self.handler = NativeEffectAreaHandler(
            self.f.f.fight,
            self.f.f.packets,
            action_id=1,
            allocate_uid=lambda: next(uid),
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
        )

    def apply(self, invocation=None, *, actor_delivery=True):
        with patch(
            "wakfu_server.combat_delivery_owners.owner_catalog",
            return_value={
                "effects": {"315": dict(runner="eYQ", bbA=actor_delivery, bbB=True)}
            },
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1477": self.definition},
        ), patch(
            "wakfu_server.combat_effect_area_geometry.registered_area_cells",
            return_value=frozenset({(5, 7)}),
        ) as cells:
            result = self.handler(
                dict(effect_class=315),
                {"parameters": [1477]},
                invocation or self.invocation,
            )
            return result, cells

    def test_detached_self_creates_area_with_actual_creator_orientation(self):
        with self.f.scope():
            result, geometry = self.apply()
        self.assertTrue(result)
        fight = self.f.f.fight
        row = fight.native_effect_areas[901]
        self.assertEqual((row["owner_id"], row["direction"]), (self.f.actor.id, 3))
        self.assertEqual(row["native_geometry_reference"], self.f.actor.position)
        geometry.assert_called_once_with(
            self.definition,
            self.invocation.cell,
            3,
            reference=self.f.actor.position,
        )
        self.assertNotIn(self.f.actor.id, fight.actors)
        self.assertEqual(len(self.f.f.packets), 1)

    def test_unscoped_actor_recipient_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unregistered.*recipient"):
            self.apply()
        self.assertEqual(self.f.f.fight.native_effect_areas, {})
        self.assertEqual(self.f.f.packets, [])

    def test_foreign_caster_does_not_grant_detached_recipient(self):
        with self.f.scope(), self.assertRaisesRegex(
            ValueError, "Unregistered.*recipient"
        ):
            self.apply(replace(self.invocation, caster_id=-7))
        self.assertEqual(self.f.f.packets, [])

    def test_owner_flags_still_reject_actor_recipient_inside_constructor(self):
        with self.f.scope(), self.assertRaisesRegex(ValueError, "owner flags"):
            self.apply(actor_delivery=False)
        self.assertEqual(self.f.f.packets, [])

    def test_unverified_context_remains_rejected(self):
        self.handler.context = lambda *args: StatExecutionContext(
            True,
            False,
            None,
            False,
            b"",
            None,
        )
        with self.f.scope(), self.assertRaisesRegex(ValueError, "execution authority"):
            self.apply()
        self.assertEqual(self.f.f.packets, [])


if __name__ == "__main__":
    unittest.main()
