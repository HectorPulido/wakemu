"""eYU keeps its actual oAP object after creation callbacks retire Qs membership."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_area import (
    NativeEffectAreaHandler,
    remove_owned_hour_area,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class DirectionalAreaRetirementTests(unittest.TestCase):
    def test_creation_callback_retirement_preserves_orientation_without_resurrection(
        self,
    ):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        fight = SimpleNamespace(
            id=77, actors={7: actor}, native_effect_areas={}, native_retained_records={}
        )
        packets, created = [], []
        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 700,
            allocate_area_uid=lambda: 900,
            context=lambda *_: StatExecutionContext(True, True, None, False, b"", None),
            container=lambda _: ({"container_type": 3}, 7),
        )

        def retire(row):
            created.append(row)
            self.assertEqual(len(packets), 1)  # Introduced before callbacks use it.
            self.assertEqual(row["uid"], 900)
            remove_owned_hour_area(fight, row["uid"])
            self.assertNotIn(900, fight.native_effect_areas)

        handler.on_created = retire
        definition = dict(
            type="HOUR",
            raw_bde=-1,
            effect_ids=[],
            entry_masks=[],
            exit_masks=[],
            native_shape_class="anD",
            native_area_properties=[],
            native_removal_masks=[],
            native_type_id=3,
        )
        with patch(
            "wakfu_server.combat_delivery_owners.owner_catalog",
            return_value={"effects": {"813": dict(runner="eYU", bbA=True, bbB=True)}},
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1605": definition},
        ), patch(
            "wakfu_server.combat_effect_area.registered_or_detached_actor",
            side_effect=lambda _fight, identity: fight.actors[identity],
        ), patch(
            "wakfu_server.combat_effect_area_geometry.registered_area_cells",
            return_value=((1, 0),),
        ):
            self.assertTrue(
                handler(
                    {"effect_class": 813},
                    {"parameters": [1605, 1]},
                    EffectInvocation(300001, 1, 7, None, (1, 0, 0)),
                )
            )
        self.assertEqual(created[0]["direction"], 1)
        self.assertEqual(created[0]["native_cells_xy"], ((1, 0),))
        self.assertEqual(fight.native_effect_areas, {})
        self.assertEqual(len(packets), 1)
