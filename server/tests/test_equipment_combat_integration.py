import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server import health_store, builds, wire
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_health import persist


class EquipmentCombatIntegrationTests(unittest.TestCase):
    def test_saved_equipment_survives_selection_damage_return_and_unequip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "world.sqlite3")
            account = store.register("equipment-check", "local-test-password")["id"]
            char = store.create_character(account, "Equipment Check", breed=8)
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            with store.connection() as db:
                db.execute("UPDATE characters SET level=6 WHERE id=?", (char["id"],))
            char = health_store.initialize(store, account, generation, char["id"])
            base_max = char["max_hp"]
            with store.connection() as db:
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(?,?,?,?,?,?)",
                    (
                        1000,
                        char["id"],
                        2021,
                        1,
                        char["inventory_containers"][0]["uid"],
                        0,
                    ),
                )
            sheet = b"".join(
                wire.proto_field(t, v)
                for t, v in ((8, 0), (18, b"Equipment check"), (24, 6), (56, 0))
            )
            blobs = dict(
                sheet=sheet,
                equipment=wire.proto_field(
                    10, wire.proto_field(8, 1000) + wire.proto_field(16, 4)
                ),
                deck=b"",
                aptitudes=b"",
            )
            char = store.save_build(account, generation, char["id"], 0, blobs)
            self.assertEqual((char["hp"], char["max_hp"]), (base_max + 6, base_max + 6))
            char = health_store.initialize(store, account, generation, char["id"])
            self.assertEqual(char["max_hp"], base_max + 6)
            resources = combat_resources(char, wp=6)
            self.assertEqual(resources["ap"], 7)
            player = Actor(
                char["id"],
                0,
                (0, 0, 0),
                char["hp"],
                7,
                3,
                0,
                6,
                account,
                True,
                max_hp=char["max_hp"],
            )
            npc = Actor(-2, 1, (1, 0, 0), 10, 6, 3, 0, 1)
            fight = Fight(
                99,
                [player, npc],
                {(0, 0, 0), (1, 0, 0)},
                {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
                {((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (0, 0, 0))},
            )
            player.hp -= 9
            fight.phase = "finished"
            fight.winner = 0
            returned = persist(store, account, generation, char, fight)["character"]
            self.assertEqual(
                (returned["hp"], returned["max_hp"]), (base_max - 3, base_max + 6)
            )
            self.assertEqual(returned["builds"], char["builds"])
            removed = store.save_build(
                account,
                generation,
                char["id"],
                0,
                dict(blobs, equipment=builds.EMPTY_EQUIPMENT),
            )
            self.assertEqual(
                (removed["hp"], removed["max_hp"]), (base_max - 3, base_max)
            )
            self.assertEqual(combat_resources(removed, wp=6)["ap"], 6)
