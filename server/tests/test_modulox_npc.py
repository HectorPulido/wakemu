import struct
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server import modulox_npc as mod
from wakfu_server.objectives import environmental_daily_selection as daily


class ModuloTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=42, account_id=7, level=120, map_id=9, instance_id=777, x=0, y=-6, z=4
        )
        self.bag = SimpleNamespace(
            is_owner=True, owns=lambda c: c["id"] == 42 and c["instance_id"] == 777
        )

    def test_original_actor_facing_has_a_native_idle_animation(self):
        import zipfile
        from pathlib import Path

        archive = (
            Path(__file__).resolve().parents[2]
            / "client/contents/animations/npcs/npcs.jar"
        )
        with zipfile.ZipFile(archive) as source:
            animation = source.read("144902070.anm")
        actor = mod.row(self.character)
        self.assertEqual(
            (actor["x"], actor["y"], actor["z"], actor["direction"]), (0, -5, 4, 1)
        )
        self.assertIn(f"{actor['direction']}_AnimStatique".encode(), animation)
        self.assertNotIn(b"0_AnimStatique", animation)
        self.assertTrue(mod._nearby(self.bag, self.character))

    def test_scene_scoped_to_owned_private_bag(self):
        fake_db = object()
        with patch.object(mod, "enabled", return_value=True), patch.object(
            mod.npc_world, "spawn", return_value=("spawn",)
        ) as spawn:
            self.assertEqual(
                mod.scene_packet(fake_db, self.bag, self.character), ("spawn",)
            )
            self.assertEqual(spawn.call_args.kwargs["enabled_actions"], (884,))
            self.assertIsNone(
                mod.scene_packet(
                    fake_db, self.bag, dict(self.character, instance_id=778)
                )
            )
            self.bag.is_owner = False
            self.assertIsNone(mod.scene_packet(fake_db, self.bag, self.character))

    def test_private_selection_allows_exterior_durable_position_only_with_session(self):
        char = self.character

        class FakeStore:
            def now(self):
                from datetime import datetime, timezone

                return datetime(2026, 11, 11, tzinfo=timezone.utc)

            def character(self, *args):
                return dict(char, map_id=527, instance_id=0)

        class DB:
            def execute(self, query, args=None):
                class Result:
                    def fetchone(self):
                        return None

                return Result()

        live = ("live", 9, 9, 777)
        with patch.object(daily, "_live", return_value=live), patch.object(
            daily, "_current", return_value=True
        ), patch.object(daily, "_lock_owner"):
            self.assertEqual(daily.select_for_character(DB(), FakeStore(), char), ())
            self.assertEqual(
                daily.select_for_character(
                    DB(), FakeStore(), char, bag_session=self.bag
                ),
                (),
            )

            # Both return no offers; only the authenticated bag reaches policy lookup.
            class CountDB(DB):
                called = False

                def execute(self, query, args=None):
                    self.called = True
                    return super().execute(query, args)

            db = CountDB()
            daily.select_for_character(db, FakeStore(), char)
            self.assertFalse(db.called)
            daily.select_for_character(db, FakeStore(), char, bag_session=self.bag)
            self.assertTrue(db.called)
            self.bag.is_owner = False
            db.called = False
            daily.select_for_character(db, FakeStore(), char, bag_session=self.bag)
            self.assertFalse(db.called)

    def test_native_offer_accepted_once_and_forged_choice_rejected(self):
        offer = dict(
            category_id=684, definition_id=100, version=1, utc_day=123, eligible=True
        )
        source = {
            "interpretation_policy": "mod",
            "daily_target_authority": {"category_id": 684},
        }
        node = {
            "id": 3972,
            "criteria": "",
            "choices": [
                {"id": 10124, "criteria": "x", "type": 5},
                {"id": 10023, "criteria": "", "type": 10},
            ],
        }

        class Store:
            @contextmanager
            def connection(self):
                yield object()

        store = Store()
        contract = SimpleNamespace(period=lambda n: 123)
        with patch.object(mod, "enabled", return_value=True), patch.object(
            mod, "_offers", return_value={684: offer}
        ), patch.object(mod.recurring, "synchronize", return_value=[]), patch.object(
            mod.storage, "load_locked", return_value={}
        ), patch.object(
            mod.recurring, "_load", return_value=(source, contract, None)
        ), patch.object(
            mod.recurring, "MODULOX_POLICY", "mod"
        ), patch(
            "wakfu_server.objectives.environmental_modulox_contracts.accept_category",
            return_value=True,
        ), patch.object(
            mod.recurring, "_now", return_value=123
        ), patch.object(
            mod.npc_dialogue, "catalog", return_value={"node_index": {3972: node}}
        ), patch.object(
            mod.storage, "record_event", return_value=True
        ) as event, patch.object(
            mod.recurring,
            "accept_from_receipt",
            return_value={"packets": [(13312, b"x")]},
        ) as accept:
            session, packets = mod.begin(
                store,
                7,
                9,
                self.character,
                mod.ACTOR,
                884,
                bag_session=self.bag,
                character_provider=lambda: self.character,
            )
            self.assertEqual(packets[-1][0], 12969)
            with self.assertRaises(ValueError):
                mod.choose(
                    store,
                    7,
                    9,
                    self.character,
                    session,
                    struct.pack(">ii", 3972, 10019),
                    bag_session=self.bag,
                )
            result = mod.choose(
                store,
                7,
                9,
                self.character,
                session,
                struct.pack(">ii", 3972, 10124),
                bag_session=self.bag,
            )
            self.assertEqual(result["packets"][0], (13312, b"x"))
            self.assertEqual(accept.call_args.args[3], 100)
            self.assertEqual(event.call_args.args[3]["choice_id"], 10124)
            with self.assertRaises(ValueError):
                mod.choose(
                    store,
                    7,
                    9,
                    self.character,
                    session,
                    struct.pack(">ii", 3972, 10124),
                    bag_session=self.bag,
                )


if __name__ == "__main__":
    unittest.main()
