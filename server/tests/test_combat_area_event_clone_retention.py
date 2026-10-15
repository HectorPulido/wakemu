"""Native 314 eYQ event clones bind their Qq but do not own the area lifetime."""

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class AreaEventCloneRetentionTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        fight = SimpleNamespace(id=77, actors={7: actor}, native_effect_areas={})
        effect_uid = iter((700, 702))
        area_uid = iter((900, 901))
        handler = NativeEffectAreaHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: next(effect_uid),
            allocate_area_uid=lambda: next(area_uid),
            context=lambda *_: StatExecutionContext(True, True, None, True, b"", None),
            container=lambda _inv: ({"container_type": 3}, 7),
        )
        handler.on_created = lambda _row: None
        return fight, handler

    def listener(self, fight, *, base_uid=70, reference=314559):
        fight.native_owned_group_effects = {
            base_uid: {
                "effect_class": 314,
                "invocation": {"reference": reference},
            }
        }

    def test_normal_retained_314_and_event_clone_have_distinct_area_owners(self):
        fight, handler = self.fixture()
        effect = {"effect_class": 314}
        values = {"parameters": [1605, 1]}
        original = EffectInvocation(314559, 1, 7, None, (0, 0, 0), base_uid=70)
        self.listener(fight)
        definition = {
            "type": "HOUR",
            "raw_bde": -1,
            "effect_ids": [],
            "entry_masks": [],
            "exit_masks": [],
            "native_shape_class": "anD",
            "native_area_properties": [],
            "native_removal_masks": [],
            "native_type_id": 3,
        }
        with patch(
            "wakfu_server.combat_delivery_owners.owner_catalog",
            return_value={"effects": {"314": {"runner": "eYQ", "bbA": False}}},
        ), patch(
            "wakfu_server.combat_delivery_owners.native_owner_flags",
            return_value=(False, True),
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1605": definition},
        ), patch(
            "wakfu_server.combat_effect_area.registered_or_detached_actor",
            side_effect=lambda _fight, actor_id: fight.actors[actor_id],
        ), patch(
            "wakfu_server.combat_effect_area_geometry.registered_area_cells",
            return_value=((0, 0),),
        ):
            self.assertTrue(handler(effect, values, original))
            normal_carrier = fight.native_owned_area_effects[700]
            self.assertEqual(normal_carrier["effect_class"], 314)
            self.assertEqual(normal_carrier["area_uid"], 900)

            clone = handler.prepare_activation(effect, values, original, clone_uid=701)
            self.assertEqual(clone.native_running_uid, 701)
            self.assertTrue(handler(effect, values, clone))
            self.assertEqual(fight.native_effect_areas[901]["effect_uid"], 701)
            self.assertEqual(fight.native_effect_areas[901]["effect_class"], 314)
            self.assertNotIn(701, fight.native_owned_area_effects)
            self.assertIn(700, fight.native_owned_area_effects)
            self.assertEqual(handler.prepared_event_clones, {})

    def test_unknown_listener_and_forged_or_canceled_clone_are_rejected(self):
        fight, handler = self.fixture()
        effect = {"effect_class": 314}
        invocation = EffectInvocation(314559, 1, 7, None, (0, 0, 0), base_uid=70)
        with self.assertRaisesRegex(ValueError, "subscribed eYQ original listener"):
            handler.prepare_activation(
                effect, {"parameters": [1605]}, invocation, clone_uid=701
            )

        self.listener(fight, reference=999)
        with self.assertRaisesRegex(ValueError, "subscribed eYQ original listener"):
            handler.prepare_activation(
                effect, {"parameters": [1605]}, invocation, clone_uid=701
            )

        self.listener(fight)
        with self.assertRaisesRegex(ValueError, "subscribed eYQ original listener"):
            handler.prepare_activation(
                effect, {"parameters": [1605]}, invocation, clone_uid=0
            )

        forged = replace(invocation, native_running_uid=999)
        with self.assertRaisesRegex(
            ValueError, "Missing prepared native eYQ event clone"
        ):
            with patch(
                "wakfu_server.combat_delivery_owners.owner_catalog",
                return_value={"effects": {"314": {"runner": "eYQ", "bbA": False}}},
            ), patch(
                "wakfu_server.combat_delivery_owners.native_owner_flags",
                return_value=(False, True),
            ):
                handler(effect, {"parameters": [1605]}, forged)

        clone = handler.prepare_activation(
            effect, {"parameters": [1605]}, invocation, clone_uid=701
        )
        handler.cancel_prepared(clone)
        with self.assertRaisesRegex(
            ValueError, "Missing prepared native eYQ event clone"
        ):
            with patch(
                "wakfu_server.combat_delivery_owners.owner_catalog",
                return_value={"effects": {"314": {"runner": "eYQ", "bbA": False}}},
            ), patch(
                "wakfu_server.combat_delivery_owners.native_owner_flags",
                return_value=(False, True),
            ):
                handler(effect, {"parameters": [1605]}, clone)


if __name__ == "__main__":
    unittest.main()
