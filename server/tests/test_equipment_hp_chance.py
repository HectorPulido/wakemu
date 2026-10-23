"""Owned eWO equip draws survive failed branches, reload and native HP inverse."""
import json
import struct
import unittest
from unittest.mock import patch

from wakfu_server.equipment_hp_lifecycle import NativeHPActor, OwnedEwoHPReplay


def operation():
    return dict(
        source_uid=10150,
        effect_id=135401,
        effect_index=0,
        slot=13,
        amount=50,
        chance=1,
        restore_current=False,
        reduce_current=True,
    )


class EquipmentHpChanceTests(unittest.TestCase):
    def test_both_branch_boundaries_reorder_rebase_inverse_and_read_only_rejection(
        self,
    ):
        for roll in (0, 1, 99):
            with self.subTest(roll=roll):
                replay = OwnedEwoHPReplay(NativeHPActor(500, 1000))
                with self.assertRaisesRegex(ValueError, "owned equip transaction"):
                    replay.reconcile([operation()])
                calls = []
                replay.reconcile([operation()], rng=lambda n: calls.append(n) or roll)
                self.assertEqual(calls, [100])
                expected = (450, 950) if roll == 0 else (500, 1000)
                self.assertEqual((replay.actor.hp, replay.actor.max_hp), expected)
                restored = OwnedEwoHPReplay.restore(
                    json.loads(json.dumps(replay.checkpoint()))
                )
                self.assertTrue(restored.matches([operation()]))
                changed_slot = dict(operation(), slot=7)
                restored.reconcile(
                    [changed_slot], rng=lambda _: self.fail("rerolled retained item")
                )
                self.assertEqual(restored.plain_receipts()[0]["chance_roll"], roll)
                self.assertEqual(restored.plain_receipts()[0]["slot"], 7)
                self.assertEqual((restored.actor.hp, restored.actor.max_hp), expected)
                self.assertTrue(restored.matches([changed_slot]))
                desired = restored.resolved_operations(
                    [changed_slot], restored.plain_receipts()
                )
                rebased = OwnedEwoHPReplay(NativeHPActor(700, 1200))
                rebased.reconcile(desired)
                self.assertEqual(rebased.actor.max_hp, 1150 if roll == 0 else 1200)
                restored.reconcile([])
                self.assertEqual(
                    (restored.actor.hp, restored.actor.max_hp),
                    (450 if roll == 0 else 500, 1000),
                )
                restored.reconcile([operation()], rng=lambda _: 99)
                self.assertEqual(restored.plain_receipts()[0]["chance_roll"], 99)
        from wakfu_server.companion_hp_equipment import project

        with self.assertRaisesRegex(ValueError, "owned equip transaction"):
            project(None, dict(raw_current=500, raw_maximum=1000), [operation()])


from postgres_case import PostgresCase
import test_equipment_level_groups_postgres as _hero_fixture


