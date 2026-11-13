from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Barrier, RLock, local

from wakfu_server.achievements.rii_orientation import damage_is_qualifying


class OrientationHitTests(unittest.TestCase):
    def setUp(self):
        self.fight = SimpleNamespace(
            actors={
                7: SimpleNamespace(position=(0, 0, 0)),
                -7: SimpleNamespace(position=(-1, 0, 0), direction=5),
            },
            rii_orientation_contract={"owner": 7, "target": -7},
        )

    def test_rear_damage_is_required(self):
        self.assertTrue(damage_is_qualifying(self.fight, 7, -7, 1))
        self.fight.actors[-7].direction = 1
        self.assertFalse(damage_is_qualifying(self.fight, 7, -7, 1))

    def test_wrong_actor_target_zero_damage_and_unbound_fight(self):
        self.assertFalse(damage_is_qualifying(self.fight, 8, -7, 1))
        self.assertFalse(damage_is_qualifying(self.fight, 7, -8, 1))
        self.assertFalse(damage_is_qualifying(self.fight, 7, -7, 0))
        self.fight.rii_orientation_contract = None
        self.assertFalse(damage_is_qualifying(self.fight, 7, -7, 1))

    def test_live_damage_event_contains_fact_only_for_bound_back_hit(self):
        from wakfu_server.combat_state import Actor, Fight

        attacker = Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True)
        target = Actor(200, 1, (3, 0, 0), 20, 4, 2, 20, 1)
        target.direction = 5
        fight = Fight(
            7,
            [attacker, target],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0)}, 1: {(3, 0, 0)}},
        )
        fight.rii_orientation_contract = {"owner": 100, "target": 200}
        fight.ready(1)
        fight.apply_damage(100, 200, 1)
        event = next(
            event for event in reversed(fight.events) if event["kind"] == "damage"
        )
        self.assertNotIn("rii_orientation_hit", event)
        self.assertEqual(fight.phase, "active")
        target.direction = 1
        with fight.effect_resolution():
            fight.apply_damage(100, 200, 1)
            self.assertEqual(fight.phase, "active")
        event = next(
            event for event in reversed(fight.events) if event["kind"] == "damage"
        )
        self.assertIs(event.get("rii_orientation_hit"), True)
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(fight.winner, attacker.team)
        self.assertEqual(target.hp, 18)
        self.assertFalse(any(e["kind"] == "death" for e in fight.events))

    def test_encounter_is_reserved_to_owner_but_unrelated_sacks_are_unaffected(self):
        from wakfu_server.achievements.rii_orientation import admit

        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {
                "character_id": 7,
                "payload": {
                    "kind": "reconstructed_rii_orientation_sack",
                    "owner": 7,
                    "actor_id": -7,
                    "ref": 5466,
                },
            }
        ]
        members = [{"id": -7, "ref": 5466}]
        self.assertTrue(admit(db, 7, members))
        with self.assertRaisesRegex(ValueError, "another player"):
            admit(db, 8, members)
        db.execute.return_value.fetchall.return_value = []
        self.assertTrue(admit(db, 8, members))

    def test_arena_policy_matches_exact_owned_orientation_receipt(self):
        from wakfu_server.achievements import rii_orientation

        db = Mock()
        actor = {"id": -7, "ref": 5466}
        db.execute.return_value.fetchone.return_value = {
            "payload": {
                "kind": "reconstructed_rii_orientation_sack",
                "owner": 7,
                "actor_id": -7,
                "ref": 5466,
            }
        }
        self.assertEqual(rii_orientation.owned_target(db, 7, [actor]), -7)
        self.assertIsNone(rii_orientation.owned_target(db, 8, [actor]))
        self.assertIsNone(
            rii_orientation.owned_target(db, 7, [{"id": -7, "ref": 2335}])
        )

    def test_simultaneous_accepts_check_availability_after_locks(self):
        from wakfu_server.achievements import rii_orientation

        thread_state = local()
        gate = Barrier(2)
        character = dict(
            id=7, account_id=2, map_id=1388, instance_id=0, x=0, y=-19, z=3
        )
        groups = Mock()
        groups.lock = RLock()
        groups.rows = []

        def available(*args):
            self.assertTrue(groups.lock._is_owned())
            self.assertTrue(getattr(thread_state, "owner_locked", False))
            return list(groups.rows)

        groups.available.side_effect = available
        groups.register_transaction.side_effect = (
            lambda db, m, i, g, members: groups.rows.append({"members": members})
        )
        db = Mock()
        db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(
                return_value={"found": 1}
                if "event_key=ANY" in sql and groups.rows
                else None
            )
        )
        store = Mock()
        store.connection.side_effect = lambda: nullcontext(db)
        store.lock_character.side_effect = lambda *a, **kw: setattr(
            thread_state, "owner_locked", True
        )
        store.character.return_value = character
        geometry = SimpleNamespace(
            outgoing={(0, -19, 3): ((1, -18, 3), (1, -19, 3), (-1, -19, 3))}
        )
        state = {"running": [5143], "objectives": []}

        def run():
            gate.wait()
            return rii_orientation.spawn(store, groups, 2, 1, character)

        with patch(
            "wakfu_server.combat_terrain.published_geometry", return_value=geometry
        ), patch(
            "wakfu_server.npc_world.load_scene",
            return_value=[{"x": 1, "y": -18, "z": 3}],
        ), patch(
            "wakfu_server.monsters.owned_instance",
            side_effect=lambda ref, level, actor, **kw: {
                "ref": ref,
                "id": actor,
                **{k: kw[k] for k in ("x", "y", "z")},
            },
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=10
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=state
        ), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(len(groups.rows), 1)
        self.assertEqual(
            tuple(groups.rows[0]["members"][0][k] for k in ("x", "y", "z")),
            (-1, -19, 3),
        )

    def test_only_authorized_hit_settles_and_sets_dialogue_flag(self):
        from wakfu_server.achievements import rii_orientation

        state = {
            "running": [5143],
            "completed": [],
            "objectives": [],
            "variables": {},
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }
        planned = {**state, "objectives": [10574]}
        flag = {
            "d": 5154,
            "native_class": "aJM",
            "aqb": True,
            "isVisible": False,
            "cjJ": [{"d": 10606, "ckc": "", "cke": "", "ckf": []}],
        }
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            {"data": {"native": {"d": 5143}}},
            {"data": {"native": flag}},
        ]
        fight = SimpleNamespace(
            id=42, rii_orientation_contract={"owner": 7, "target": -7}
        )
        store = SimpleNamespace(now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        event = {
            "kind": "damage",
            "source_id": 7,
            "target_id": -7,
            "rii_orientation_hit": True,
        }
        with patch("wakfu_server.achievements.service._owner"), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=state
        ), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as receipt, patch(
            "wakfu_server.achievements.storage.store"
        ) as save, patch(
            "wakfu_server.achievements.mission_progress.advance_objective",
            return_value=(planned, [], [10574], []),
        ), patch(
            "wakfu_server.achievements.wire.changes", return_value=[(1, b"ok")]
        ):
            self.assertEqual(
                rii_orientation.settle(
                    db,
                    store,
                    {"id": 7},
                    fight,
                    [{**event, "rii_orientation_hit": False}],
                ),
                [],
            )
            self.assertEqual(
                rii_orientation.settle(db, store, {"id": 7}, fight, [event]),
                [(1, b"ok")],
            )
            self.assertEqual(save.call_args.args[2]["objectives"], [10574, 10606])
            self.assertEqual(receipt.call_count, 2)

    def test_final_settlement_requires_owned_fight_and_propagates_errors(self):
        from wakfu_server.achievements import rii_orientation

        actor = SimpleNamespace(team=0)
        target = SimpleNamespace(team=1)
        event = {
            "kind": "damage",
            "source_id": 7,
            "target_id": -7,
            "rii_orientation_hit": True,
        }
        fight = SimpleNamespace(
            id=42,
            phase="finished",
            winner=0,
            actors={7: actor, -7: target},
            events=[event],
            rii_orientation_contract={"owner": 7, "target": -7},
        )
        members = [{"character_id": 7, "account_id": 2, "session_generation": 1}]
        monsters = [{"id": -7, "ref": 5466}]
        receipt = {
            "payload": {
                "kind": "reconstructed_rii_orientation_sack",
                "owner": 7,
                "actor_id": -7,
                "ref": 5466,
            }
        }
        participant = {"status": "finished", "fight_kind": "pve", "team": 0}
        db, store = Mock(), Mock()
        db.execute.return_value.fetchone.side_effect = [receipt, participant]
        store.character.return_value = {"id": 7}
        with patch.object(
            rii_orientation, "settle", return_value=[(123, b"done")]
        ) as settle:
            self.assertEqual(
                rii_orientation.settle_participants(
                    db, store, fight, members, monsters
                ),
                {2: [(123, b"done")]},
            )
            settle.assert_called_once_with(db, store, {"id": 7}, fight, [event])
        db.execute.return_value.fetchone.side_effect = [receipt, participant]
        with patch.object(
            rii_orientation, "settle", side_effect=ValueError("database failure")
        ):
            with self.assertRaisesRegex(ValueError, "database failure"):
                rii_orientation.settle_participants(db, store, fight, members, monsters)
        db.execute.return_value.fetchone.side_effect = [None]
        with patch.object(rii_orientation, "settle") as settle:
            self.assertEqual(
                rii_orientation.settle_participants(
                    db, store, fight, members, monsters
                ),
                {},
            )
            settle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
