"""A real companion sheet keeps native resource and HP gear across custody."""
import struct
import unittest

import test_companion_equipment_postgres as _fixture


class CompanionResourceReductionPostgresTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture.CompanionEquipmentPostgresTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.store = self.fixture.store

    def test_real_resource_and_hp_items_project_reload_and_clear_together(self):
        from wakfu_server import companion_equipment, companions
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.combat.combat_companions import native_stats
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values
        from wakfu_server.equipment import RULES

        f = self.fixture
        companion, _ = f._activate()
        # Both levels come from the supported native XP curve; the main
        # character's account level cap allows the breed-2828 companion to
        # reach 200. The selected item minimum is only 45.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200 WHERE id=%s", (f.character["id"],)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[200], f.character["id"]),
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[200], companion["id"]),
            )

        ap_item = f._grant(ref=9434, slot=1)
        hp_item = f._grant(ref=6583, slot=2)
        ap_slot = min(set(RULES[9434]["slots"]) & companion_equipment.SLOTS)
        hp_slot = min(set(RULES[6583]["slots"]) & companion_equipment.SLOTS)
        self.assertEqual(16, ap_slot)
        self.assertEqual(13, hp_slot)
        self.assertGreaterEqual(200, RULES[9434]["minimum_level"])
        before_row = dict(companion)
        owner = self.store.character(f.account, f.character["id"])
        baseline = native_stats(
            before_row["breed_ref"], 200, owner=owner, record=before_row
        )

        body = struct.pack(
            ">qhBbqBbq",
            companion["id"],
            2,
            1,
            hp_slot,
            hp_item["uid"],
            1,
            ap_slot,
            ap_item["uid"],
        )
        saved = companion_equipment.save(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            body,
            in_fight=False,
        )
        self.assertEqual(companion["id"], saved["companion_id"])
        self.assertIsNone(f._owned(ap_item["uid"]))
        self.assertIsNone(f._owned(hp_item["uid"]))

        with self.store.connection() as db:
            row = dict(
                db.execute(
                    "SELECT * FROM account_companions WHERE id=%s", (companion["id"],)
                ).fetchone()
            )
            entries = companion_equipment.hydrate_equipment(db, [row])[0][
                "equipment_entries"
            ]
        native_rows = native_npc_creation_values(row["breed_ref"], 200)
        from wakfu_server.equipment_resource_bonuses import from_native_values

        effects = companion_equipment.stat_bonuses(
            entries,
            owner,
            200,
            native_baseline={
                key: value["current"] for key, value in native_rows.items()
            },
            native_resource_baseline=from_native_values(native_rows),
        )
        projected = native_stats(
            row["breed_ref"], 200, equipment_entries=entries, owner=owner, record=row
        )
        # The empty sheet exposes the level-based emblem (+5 AP at this
        # level); once a physical sheet is present, the native NPC baseline
        # is used and the two actual 9434 operations (+1, eWO -1) net to 6.
        raw_ap = native_rows[2]["maximum"]
        self.assertEqual(
            raw_ap, effects["resource_projection"]["initial"][2]["maximum"]
        )
        self.assertEqual(raw_ap, projected["max_ap"])
        reductions = [
            step["receipt"]
            for step in effects["resource_projection"]["steps"]
            if step["receipt"]["family"] == "eWO"
        ]
        self.assertEqual(1, len(reductions))
        self.assertEqual(1, reductions[0]["amount"])
        self.assertEqual(
            reductions[0]["before"]["maximum"] - 1, reductions[0]["after"]["maximum"]
        )
        self.assertEqual(1, len(effects["hp_operations"]))
        self.assertEqual(15, effects["hp_operations"][0]["amount"])
        self.assertEqual(row["hp"], projected["hp"])
        self.assertEqual(row["max_hp"], projected["max_hp"])
        self.assertEqual(
            {ap_item["uid"], hp_item["uid"]},
            {entry["entry"]["item"]["uid"] for entry in entries},
        )

        # Hydrate the durable companion through a fresh Store and recompute
        # from the same native NPC baseline and exact owned item UIDs.
        reopened = f.reopen()
        with reopened.connection() as db:
            loaded = next(
                value
                for value in companions.collection(db, f.account)
                if value["id"] == companion["id"]
            )
            loaded_entries = companion_equipment.hydrate_equipment(db, [loaded])[0][
                "equipment_entries"
            ]
        reloaded = native_stats(
            loaded["breed_ref"],
            200,
            equipment_entries=loaded_entries,
            owner=owner,
            record=loaded,
        )
        self.assertEqual(projected, reloaded)
        self.assertEqual(
            {ap_item["uid"], hp_item["uid"]},
            {entry["entry"]["item"]["uid"] for entry in loaded_entries},
        )

        clear = struct.pack(">qhBbBb", companion["id"], 2, 0, hp_slot, 0, ap_slot)
        companion_equipment.save(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            clear,
            in_fight=False,
        )
        self.assertIsNotNone(f._owned(ap_item["uid"]))
        self.assertIsNotNone(f._owned(hp_item["uid"]))
        with self.store.connection() as db:
            cleared_row = dict(
                db.execute(
                    "SELECT * FROM account_companions WHERE id=%s", (companion["id"],)
                ).fetchone()
            )
            cleared_entries = companion_equipment.hydrate_equipment(db, [cleared_row])[
                0
            ]["equipment_entries"]
        restored = native_stats(
            cleared_row["breed_ref"],
            200,
            equipment_entries=cleared_entries,
            owner=owner,
            record=cleared_row,
        )
        self.assertEqual(baseline["max_ap"], restored["max_ap"])
        self.assertEqual(baseline["ap"], restored["ap"])
        self.assertEqual(baseline["max_hp"], restored["max_hp"])
        self.assertEqual(baseline["hp"], restored["hp"])
        self.assertEqual([], cleared_entries)
