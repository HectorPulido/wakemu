"""A failed floor lesson must remain reachable when its group survives."""
import unittest
from contextlib import nullcontext
from threading import RLock
from unittest.mock import Mock, patch

from wakfu_server.achievements import (
    rii_area_encounter,
    rii_los_encounter,
    rii_owned_lesson,
    storage,
    rii_training_arena,
)
from wakfu_server import combat_monster_world


class TrainingRetryTests(unittest.TestCase):
    def test_owned_existing_encounters_are_reused_after_returning_to_floor(self):
        cases = (
            (
                rii_owned_lesson,
                10610,
                [10609],
                lambda store, groups, player: rii_owned_lesson.spawn(
                    store, groups, 5, "g", player, rii_owned_lesson.MOVEMENT
                ),
            ),
            (
                rii_owned_lesson,
                10611,
                [10610],
                lambda store, groups, player: rii_owned_lesson.spawn(
                    store, groups, 5, "g", player, rii_owned_lesson.STATES
                ),
            ),
            (
                rii_los_encounter,
                10608,
                [10576],
                lambda store, groups, player: rii_los_encounter.spawn(
                    store, groups, 5, "g", player
                ),
            ),
            (
                rii_area_encounter,
                10609,
                [10608],
                lambda store, groups, player: rii_area_encounter.spawn(
                    store, groups, 5, "g", player
                ),
            ),
        )
        for module, objective, prerequisites, spawn in cases:
            with self.subTest(objective=objective):
                db = Mock()
                player = {
                    "id": 8,
                    "account_id": 5,
                    "map_id": 1388,
                    "instance_id": 0,
                    "x": 0,
                    "y": -16,
                    "z": 0,
                    "_rii_training_objective": objective,
                }
                store = Mock()
                store.connection.return_value = nullcontext(db)
                store.character.return_value = player
                group = {"key": (1388, 0, 99), "members": [{"id": -42, "ref": 5466}]}
                groups = Mock(lock=RLock())
                groups.available.return_value = [group]
                with patch.object(
                    storage,
                    "load_locked",
                    return_value={"running": [5143], "objectives": prerequisites},
                ), patch.object(
                    module, "bind", return_value={"owner": 8}
                ) as bind, patch.object(
                    rii_training_arena, "mark_setup_ready_in_transaction"
                ) as ready, patch.object(
                    combat_monster_world, "spawn_group", return_value=b"existing"
                ) as packet:
                    self.assertEqual(spawn(store, groups, player), (12608, b"existing"))
                bind.assert_called_once()
                ready.assert_called_once_with(db, player, objective)
                packet.assert_called_once_with(group["members"], group_id=99)
                groups.register_transaction.assert_not_called()

    def test_retry_only_reuses_groups_with_matching_durable_receipts(self):
        area = [{"id": -n, "ref": 5466} for n in range(40, 44)]
        los = [{"id": -60, "ref": 5466}] + [
            {"id": -n, "ref": rii_los_encounter.ROCK_REFERENCE} for n in range(61, 64)
        ]
        payloads = {
            **{
                rii_area_encounter.KEY
                + str(-m["id"]): rii_area_encounter.payload(8, m["id"])
                for m in area
            },
            rii_los_encounter.LOS.key
            + "60": rii_owned_lesson.payload(rii_los_encounter.LOS, 8, -60),
            **{
                rii_los_encounter.ROCK_KEY
                + str(-m["id"]): rii_los_encounter.rock_payload(8, m["id"], -60)
                for m in los[1:]
            },
        }
        for module, objective, prerequisite, members in (
            (rii_area_encounter, 10609, 10608, area),
            (rii_los_encounter, 10608, 10576, los),
        ):
            with self.subTest(objective=objective):
                db = Mock()

                def execute(sql, args=()):
                    row = (
                        {"payload": payloads[args[1]]}
                        if (
                            sql.startswith("SELECT payload")
                            and args[0] == 8
                            and args[1] in payloads
                        )
                        else None
                    )
                    return Mock(fetchone=Mock(return_value=row))

                db.execute.side_effect = execute
                player = {
                    "id": 8,
                    "account_id": 5,
                    "map_id": 1388,
                    "instance_id": 0,
                    "x": 0,
                    "y": -16,
                    "z": 0,
                    "_rii_training_objective": objective,
                }
                store = Mock()
                store.connection.return_value = nullcontext(db)
                store.character.return_value = player
                groups = Mock(lock=RLock())
                groups.available.return_value = [
                    {"key": (1388, 0, 99), "members": members}
                ]
                with patch.object(
                    storage,
                    "load_locked",
                    return_value={"running": [5143], "objectives": [prerequisite]},
                ), patch.object(
                    rii_training_arena, "mark_setup_ready_in_transaction"
                ) as ready, patch.object(
                    combat_monster_world, "spawn_group", return_value=b"existing"
                ):
                    self.assertEqual(
                        module.spawn(store, groups, 5, "g", player),
                        (12608, b"existing"),
                    )
                ready.assert_called_once_with(db, player, objective)
                groups.register_transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
