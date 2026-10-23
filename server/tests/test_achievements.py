"""Qualified achievements consume exact identities and unit counter transitions."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.achievements import catalog, engine, rewards, service, storage, wire


def empty_state():
    return dict(
        variables={},
        objectives=[],
        running=[],
        completed=[],
        tracking=[],
        recent=[],
        completion_dates={},
    )


class AchievementTests(unittest.TestCase):
    def test_catalog_native_ids_sources_and_mission_exclusion(self):
        document = json.loads(
            Path(catalog.__file__).with_name("qualified_rules.json").read_text()
        )
        rules = catalog.validate(document)
        ledger = json.loads(
            Path(
                "docs/reports/achievements/installed-definition-ledger.json"
            ).read_text()
        )
        installed = {row["id"]: row for row in ledger["definitions"]}
        self.assertEqual(len(rules["definitions"]), 30)
        self.assertEqual(
            sum(len(row["objectives"]) for row in rules["definitions"].values()), 69
        )
        for path, expected in document["source_sha256"].items():
            self.assertEqual(
                hashlib.sha256(Path(path).read_bytes()).hexdigest(), expected
            )
        for identity, rule in rules["definitions"].items():
            self.assertNotEqual(installed[identity]["category_root"], 4)
            self.assertFalse(installed[identity]["literal_mission_dependency"])
            self.assertNotEqual(installed[identity]["criterion_aHe"].strip(), "False")
            self.assertEqual(
                {o["objective_id"] for o in rule["objectives"]},
                {o["objective_id"] for o in installed[identity]["objectives"]},
            )
            self.assertTrue(set(rule["prerequisites"]) <= set(rules["definitions"]))
        self.assertEqual(
            set(rules["breed_variables"]),
            {b["breed_id"] for b in document["variable_bindings"]},
        )

    def test_native_equality_is_latched_inside_multi_unit_batch_and_prerequisites_wait(
        self,
    ):
        definitions = {
            1: dict(
                objectives=[
                    dict(objective_id=11, variable_id=51, operator="==", threshold=1)
                ],
                prerequisites=[],
                rewards=[],
            ),
            2: dict(
                objectives=[
                    dict(objective_id=12, variable_id=51, operator="==", threshold=2)
                ],
                prerequisites=[1],
                rewards=[dict(d=7, aeV=2, ckl=[9])],
            ),
        }
        initial = empty_state()
        after, intents, objectives, completed = engine.advance(
            initial,
            dict(original_breeds=[39, 39, 39], completed_dungeon_id=None),
            dict(definitions=definitions, breed_variables={39: 51}),
            now_ms=1000,
        )
        self.assertEqual(initial, empty_state())
        self.assertEqual(after["variables"], {"51": 3})
        self.assertEqual(objectives, [11, 12])
        self.assertEqual(completed, [1, 2])
        self.assertEqual(len(intents), 1)
        replay, rewards_again, _, completed_again = engine.advance(
            after,
            dict(original_breeds=[]),
            dict(definitions=definitions, breed_variables={39: 51}),
            now_ms=2000,
        )
        self.assertEqual(rewards_again, [])
        self.assertEqual(completed_again, [])
        self.assertEqual(replay["completion_dates"], {"1": 1000, "2": 1000})

    def test_objective_milestone_waits_for_unfinished_parent(self):
        definitions = {
            1: dict(
                objectives=[dict(objective_id=11, dungeon_id=90)],
                prerequisites=[],
                rewards=[],
            ),
            2: dict(
                objectives=[
                    dict(objective_id=12, variable_id=51, operator="==", threshold=1)
                ],
                prerequisites=[1],
                rewards=[],
            ),
        }
        rules = dict(definitions=definitions, breed_variables={39: 51})
        after, _, _, completed = engine.advance(
            empty_state(), dict(original_breeds=[39]), rules, now_ms=1
        )
        self.assertEqual(after["objectives"], [12])
        self.assertEqual(completed, [])
        after, _, _, completed = engine.advance(
            after, dict(original_breeds=[], completed_dungeon_id=90), rules, now_ms=2
        )
        self.assertEqual(completed, [1, 2])

    def test_reward_parameter_types_and_native_arity_are_strict(self):
        self.assertEqual(rewards.validate(dict(aeV=5, ckl=[2021, 2])), (5, (2021, 2)))
        self.assertEqual(rewards.validate(dict(aeV=6, ckl=[100])), (6, (100,)))
        self.assertEqual(rewards.validate(dict(aeV=3, ckl=[9])), (3, (9,)))
        for row in (
            dict(aeV=6, ckl=[True]),
            dict(aeV=6, ckl=[1.0]),
            dict(aeV=6, ckl=[]),
            dict(aeV=3, ckl=[1, 2]),
            dict(aeV=3, ckl=[False]),
            dict(aeV=True, ckl=[1]),
            dict(aeV=2, ckl=[True]),
            dict(aeV=5, ckl=[1, 1.0]),
            dict(aeV=5, ckl=[1]),
            dict(aeV=99, ckl=[]),
            dict(aeV=2, ckl=[0]),
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                rewards.validate(row)

    def test_original_winning_roster_rejects_summons_duplicates_or_wrong_team(self):
        class DB:
            def execute(self, sql, params):
                return SimpleNamespace(
                    fetchone=lambda: dict(team=0, status="finished", fight_kind="pve")
                    if "combat_fight_participants" in sql
                    else None
                )

        player = SimpleNamespace(controlled=True, owner_id=7, team=0, hp=1)
        enemy = SimpleNamespace(controlled=False, team=1, hp=0)
        fight = SimpleNamespace(
            id=5,
            phase="finished",
            winner=0,
            actors={1: player, -2: enemy},
            native_summon_registrations={},
        )
        character = dict(id=1, account_id=7)
        self.assertEqual(
            service._event(DB(), character, fight, [dict(id=-2, ref=39)])[
                "original_breeds"
            ],
            [39],
        )
        for roster in (
            [dict(id=-2, ref=39)] * 2,
            [dict(id=1, ref=39)],
            [dict(id=-99, ref=39)],
        ):
            with self.assertRaises(ValueError):
                service._event(DB(), character, fight, roster)
        fight.native_summon_registrations = {-2: object()}
        with self.assertRaises(ValueError):
            service._event(DB(), character, fight, [dict(id=-2, ref=39)])

    def test_native_version5_section_and_absolute_notifications(self):
        state = empty_state()
        state.update(running=[238], variables={"51": 1}, objectives=[617])
        section = wire.section(state)
        self.assertEqual(int.from_bytes(section[:2], "big"), len(section) - 3)
        self.assertEqual(int.from_bytes(section[2:6], "big"), 5)
        self.assertEqual(section[-1], 0)
        self.assertEqual(
            [op for op, _ in wire.changes(1, empty_state(), state, [617], [], 1000)],
            [13312, 13295, 13832],
        )
        activation = wire.changes(1, empty_state(), state, [617], [], 1000)[0]
        import struct

        self.assertEqual(activation, (13312, struct.pack(">qi", 1, 238)))
        # Retained progress and reconnect snapshots do not reset/reannounce it.
        self.assertEqual(wire.changes(1, state, state, [], [], 1000), [])


class AchievementCombatAdapterTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        # Native settlement is mocked here; custom receipt authority is tested by PG integration.
        custom = patch(
            "wakfu_server.custom_tasks.adapters.original_kills",
            return_value=dict(updated=[], completed=[], replayed=False),
        )
        custom.start()
        self.addCleanup(custom.stop)

    def fixture(self):
        player = lambda owner, team=0: SimpleNamespace(
            controlled=True, owner_id=owner, team=team, hp=1
        )
        enemy = lambda hp=0: SimpleNamespace(controlled=False, team=1, hp=hp)
        fight = SimpleNamespace(
            id=1,
            phase="finished",
            winner=0,
            actors={
                1: player(7),
                2: player(7),
                3: player(8, 1),
                -1: enemy(),
                -2: enemy(5),
                -3: enemy(),
            },
            native_summon_registrations={-3: object()},
        )
        return fight, [
            dict(account_id=7, character_id=1),
            dict(account_id=7, character_id=2),
            dict(account_id=8, character_id=3),
        ]

    def test_owned_hero_packets_route_once_and_only_original_dead_enemies_credit(self):
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import combat_adapter

        fight, participants = self.fixture()
        store = Mock()
        store.character.side_effect = lambda owner, identity, db: dict(
            id=identity, account_id=owner
        )
        roster = [dict(id=i, ref=39) for i in (-1, -2, -3)]
        with patch.object(
            service, "settle", return_value=dict(packets=[(13295, b"owned")])
        ) as settle, patch(
            "wakfu_server.custom_tasks.adapters.original_kills",
            return_value=dict(replayed=False, updated=[], completed=[]),
        ):
            result = combat_adapter.settle_participants(
                object(), store, fight, participants, roster
            )
        self.assertEqual(
            result,
            dict(
                packets_by_owner={7: [(13295, b"owned"), (13295, b"owned")]},
                notification_receipts=[],
                custom_task_updates=[],
            ),
        )
        self.assertEqual(settle.call_count, 2)
        for call in settle.call_args_list:
            self.assertEqual(call.args[-1], [dict(id=-1, ref=39)])

    def test_rift_uses_durable_all_wave_facts_per_winner_and_ignores_current_roster(
        self,
    ):
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import combat_adapter, rift_facts

        fight, participants = self.fixture()
        fight.rift_wave_state = {"instance_id": 9}
        store = Mock()
        store.character.side_effect = lambda owner, identity, db: dict(
            id=identity, account_id=owner
        )
        facts = ({"id": -100, "ref": 39}, {"id": -101, "ref": 2})
        with patch.object(
            rift_facts, "load_locked", return_value=facts
        ) as load, patch.object(
            service, "settle", return_value=dict(packets=[])
        ) as settle, patch(
            "wakfu_server.custom_tasks.adapters.original_kills",
            return_value=dict(replayed=False, updated=[], completed=[]),
        ):
            result = combat_adapter.settle_participants(
                object(),
                store,
                fight,
                participants,
                [dict(id=True, ref="malformed-current-wave")],
            )
        self.assertEqual(
            result,
            dict(
                packets_by_owner={7: []},
                notification_receipts=[],
                custom_task_updates=[],
            ),
        )
        self.assertEqual(load.call_count, 2)
        self.assertEqual(settle.call_count, 2)
        self.assertEqual([call.args[2]["id"] for call in load.call_args_list], [1, 2])
        for call in load.call_args_list:
            self.assertEqual(call.args[-1], (1, 2))
        for call in settle.call_args_list:
            self.assertEqual(call.args[-1], facts)

    def test_duplicate_or_malformed_originals_reject_before_credit(self):
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import combat_adapter

        fight, participants = self.fixture()
        for roster in (
            [dict(id=-1, ref=39)] * 2,
            [dict(id=True, ref=39)],
            [dict(id=-1, ref=True)],
        ):
            with patch.object(service, "settle") as settle, self.assertRaises(
                ValueError
            ):
                combat_adapter.settle_participants(
                    object(), Mock(), fight, participants, roster
                )
            settle.assert_not_called()

    def test_withdrawn_winner_does_not_receive_credit(self):
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import combat_adapter

        fight, participants = self.fixture()
        participants[0]["withdrawn"] = True
        fight.actors[2].pve_withdrawn = True
        with patch.object(service, "settle") as settle:
            self.assertEqual(
                combat_adapter.settle_participants(
                    object(), Mock(), fight, participants, []
                ),
                dict(
                    packets_by_owner={},
                    notification_receipts=[],
                    custom_task_updates=[],
                ),
            )
        settle.assert_not_called()

    def test_custom_hook_follows_each_native_hero_settlement_and_returns_owned_metadata(
        self,
    ):
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import combat_adapter

        fight, participants = self.fixture()
        store = Mock()
        store.character.side_effect = lambda owner, identity, db: dict(
            id=identity, account_id=owner
        )
        calls = []
        outcomes = {
            1: dict(replayed=False, updated=["hunter"], completed=[]),
            2: dict(replayed=False, updated=["hunter"], completed=["hunter"]),
        }

        def native(db, store, character, fight, facts):
            calls.append(("native", character["id"]))
            return dict(packets=[])

        def custom(db, owner, identity, fight_id):
            calls.append(("custom", owner, identity, fight_id))
            return outcomes[identity]

        with patch.object(service, "settle", side_effect=native), patch(
            "wakfu_server.custom_tasks.adapters.original_kills", side_effect=custom
        ):
            result = combat_adapter.settle_participants(
                object(), store, fight, participants, [dict(id=-1, ref=39)]
            )
        self.assertEqual(
            calls,
            [("native", 1), ("custom", 7, 1, 1), ("native", 2), ("custom", 7, 2, 1)],
        )
        self.assertEqual(
            result["custom_task_updates"],
            [
                dict(account_id=7, character_id=1, result=outcomes[1]),
                dict(account_id=7, character_id=2, result=outcomes[2]),
            ],
        )
        self.assertEqual(result["packets_by_owner"], {7: []})
        self.assertEqual(result["notification_receipts"], [])


class AchievementTrackingTests(unittest.TestCase):
    def test_tracking_native_length_and_canonical_boolean(self):
        import struct

        self.assertEqual(
            service.decode_tracking(struct.pack(">iB", 238, 1)), (238, True)
        )
        self.assertEqual(
            service.decode_tracking(struct.pack(">iB", 238, 0)), (238, False)
        )
        for body in (
            b"",
            struct.pack(">iB", 238, 2),
            struct.pack(">iB", 0, 1),
            struct.pack(">iB", 238, 1) + b"x",
        ):
            with self.assertRaises(ValueError):
                service.decode_tracking(body)


class AchievementNotificationRoutingTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        # Native settlement is mocked here; custom receipt authority is tested by PG integration.
        custom = patch(
            "wakfu_server.custom_tasks.adapters.original_kills",
            return_value=dict(updated=[], completed=[], replayed=False),
        )
        custom.start()
        self.addCleanup(custom.stop)

    def test_each_hero_returns_only_its_settlement_key_without_acknowledging(self):
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import combat_adapter

        fight, participants = AchievementCombatAdapterTests().fixture()
        store = Mock()
        store.character.side_effect = lambda owner, identity, db: dict(
            id=identity, account_id=owner
        )
        with patch.object(
            service,
            "settle",
            side_effect=[
                dict(packets=[(13295, b"a")], notification_key="fight:1:a"),
                dict(packets=[(13295, b"b")], notification_key="fight:1:b"),
            ],
        ), patch.object(service, "notification_batches") as batches, patch.object(
            service, "acknowledge_notifications"
        ) as ack, patch(
            "wakfu_server.custom_tasks.adapters.original_kills",
            return_value=dict(replayed=False, updated=[], completed=[]),
        ):
            result = combat_adapter.settle_participants(
                object(), store, fight, participants, [dict(id=-1, ref=39)]
            )
        self.assertEqual(
            result["notification_receipts"],
            [
                dict(account_id=7, character_id=1, key="fight:1:a"),
                dict(account_id=7, character_id=2, key="fight:1:b"),
            ],
        )
        self.assertEqual(
            result["packets_by_owner"], {7: [(13295, b"a"), (13295, b"b")]}
        )
        batches.assert_not_called()
        ack.assert_not_called()