class EquipmentHpChancePostgresTests(PostgresCase):
    _owner = _hero_fixture.EquipmentLevelGroupsPostgresTests._owner
    _grant = _hero_fixture.EquipmentLevelGroupsPostgresTests._grant
    _save = _hero_fixture.EquipmentLevelGroupsPostgresTests._save

    def test_real_owned_build_failed_and_applied_draw_reload_no_reroll_and_inverse(
        self,
    ):
        from wakfu_server import health_store
        from wakfu_server.equipment_hp_lifecycle import load
        from wakfu_server.equipment_stats import bonuses
        from wakfu_server.combat_equipment_root_roles import root_role
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )

        account, generation, owner = self._owner(100)
        item = self._grant(account, generation, owner, 10150, 0)
        for roll in (99, 0):
            with self.subTest(roll=roll):
                with patch("secrets.randbelow", return_value=roll) as draw:
                    equipped = self._save(account, generation, owner, item)
                self.assertEqual(draw.call_count, 1)
                with self.store.connection() as db:
                    before = load(db, owner["id"])
                self.assertEqual(before["receipts"][0]["chance_roll"], roll)
                self.assertEqual(
                    before["receipts"][0]["actual"], 50 if roll == 0 else 0
                )
                from wakfu_server.equipment_stats import CATALOG

                effect = next(
                    row for row in CATALOG[10150]["effects"] if row["id"] == 135401
                )
                roots = native_copied_equipment_catalog()["definitions"]["10150"][
                    "ordered_effects"
                ]
                self.assertEqual(
                    root_role(
                        10150,
                        next(row for row in roots if row["reference"] == 135401),
                        effect,
                    ),
                    "snapshot-owned-hp",
                )
                with patch(
                    "secrets.randbelow", side_effect=AssertionError("reload rerolled")
                ):
                    reopened = self.store.character(account, owner["id"])
                    self.assertEqual(
                        bonuses(reopened)["hp_operations"],
                        bonuses(equipped)["hp_operations"],
                    )
                    health_store.initialize(
                        self.store, account, generation, owner["id"]
                    )
                    self._save(account, generation, reopened, item)
                with self.store.connection() as db:
                    current = load(db, owner["id"])
                self.assertEqual(current["receipts"], before["receipts"])
                # Exercise inverse on a genuine wounded persisted owner.
                live = self.store.character(account, owner["id"])
                wounded = health_store.sync(
                    self.store,
                    account,
                    generation,
                    owner["id"],
                    live["hp"],
                    live["max_hp"] - 100,
                    coefficient=0,
                )
                removed = self._save(account, generation, wounded)
                # Ordinary stat changes preserve the existing wound. The eWO
                # inverse increases maximum by its actual receipt, without
                # restoring that part of current HP.
                actual = current["receipts"][0]["actual"]
                ordinary_delta = removed["max_hp"] - wounded["max_hp"] - actual
                self.assertEqual(
                    removed["hp"],
                    min(removed["max_hp"], max(0, wounded["hp"] + ordinary_delta)),
                )
                # The item's other ordinary stats may also alter maximum HP;
                # the native inverse receipt itself remains exactly fifty.
                self.assertEqual(
                    current["receipts"][0]["actual"], 50 if roll == 0 else 0
                )
                with self.store.connection() as db:
                    self.assertEqual(load(db, owner["id"])["receipts"], [])
                owner = removed


class CompanionHpChancePostgresTests(unittest.TestCase):
    def test_owned_companion_real_save_reload_ready_and_remove_reuse_failed_and_applied_draw(
        self,
    ):
        import test_companion_equipment_postgres as fixture
        from wakfu_server import companion_equipment, companions
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.equipment import RULES
        from wakfu_server.combat_companions import companion_projection, companion_actor

        f = fixture.CompanionEquipmentPostgresTests()
        self.addCleanup(f.doCleanups)
        f.setUp()
        companion, _ = f._activate()
        with f.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=%s", (f.character["id"],)
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[100], companion["id"]),
            )
        gear = f._grant(10150, slot=1)
        slot = min(set(RULES[10150]["slots"]) & companion_equipment.SLOTS)
        for roll in (99, 0):
            with self.subTest(roll=roll):
                with patch("secrets.randbelow", return_value=roll) as draw:
                    companion_equipment.save(
                        f.store,
                        f.account,
                        f.generation,
                        f.character["id"],
                        f._save_body(companion["id"], gear["uid"], slot=slot),
                        in_fight=False,
                    )
                self.assertEqual(draw.call_count, 1)
                reopened = f.reopen()
                with patch(
                    "secrets.randbelow",
                    side_effect=AssertionError("companion reload rerolled"),
                ):
                    with reopened.connection() as db:
                        row = next(
                            row
                            for row in companions.collection(db, f.account)
                            if row["id"] == companion["id"]
                        )
                    receipt = row["equipment_hp_projection"]["receipts"][0]
                    self.assertEqual(
                        (receipt["chance_roll"], receipt["actual"]),
                        (roll, 50 if roll == 0 else 0),
                    )
                    owner = reopened.character(f.account, f.character["id"])
                    row.update(level=100, owner_character_id=owner["id"])
                    actor = companion_actor(companion_projection(row, owner), 0)
                    self.assertEqual(actor.max_hp, row["max_hp"])
                    companion_equipment.save(
                        reopened,
                        f.account,
                        f.generation,
                        owner["id"],
                        f._save_body(companion["id"], gear["uid"], slot=slot),
                        in_fight=False,
                    )
                companion_equipment.save(
                    reopened,
                    f.account,
                    f.generation,
                    f.character["id"],
                    struct.pack(">qhBb", companion["id"], 1, 0, slot),
                    in_fight=False,
                )
                with reopened.connection() as db:
                    after = db.execute(
                        "SELECT equipment_hp_projection FROM account_companions WHERE id=%s",
                        (companion["id"],),
                    ).fetchone()
                self.assertEqual(after["equipment_hp_projection"]["receipts"], [])
