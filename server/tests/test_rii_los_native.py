import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from datetime import datetime, timezone
from wakfu_server.achievements import rii_los_native


class NativeLosRosterTests(unittest.TestCase):
    def test_native_obstacle_refresh_is_owned_and_uses_retirement_callback(self):
        fight = SimpleNamespace(
            id=42,
            actors={-20: SimpleNamespace(position=(0, -13, 0), hp=75)},
            rii_los_lesson_contract={
                "owner": 3,
                "target": -20,
                "native_los_areas": True,
            },
            native_effect_areas={
                11: {"owner_id": 3, "reference": 1808},
                12: {"owner_id": 8, "reference": 1808},
                13: {"owner_id": 3, "reference": 1900},
            },
        )
        callback = Mock()
        dispatcher = SimpleNamespace(
            native_area_events=SimpleNamespace(area_removed=callback)
        )
        packets = []
        import sys

        remove = Mock()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.combat_effect_area": SimpleNamespace(
                    remove_owned_hour_area=remove
                ),
                "wakfu_server.combat_effect_area_codec": SimpleNamespace(
                    area_retirement=Mock()
                ),
            },
        ):
            self.assertEqual(
                rii_los_native.retire_before_cast(
                    fight,
                    dispatcher,
                    packets,
                    actor_id=3,
                    spell_id=7968,
                    target=(0, -13, 0),
                    action_id=5,
                ),
                1,
            )
            remove.assert_called_once_with(
                fight, 11, callbacks=dispatcher.native_area_events
            )
        self.assertEqual(packets, [])
        self.assertEqual(
            rii_los_native.retire_before_cast(
                fight,
                dispatcher,
                packets,
                actor_id=8,
                spell_id=7968,
                target=(0, -13, 0),
                action_id=5,
            ),
            0,
        )

    def test_single_sack_receipt_is_required(self):
        sack = {"id": -20, "ref": 5466}
        with patch(
            "wakfu_server.achievements.rii_owned_lesson.bind",
            return_value={"owner": 3, "target": -20, "hits": 0},
        ) as bind:
            result = rii_los_native.bind(object(), 3, [sack])
            self.assertEqual(
                result, {"owner": 3, "target": -20, "hits": 0, "native_los_areas": True}
            )
            bind.assert_called_once()
        with patch(
            "wakfu_server.achievements.rii_owned_lesson.bind", return_value=None
        ):
            self.assertIsNone(rii_los_native.bind(object(), 3, [sack]))

    def test_rejects_legacy_three_rocks_and_unrelated_monster(self):
        self.assertIsNone(
            rii_los_native.bind(
                object(), 3, [{"id": -20, "ref": 5466}, {"id": -21, "ref": 4528}]
            )
        )
        self.assertIsNone(rii_los_native.bind(object(), 3, [{"id": -20, "ref": 4528}]))

    def test_spawn_delegates_exact_lesson_definition(self):
        with patch(
            "wakfu_server.achievements.rii_owned_lesson.spawn", return_value=("scene",)
        ) as spawn:
            self.assertEqual(rii_los_native.spawn(1, 2, 3, 4, 5), ("scene",))
            self.assertEqual(spawn.call_args.args, (1, 2, 3, 4, 5, rii_los_native.LOS))

    def test_native_roster_default_and_legacy_fallback(self):
        from wakfu_server.achievements import rii_los_encounter

        with patch.dict(
            "os.environ", {"WAKFU_RII_NATIVE_LOS_ENABLED": "0"}
        ), patch.object(rii_los_encounter, "_spawn_legacy", return_value="legacy"):
            self.assertEqual(rii_los_encounter.spawn(1, 2, 3, 4, 5), "legacy")
        with patch.dict("os.environ", {}, clear=True), patch.object(
            rii_los_native, "spawn", return_value="native"
        ):
            self.assertEqual(rii_los_encounter.spawn(1, 2, 3, 4, 5), "native")

    def test_native_runtime_does_not_force_damage_rock_movement_or_four_hit_win(self):
        from wakfu_server.achievements import rii_los_encounter

        fight = SimpleNamespace(
            phase="active",
            actors={
                3: SimpleNamespace(team=0, hp=100),
                -20: SimpleNamespace(team=1, hp=50),
            },
            rii_los_lesson_contract={
                "owner": 3,
                "target": -20,
                "hits": 4,
                "native_los_areas": True,
            },
        )
        self.assertIsNone(
            rii_los_encounter.hit(
                fight,
                source_id=3,
                target_id=-20,
                effect_reference=361213,
                damage=25,
                actor_authority=object(),
                spell_id=7968,
            )
        )
        self.assertFalse(rii_los_encounter.move_one_rock(fight, [], action_id=1))
        self.assertFalse(rii_los_encounter.finish_if_qualified(fight))
        self.assertEqual(fight.actors[-20].hp, 50)

    def test_settlement_rejects_victory_with_living_sack(self):
        from wakfu_server.achievements import rii_owned_lesson

        fight = SimpleNamespace(
            id=42,
            phase="finished",
            winner=0,
            actors={
                3: SimpleNamespace(team=0, hp=100),
                -20: SimpleNamespace(team=1, hp=50),
            },
            rii_los_lesson_contract={
                "owner": 3,
                "target": -20,
                "hits": 4,
                "native_los_areas": True,
            },
        )
        db = Mock()
        result = rii_owned_lesson.settle_participants(
            db,
            object(),
            rii_los_native.LOS,
            fight,
            [],
            [{"id": -20, "ref": 5466}],
            contract_name="rii_los_lesson_contract",
        )
        self.assertEqual(result, {})
        db.execute.assert_not_called()

    def test_settlement_accepts_real_victory_without_synthetic_hit_count(self):
        from wakfu_server.achievements import (
            rii_owned_lesson,
            mission_progress,
            storage,
            wire,
        )

        fight = SimpleNamespace(
            id=42,
            phase="finished",
            winner=0,
            actors={
                3: SimpleNamespace(team=0, hp=100),
                -20: SimpleNamespace(team=1, hp=0),
            },
            rii_los_lesson_contract={
                "owner": 3,
                "target": -20,
                "hits": 0,
                "native_los_areas": True,
            },
        )
        db, store = Mock(), Mock()
        db.execute.return_value.fetchone.side_effect = [
            {"payload": rii_owned_lesson.payload(rii_los_native.LOS, 3, -20)},
            {"team": 0, "status": "finished", "fight_kind": "pve"},
            {"data": {"native": {"d": 5143}}},
        ]
        store.character.return_value = {"id": 3}
        store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        before = {"running": [5143], "objectives": []}
        after = {"running": [5143], "objectives": [10608]}
        member = {"character_id": 3, "account_id": 2, "session_generation": "session"}
        with patch.object(storage, "load_locked", return_value=before), patch.object(
            storage, "record_event", return_value=True
        ), patch.object(storage, "store"), patch.object(
            mission_progress, "advance_objective", return_value=(after, [], [10608], [])
        ), patch.object(
            wire, "changes", return_value=[(13832, b"ok")]
        ):
            result = rii_owned_lesson.settle_participants(
                db,
                store,
                rii_los_native.LOS,
                fight,
                [member],
                [{"id": -20, "ref": 5466}],
                contract_name="rii_los_lesson_contract",
            )
        self.assertEqual(result, {2: [(13832, b"ok")]})


if __name__ == "__main__":
    unittest.main()
