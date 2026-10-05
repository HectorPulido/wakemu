import unittest
from unittest.mock import patch
from wakfu_server.equipment_stats import (
    bonuses,
    effective_character,
    combat_resources,
    CATALOG,
)
from wakfu_server.wire import proto_field
from wakfu_server.combat_actor_snapshot import build_player_snapshot
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_wire import arena
from wakfu_server.monsters import owned_instance


class FullSetTests(unittest.TestCase):
    def character(self):
        refs = list(range(2021, 2028))
        slots = [4, 7, 12, 13, 10, 0, 15]
        items = [
            dict(uid=1000 + i, character_id=7, reference=ref, quantity=1)
            for i, ref in enumerate(refs)
        ]
        sheet = b"".join(
            proto_field(10, proto_field(8, item["uid"]) + proto_field(16, slot))
            for item, slot in zip(items, slots)
        )
        return effective_character(
            dict(
                id=7,
                account_id=3,
                breed=11,
                level=20,
                hp=60,
                map_id=1134,
                x=0,
                y=0,
                z=0,
                inventory_items=items,
                builds={0: {"equipment": sheet.hex()}},
            )
        )

    def test_full_set_passive_stats_and_placement_snapshot(self):
        character = self.character()
        result = bonuses(character)
        self.assertEqual(result["unsupported"], [])
        self.assertEqual(
            {row["effect_id"] for row in result["active_effects"]}, {2817, 2931}
        )
        self.assertEqual(result["stats"], {1: 61, 2: 2, 9: 6, 20: 75, 8: 5, 27: 5})
        resources = combat_resources(character)
        cells = [(0, 0, 0), (1, 0, 0)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain["validated_cells"] = cells
        monster = owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0)
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=7,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=1,
        )
        actor = fight.actors[7]
        snapshot = build_player_snapshot(
            character,
            actor,
            wp_current=resources["wp"],
            wp_maximum=resources["wp"],
            running_effects=(),
        )
        snapshot.install(actor)
        self.assertEqual(actor.effect_stats[2], 8)
        self.assertEqual(actor.hp, 60)
        self.assertEqual(actor.max_hp, character["max_hp"])

    def test_unknown_passive_still_reports_failure(self):
        character = self.character()
        item = dict(CATALOG[2027])
        item["effects"] = list(item["effects"]) + [
            dict(
                id=1,
                generic=987,
                runner="unknown",
                values=[],
                stat_id=-1,
                parameter_count=0,
                target_mask=0,
                effect_criteria=False,
                has_triggers=False,
                native_variant=0,
                native_active_effect=False,
            )
        ]
        with patch.dict(CATALOG, {2027: item}):
            self.assertEqual(bonuses(character)["unsupported"][0]["effect_id"], 1)
