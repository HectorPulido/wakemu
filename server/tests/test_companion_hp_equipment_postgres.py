"""Native HP-reduction equipment must reach actual sidekick projections."""
import struct
import unittest

import test_companion_equipment_postgres as _fixture


class CompanionHPItemPostgresTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture.CompanionEquipmentPostgresTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.store = self.fixture.store

    def test_real_admitted_hp_reduction_reaches_owned_companion_and_reconnect(self):
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server import companion_equipment, companions
        from wakfu_server.items.equipment import RULES
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values
        from wakfu_server.equipment_hp_lifecycle import NativeHPActor, OwnedEwoHPReplay

        f = self.fixture
        companion, _descriptor = f._activate()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=50 WHERE id=%s", (f.character["id"],)
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[50], companion["id"]),
            )
        gear = f._grant(20666, slot=1)
        equipment_slot = min(set(RULES[20666]["slots"]) & companion_equipment.SLOTS)
        saved = companion_equipment.save(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            f._save_body(companion["id"], gear["uid"], slot=equipment_slot),
            in_fight=False,
        )
        with self.store.connection() as db:
            row = dict(
                db.execute(
                    "SELECT * FROM account_companions WHERE id=%s", (companion["id"],)
                ).fetchone()
            )
            entries = companion_equipment.hydrate_equipment(db, [row])[0][
                "equipment_entries"
            ]
        owner = self.store.character(f.account, f.character["id"])
        level = 50
        native = native_npc_creation_values(row["breed_ref"], level)
        from wakfu_server.equipment_resource_bonuses import from_native_values

        effects = companion_equipment.stat_bonuses(
            entries,
            owner,
            level,
            native_baseline={
                identity: value["current"] for identity, value in native.items()
            },
            native_resource_baseline=from_native_values(native),
        )
        self.assertEqual(effects["unsupported"], [])
        self.assertEqual(len(effects["hp_operations"]), 1)
        expected = OwnedEwoHPReplay(
            NativeHPActor(
                raw_current=native[1]["current"],
                raw_maximum=native[1]["maximum"],
                raw_minimum=native[1]["minimum"],
            )
        )
        expected.reconcile(effects["hp_operations"])
        self.assertEqual(row["max_hp"], expected.actor.max_hp)
        self.assertEqual(row["hp"], expected.actor.hp)
        self.assertIsNone(f._owned(gear["uid"]))
        # A reload must preserve the same HP behavior, not merely the saved UI.
        reopened = f.reopen()
        with reopened.connection() as db:
            current = next(
                value
                for value in companions.collection(db, f.account)
                if value["id"] == companion["id"]
            )
        self.assertEqual(current["max_hp"], expected.actor.max_hp)
        self.assertEqual(saved["companion_id"], companion["id"])

        from wakfu_server.combat_companions import companion_projection, companion_actor

        current["level"] = level
        current["owner_character_id"] = owner["id"]
        source = companion_projection(current, owner)
        actor = companion_actor(source, 0)
        self.assertEqual(
            (actor.hp, actor.max_hp), (expected.actor.hp, expected.actor.max_hp)
        )
        self.assertEqual(
            actor.effect_base_maxima[1], expected.actor.effect_base_maxima[1]
        )
        self.assertEqual(
            actor.effect_hp_raw_current, expected.actor.effect_hp_raw_current
        )
        # Removing the physical source uses native inverse receipts, not a flat
        # subtraction or an equipment-specific exception.
        companion_equipment.save(
            self.store,
            f.account,
            f.generation,
            owner["id"],
            struct.pack(">qhBb", companion["id"], 1, 0, equipment_slot),
            in_fight=False,
        )
        with self.store.connection() as db:
            removed = dict(
                db.execute(
                    "SELECT * FROM account_companions WHERE id=%s", (companion["id"],)
                ).fetchone()
            )
        from wakfu_server.equipment_hp_lifecycle import OwnedEwoHPReplay

        restored = OwnedEwoHPReplay.restore(removed["equipment_hp_projection"])
        self.assertEqual(restored.receipts, {})
        self.assertEqual(
            (removed["hp"], removed["max_hp"]),
            (restored.actor.hp, restored.actor.max_hp),
        )
        self.assertIsNotNone(f._owned(gear["uid"]))

    def test_wounded_hp_inverse_and_terminal_recovery_preserve_native_checkpoint(self):
        from wakfu_server import companion_equipment, companions, fight_store
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.items.equipment import RULES
        from wakfu_server.equipment_hp_lifecycle import OwnedEwoHPReplay

        f = self.fixture
        companion, _ = f._activate()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=50 WHERE id=%s", (f.character["id"],)
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[50], companion["id"]),
            )
        item = f._grant(20666, slot=1)
        slot = min(set(RULES[20666]["slots"]) & companion_equipment.SLOTS)
        companion_equipment.save(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            f._save_body(companion["id"], item["uid"], slot=slot),
            in_fight=False,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_companions SET hp=max_hp-40 WHERE id=%s",
                (companion["id"],),
            )
            before = dict(
                db.execute(
                    "SELECT * FROM account_companions WHERE id=%s", (companion["id"],)
                ).fetchone()
            )
        expected = OwnedEwoHPReplay.restore(before["equipment_hp_projection"])
        raw = expected.actor.plain()
        raw["raw_current"] = before["hp"]
        from wakfu_server.equipment_hp_lifecycle import NativeHPActor

        expected = OwnedEwoHPReplay(NativeHPActor(**raw), expected.plain_receipts())
        # Exact inverse on a wounded actor differs from preserving wound debt.
        for key in tuple(expected.receipts):
            expected.remove(key)
        from wakfu_server.companion_hp_equipment import project

        baseline = expected.actor.plain()
        baseline["raw_current"] = baseline["raw_maximum"]
        inverse = project(before, baseline, ())
        self.assertEqual(inverse.actor.plain(), expected.actor.plain())
        self.assertEqual(inverse.receipts, {})
        companion_equipment.save(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            struct.pack(">qhBb", companion["id"], 1, 0, slot),
            in_fight=False,
        )
        # The ordinary empty-sheet emblem changes the baseline, so re-equip
        # before checking the combat recovery checkpoint for the same source.
        companion_equipment.save(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            f._save_body(companion["id"], item["uid"], slot=slot),
            in_fight=False,
        )
        companions.add_to_party(
            self.store,
            f.account,
            f.generation,
            f.character["id"],
            struct.pack(">q", companion["id"]),
        )
        fight_id = fight_store.create(
            self.store, f.account, f.generation, f.character["id"], team=0
        )
        with self.store.connection() as db:
            companions.enroll(
                db,
                fight_id,
                companion["id"],
                f.account,
                f.character["id"],
                f.generation,
                0,
            )
            row = dict(
                db.execute(
                    "SELECT * FROM account_companions WHERE id=%s", (companion["id"],)
                ).fetchone()
            )
            self.assertTrue(
                companions.settle_health(
                    db, self.store, fight_id, companion["id"], 0, row["max_hp"]
                )
            )
            self.assertFalse(
                companions.settle_health(
                    db, self.store, fight_id, companion["id"], 0, row["max_hp"]
                )
            )
            after = dict(
                db.execute(
                    "SELECT * FROM account_companions WHERE id=%s", (companion["id"],)
                ).fetchone()
            )
        restored = OwnedEwoHPReplay.restore(after["equipment_hp_projection"])
        self.assertEqual(after["hp"], after["max_hp"])
        self.assertEqual(restored.actor.hp, after["hp"])
        self.assertEqual(
            restored.actor.effect_hp_raw_current, restored.actor.effect_base_maxima[1]
        )
        self.assertEqual(len(restored.receipts), 1)
