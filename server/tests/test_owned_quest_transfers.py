"""Owned transfer authorization and shared-transaction orchestration."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from wakfu_server import owned_quest_transfers as transfers
from wakfu_server.quest_instance_configuration import reviewed_entry_gate


class QuestTransferDeclarationTests(unittest.TestCase):
    def test_exact_native_pair_and_modes_only(self):
        row = dict(
            schema="owned-quest-transfer-v1",
            source_id=23621,
            destination_id=4029,
            target_route_key="temple",
        )
        topology = dict(owned_quest_transfers=[row])
        body = struct.pack(">qiBi", 23621, 4029, 0, 2)
        self.assertEqual(transfers.selection(topology, body), row)
        self.assertIsNone(transfers.selection({}, body))
        self.assertIsNone(
            transfers.selection(topology, struct.pack(">qiBi", 23621, 2003, 0, 2))
        )
        for malformed in (b"", struct.pack(">qiBi", 23621, 4029, 2, 2)):
            with self.assertRaises(ValueError):
                transfers.selection(topology, malformed)
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            transfers.selection(dict(owned_quest_transfers=[row, row]), body)

    def test_empty_native_gate_requires_explicit_review_and_retains_exact_predicates(
        self,
    ):
        self.assertFalse(reviewed_entry_gate("", 2165, {}))
        self.assertTrue(reviewed_entry_gate("", 2165, dict(native_entry_criterion="")))
        for criterion in (
            "IsAchievementComplete(2165)",
            "True",
            "IsAchievementRunning(2165) or True",
        ):
            self.assertFalse(reviewed_entry_gate(criterion, 2165, {}))
            self.assertFalse(
                reviewed_entry_gate(
                    criterion, 2165, dict(native_entry_criterion=criterion)
                )
            )
        for criterion in ("IsAchievementRunning(2165)", "IsAchievementActive(2165)"):
            self.assertTrue(reviewed_entry_gate(criterion, 2165, {}))

    def test_story_target_requires_its_validator_and_exact_solo_policy(self):
        story = SimpleNamespace(policy=lambda configuration: configuration["declared"])
        config = dict(
            topology=dict(
                owned_story_controller={"schema": "owned-story-controller-v1"}
            ),
            declared=dict(maximum_members=1),
        )
        with patch.object(
            transfers.owned_quest_encounters, "policy", return_value=None
        ), patch.dict("sys.modules", {"wakfu_server.owned_story_controller": story}):
            self.assertEqual(transfers.target_policy(config), dict(maximum_members=1))
            self.assertIsNone(transfers.target_policy(dict(topology={})))
            for declared in (None, dict(maximum_members=True), dict(maximum_members=2)):
                with self.subTest(declared=declared):
                    config["declared"] = declared
                    with self.assertRaisesRegex(ValueError, "solo admission"):
                        transfers.target_policy(config)

    def test_story_route_registration_uses_same_strict_target_qualification(self):
        from wakfu_server.quest_instance_configuration import merge_runtime_routes

        route = SimpleNamespace(
            entry_map_id=747, entry_object_id=23621, destination_id=4029
        )
        config = dict(
            topology=dict(
                owned_story_controller={"schema": "owned-story-controller-v1"}
            ),
            route={},
        )
        story = SimpleNamespace(policy=lambda _: dict(maximum_members=1))
        with patch.object(
            transfers.owned_quest_encounters, "policy", return_value=None
        ), patch.dict(
            "sys.modules", {"wakfu_server.owned_story_controller": story}
        ), patch.object(
            transfers.dungeon_instances, "_load_routes", return_value={"temple": route}
        ):
            self.assertEqual(merge_runtime_routes({}, [config]), {"temple": route})
            story.policy = lambda _: dict(maximum_members=2)
            with self.assertRaisesRegex(ValueError, "solo admission"):
                merge_runtime_routes({}, [config])


class OwnedQuestTransferTests(unittest.TestCase):
    def setUp(self):
        self.body = struct.pack(">qiBi", 23621, 4029, 0, 2)
        self.origin = dict(
            id=7, account_id=3, map_id=747, instance_id=99, x=0, y=-18, z=-4
        )
        self.row = dict(
            schema="owned-quest-transfer-v1",
            source_id=23621,
            destination_id=4029,
            target_route_key="temple",
        )
        self.config = dict(topology=dict(owned_quest_transfers=[self.row]))
        self.native = dict(id=23621, map_id=747)
        self.route = SimpleNamespace(key="temple", start_map_id=887)
        self.resolved = dict(route=self.route, source=self.native)
        self.state = dict(objectives=[4298], completed=[])
        self.members = [dict(character_id=7, session_generation="lease")]
        self.social = [dict(character_id=7)]
        self.completed = True
        self.effects = []
        self.db = SimpleNamespace(execute=self.execute)
        self.connections = 0

        @contextmanager
        def connection():
            self.connections += 1
            saved = deepcopy(self.effects)
            try:
                yield self.db
            except Exception:
                self.effects[:] = saved
                raise

        self.store = SimpleNamespace(
            connection=connection,
            lock_character=lambda *_: None,
            character=lambda *_args, **_kwargs: dict(self.origin),
            now=lambda: datetime.now(timezone.utc),
        )
        patches = [
            patch.object(
                transfers.dungeon_runtime,
                "configuration_for_instance",
                return_value=(dict(party_id=55, instance_id=99), self.config),
            ),
            patch.object(
                transfers.owned_quest_encounters,
                "policy",
                return_value=dict(
                    quest_id=2165, victory_objective=4298, maximum_members=1
                ),
            ),
            patch.object(
                transfers.storage, "load_locked", side_effect=lambda *_: self.state
            ),
            patch.object(
                transfers.dungeon_transport,
                "resolve_request",
                return_value=self.resolved,
            ),
            patch.object(
                transfers.dungeon_runtime_config,
                "active_configuration",
                return_value=self.config,
            ),
            patch.object(
                transfers.dungeon_instances,
                "canonical_context_key",
                return_value="temple",
            ),
            patch("wakfu_server.player_parties._lock_members"),
            patch("wakfu_server.companions.controlled_count", return_value=0),
        ]
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def execute(self, sql, args):
        if sql.startswith("SELECT character_id,session_generation"):
            rows = self.members
        elif sql.startswith("SELECT character_id FROM player_party_members"):
            rows = self.social
        elif sql.startswith("SELECT status FROM dungeon_room_runs"):
            rows = [dict(status="completed" if self.completed else "active")]
        elif sql.startswith("SELECT id FROM player_parties"):
            rows = [dict(id=55)]
        elif sql.startswith("UPDATE dungeon_transition_outbox"):
            self.effects.append((sql, args))
            rows = []
        else:
            raise AssertionError(sql)
        return SimpleNamespace(
            fetchone=lambda: rows[0] if rows else None, fetchall=lambda: rows
        )

    def invoke(self, **kwargs):
        return transfers.transfer(
            self.store,
            3,
            "lease",
            7,
            self.body,
            source_allowed=kwargs.get("source_allowed", lambda *_: True),
            criterion_allowed=lambda *_: True,
            in_fight=lambda *_: False,
        )

    def test_departure_and_native_entry_share_connection_and_restore_true_source_event(
        self,
    ):
        def leave(*_args, **kwargs):
            self.assertIs(kwargs["_db"], self.db)
            self.assertEqual(
                kwargs["destination_for"](),
                {k: self.origin[k] for k in ("map_id", "x", "y", "z")},
            )
            self.effects.append("left")

        def enter(*_args, **kwargs):
            self.assertIs(kwargs["_db"], self.db)
            intermediate = dict(self.origin, instance_id=0)
            self.assertTrue(kwargs["source_allowed"](intermediate, dict(self.native)))
            self.assertFalse(
                kwargs["source_allowed"](dict(intermediate, x=1), dict(self.native))
            )
            self.assertFalse(
                kwargs["source_allowed"](intermediate, dict(self.native, id=1))
            )
            self.effects.append("entered")
            return dict(instance_id=100)

        with patch.object(
            transfers.dungeon_exit, "_leave", side_effect=leave
        ), patch.object(transfers.dungeon_transport, "_enter", side_effect=enter):
            self.assertEqual(self.invoke(), dict(instance_id=100))
        self.assertEqual(self.connections, 1)
        self.assertEqual(self.effects[:2], ["left", "entered"])
        self.assertIn("status='superseded'", self.effects[2][0])
        self.assertEqual(self.effects[2][1][1:], (99, 7))
        self.assertIn("source_instance_id=%s", self.effects[3][0])
        self.assertEqual(self.effects[3][1], (99, 100, 7, "lease"))

    def test_failed_native_target_admission_rolls_back_departure_and_pending_delivery(
        self,
    ):
        def leave(*_args, **kwargs):
            self.effects.extend(
                ["returned membership", "company cleanup", "pending exit"]
            )

        with patch.object(
            transfers.dungeon_exit, "_leave", side_effect=leave
        ), patch.object(
            transfers.dungeon_transport,
            "_enter",
            side_effect=ValueError("missing native key"),
        ):
            with self.assertRaisesRegex(ValueError, "missing native key"):
                self.invoke()
        self.assertEqual(self.effects, [])

    def test_group_stale_generation_and_unsettled_source_fail_before_departure(self):
        for case in ("group", "generation", "unsettled", "source"):
            with self.subTest(case=case):
                self.members = [dict(character_id=7, session_generation="lease")]
                self.social = [dict(character_id=7)]
                self.completed, self.state["objectives"] = True, [4298]
                if case == "group":
                    self.social.append(dict(character_id=8))
                elif case == "generation":
                    self.members[0]["session_generation"] = "stale"
                elif case == "unsettled":
                    self.completed = False
                with patch.object(transfers.dungeon_exit, "_leave") as leave:
                    with self.assertRaises(ValueError):
                        self.invoke(source_allowed=lambda *_: case != "source")
                    leave.assert_not_called()

    def test_source_quest_state_does_not_block_qualified_physical_transfer(self):
        for label, state in (
            ("questless", dict(objectives=[], completed=[], running=[])),
            ("active", dict(objectives=[], completed=[], running=[2165])),
            ("completed", dict(objectives=[4298], completed=[2165], running=[])),
        ):
            with self.subTest(state=label):
                self.state.update(state)
                with patch.object(
                    transfers.dungeon_exit,
                    "_leave",
                    side_effect=lambda *_a, **_k: {"instance_id": 0},
                ) as leave, patch.object(
                    transfers.dungeon_transport,
                    "_enter",
                    return_value={"instance_id": 100},
                ), patch.object(
                    transfers.storage,
                    "load_locked",
                    side_effect=AssertionError(
                        "physical travel must not inspect quest state"
                    ),
                ):
                    self.assertEqual(self.invoke(), {"instance_id": 100})
                    leave.assert_called_once()


class StoryAdmissionHookTests(unittest.TestCase):
    def test_declared_story_admits_before_native_payment_and_runtime_creation(self):
        from wakfu_server import dungeon_transport
        from wakfu_server import owned_story_controller
        from wakfu_server.application import owned_object_trial_dispatch

        for declared, trial_declared in ((False, False), (True, False), (False, True)):
            with self.subTest(declared=declared, trial_declared=trial_declared):
                events = []
                db = SimpleNamespace(
                    execute=lambda sql, *_: SimpleNamespace(
                        fetchone=lambda: (
                            {"present": 1}
                            if declared and "owned_story_controller" in sql
                            else {"present": 1}
                            if trial_declared and "owned_object_trials" in sql
                            else None
                        )
                    )
                )
                route = SimpleNamespace(key="temple", criterion="", template_id=1000887)
                resolved = dict(
                    route=route,
                    source=dict(id=23621),
                    difficulty_selection=dict(stasis_level=2, competitive=False),
                    native_destination=dict(cyW=1, item_reference=18747),
                    destination=dict(map_id=887, x=0, y=0, z=0, direction=1),
                )
                story = SimpleNamespace(
                    initialize=lambda *_a, **_k: events.append("story")
                )

                def create(*_args, **kwargs):
                    session = dict(
                        instance_id=100,
                        context_policy_version=1,
                        members=[7],
                        reused=False,
                        transition=dict(map_id=887, x=0, y=0, z=0),
                    )
                    kwargs["initialize_instance"](db, session)
                    return session

                with patch.object(
                    dungeon_transport, "resolve_request", return_value=resolved
                ), patch.object(
                    dungeon_transport.dungeon_instances,
                    "create_or_reuse",
                    side_effect=create,
                ), patch.object(
                    dungeon_transport.dungeon_instances,
                    "canonical_context_key",
                    return_value="temple",
                ), patch.object(
                    transfers.owned_quest_encounters,
                    "initialize",
                    side_effect=lambda *_a, **_k: events.append("owned"),
                ), patch(
                    "wakfu_server.dungeon_entry_payment.consume",
                    side_effect=lambda *_: events.append("payment"),
                ), patch(
                    "wakfu_server.special_instance_admission.initialize",
                    side_effect=lambda *_: events.append("special"),
                ), patch.object(
                    owned_story_controller,
                    "initialize",
                    side_effect=story.initialize,
                ), patch.object(
                    owned_object_trial_dispatch,
                    "initialize",
                    side_effect=lambda *_args, **_kwargs: events.append("trial"),
                ):
                    dungeon_transport._enter(
                        None,
                        3,
                        "lease",
                        7,
                        747,
                        struct.pack(">qiBi", 23621, 4029, 0, 2),
                        criterion_allowed=lambda *_: True,
                        source_allowed=lambda *_: True,
                        initialize_instance=lambda *_: events.append("runtime"),
                    )
                self.assertEqual(
                    events,
                    ["owned"]
                    + (["story"] if declared else [])
                    + ["payment", "special"]
                    + (["trial"] if trial_declared else [])
                    + ["runtime"],
                )

    def test_camp_profile_freezes_followup_reentry_and_exact_native_paid_story_transfer(
        self,
    ):
        import json
        from pathlib import Path
        from wakfu_server.combat_geometry import published_geometry
        from wakfu_server.monsters import reference
        from wakfu_server.quest_instance_configuration import compile_profile

        root = Path(__file__).parents[1] / "wakfu_server/maps/quest_encounter_profiles"
        profile = json.loads((root / "astrub-grambo-camp.json").read_text())
        walking = json.loads((root / profile["exploration_file"]).read_text())
        sources = {
            (s["map_id"], s["id"]): s
            for s in transfers.dungeon_transport.generic_transports._CATALOG
        }

        def compile(value):
            return compile_profile(
                value,
                geometry=published_geometry(747),
                exploration=walking,
                sources=sources,
                monster=reference(3249),
            )

        config = compile(profile)
        self.assertEqual(
            config["topology"]["owned_quest_encounter"]["reentry_quests"], [2166, 2170]
        )
        declared = config["topology"]["owned_quest_transfers"]
        self.assertEqual(len(declared), 1)
        self.assertEqual(
            (
                declared[0]["source_id"],
                declared[0]["destination_id"],
                declared[0]["target_route_key"],
            ),
            (23621, 4029, "quest-map-887-23621-4029"),
        )
        target = next(
            t
            for t in sources[(747, 23621)]["destinations"]
            if t["destination_id"] == 4029
        )
        self.assertEqual((target["item_reference"], target["cyW"]), (18747, 1))
        for case in ("duplicate", "same-map", "missing"):
            bad = deepcopy(profile)
            if case == "duplicate":
                bad["owned_quest_transfers"].append(deepcopy(declared[0]))
            elif case == "same-map":
                bad["owned_quest_transfers"][0].update(
                    source_id=21379, destination_id=1462
                )
            else:
                bad["owned_quest_transfers"][0]["destination_id"] = 999999
            with self.subTest(case=case), self.assertRaises(ValueError):
                compile(bad)


class ObjectTrialTransferPolicyTests(unittest.TestCase):
    def test_actual_excavation_story_transfer_requires_all_three_cures_and_settled_run(
        self,
    ):
        self.execute = OwnedQuestTransferTests.execute.__get__(self)
        OwnedQuestTransferTests.setUp(self)
        from wakfu_server import owned_story_controller, owned_story_reentry

        root = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
        selected = json.loads((root / "wild-estate-excavation-717.json").read_text())
        manifest = json.loads(
            (root / "wild-estate-excavation-717.instance.json").read_text()
        )
        native = json.loads(
            (root / "wild-estate-excavation-717.native.v1.json").read_text()
        )
        declaration = manifest["owned_transfers"][0]
        self.assertEqual(
            (declaration["source_id"], declaration["destination_id"]), (20568, 1426)
        )
        self.assertEqual(
            selected["native_links"][-1]["requires"], ["excavation-room-3-cured"]
        )
        source_config = dict(
            topology=dict(
                owned_story_controller=selected,
                owned_quest_transfers=manifest["owned_transfers"],
            )
        )
        target_config = dict(
            topology={"owned_story_controller": {"id": "target-owned"}}
        )
        self.config = source_config
        transfers.dungeon_runtime.configuration_for_instance.return_value = (
            dict(party_id=55, instance_id=99),
            source_config,
        )
        route = SimpleNamespace(key=declaration["target_route_key"], start_map_id=718)
        source = transfers.dungeon_transport.generic_transports.source(717, 20568)
        resolved = dict(route=route, source=source)
        body = struct.pack(">qiBi", 20568, 1426, 0, 2)
        self.origin.update(
            map_id=717, x=int(source["x"]), y=int(source["y"]), z=int(source["z"])
        )
        self.body = body
        steps = {
            "excavation-room-1-cured",
            "excavation-room-2-cured",
            "excavation-room-3-cured",
        }
        completed_steps = set(steps)
        departed, admitted = [], []

        def call():
            return transfers.transfer(
                self.store,
                3,
                "lease",
                7,
                body,
                source_allowed=lambda *_: True,
                criterion_allowed=lambda *_: True,
                in_fight=lambda *_: False,
            )

        def enter(*_args, **kwargs):
            kwargs["initialize_instance"](self.db, {"context_policy_version": 1})
            admitted.append(self.db)
            return {"instance_id": 100}

        with patch.object(
            transfers.owned_quest_encounters, "policy", return_value=None
        ), patch.object(
            owned_story_controller,
            "_scope",
            side_effect=lambda *_: (selected, completed_steps),
        ), patch(
            "wakfu_server.owned_story_mechanics.sources", return_value=native
        ), patch(
            "wakfu_server.owned_story_mechanics.executor", return_value=object()
        ), patch.object(
            owned_story_controller,
            "_settle",
            return_value={"applied": True, "packets": []},
        ), patch.object(
            transfers.dungeon_transport, "resolve_request", return_value=resolved
        ), patch.object(
            transfers.dungeon_runtime_config,
            "active_configuration",
            return_value=target_config,
        ), patch.object(
            transfers.dungeon_runtime_config,
            "pinned_configuration",
            return_value=target_config,
        ), patch.object(
            transfers.dungeon_instances, "canonical_context_key", return_value=route.key
        ), patch.object(
            transfers, "target_policy", return_value={"maximum_members": 1}
        ), patch.object(
            owned_story_reentry, "prepare"
        ), patch.object(
            transfers.dungeon_exit,
            "_leave",
            side_effect=lambda *_a, **_k: departed.append(self.db),
        ), patch.object(
            transfers.dungeon_transport, "_enter", side_effect=enter
        ), patch(
            "wakfu_server.player_parties._lock_members"
        ), patch(
            "wakfu_server.companions.controlled_count", return_value=0
        ):
            completed_steps.remove("excavation-room-3-cured")
            with self.assertRaisesRegex(ValueError, "earned native link frontier"):
                call()
            self.assertEqual((departed, admitted), ([], []))

            completed_steps.add("excavation-room-3-cured")
            self.completed = False
            with self.assertRaisesRegex(ValueError, "settled solo encounter"):
                call()
            self.assertEqual((departed, admitted), ([], []))

            self.completed = True
            self.assertEqual(call(), {"instance_id": 100})
            self.assertEqual(departed, [self.db])
            self.assertEqual(admitted, [self.db])

    def test_actual_zero_room_trial_transfer_shares_db_and_keeps_room_guard(self):
        from wakfu_server import owned_object_trials

        root = (
            Path(__file__).parents[1] / "wakfu_server/maps/owned_object_trial_profiles"
        )
        config = json.loads(
            (root / "huppermage-tiles-1025.configuration.json").read_text()
        )
        declaration = config["topology"]["owned_quest_transfers"][0]
        self.assertEqual(
            (declaration["source_id"], declaration["destination_id"]), (26174, 2351)
        )
        self.assertEqual(transfers.source_policy(config)[0], "object_trial")
        body = struct.pack(
            ">qiBi", declaration["source_id"], declaration["destination_id"], 0, 2
        )
        origin = dict(
            id=7,
            account_id=3,
            map_id=1025,
            instance_id=144115188075855999,
            x=-3,
            y=-6,
            z=-2,
        )
        route = SimpleNamespace(key=declaration["target_route_key"], start_map_id=1026)
        source = dict(id=declaration["source_id"], map_id=1025)
        resolved = dict(route=route, source=source)

        class TransferDB:
            def __init__(self):
                self.progress = None
                self.writes = []

            def execute(self, sql, args=()):
                if sql.startswith("SELECT id FROM player_parties"):
                    rows = [dict(id=55)]
                elif sql.startswith(
                    "SELECT character_id,session_generation FROM dungeon_instance_members"
                ):
                    rows = [dict(character_id=7, session_generation="lease")]
                elif sql.startswith("SELECT character_id FROM player_party_members"):
                    rows = [dict(character_id=7)]
                elif sql.startswith("SELECT status FROM dungeon_room_runs"):
                    rows = [] if self.progress is None else [dict(status=self.progress)]
                elif sql.startswith("UPDATE dungeon_transition_outbox"):
                    self.writes.append((sql, args))
                    rows = []
                else:
                    raise AssertionError("Unexpected transfer SQL: " + sql)
                return SimpleNamespace(
                    fetchone=lambda: rows[0] if rows else None,
                    fetchall=lambda: rows,
                )

        db = TransferDB()
        connections = []

        @contextmanager
        def connection():
            connections.append(db)
            yield db

        store = SimpleNamespace(
            connection=connection,
            lock_character=lambda *_: None,
            character=lambda *_a, **_k: dict(origin),
            now=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc),
        )
        left, entered = [], []

        def leave(*_args, **kwargs):
            left.append(kwargs["_db"])

        def enter(*_args, **kwargs):
            entered.append(kwargs["_db"])
            kwargs["initialize_instance"](kwargs["_db"], {"context_policy_version": 1})
            return dict(instance_id=144115188075856000)

        def call():
            return transfers.transfer(
                store,
                3,
                "lease",
                7,
                body,
                source_allowed=lambda actor, selected: actor["map_id"] == 1025
                and selected == source,
                criterion_allowed=lambda *_: True,
                in_fight=lambda *_: False,
            )

        with patch.object(
            transfers.dungeon_runtime,
            "configuration_for_instance",
            return_value=(dict(party_id=55, instance_id=origin["instance_id"]), config),
        ), patch.object(
            transfers.owned_quest_encounters, "policy", return_value=None
        ), patch.object(
            owned_object_trials,
            "_scope",
            return_value=(owned_object_trials.policy(config), origin),
        ) as scope, patch.object(
            transfers.dungeon_transport, "resolve_request", return_value=resolved
        ), patch.object(
            transfers.dungeon_runtime_config,
            "active_configuration",
            return_value=config,
        ), patch.object(
            transfers.dungeon_runtime_config,
            "pinned_configuration",
            return_value=config,
        ), patch.object(
            transfers.dungeon_instances, "canonical_context_key", return_value=route.key
        ), patch.object(
            transfers, "target_policy", return_value=dict(maximum_members=1)
        ), patch.object(
            transfers.dungeon_exit, "_leave", side_effect=leave
        ), patch.object(
            transfers.dungeon_transport, "_enter", side_effect=enter
        ), patch(
            "wakfu_server.player_parties._lock_members"
        ), patch(
            "wakfu_server.companions.controlled_count", return_value=0
        ):
            accepted = call()
            self.assertEqual(accepted, {"instance_id": 144115188075856000})
            scope.assert_called_once_with(db, store, origin)
            self.assertEqual(left, [db])
            self.assertEqual(entered, [db])
            self.assertEqual(connections, [db])
            self.assertEqual(len(db.writes), 2)

            # The zero-room trial itself qualifies completion. A room-run row,
            # even marked completed, is not a substitute for that policy.
            left.clear()
            entered.clear()
            db.progress = "completed"
            with self.assertRaisesRegex(ValueError, "settled solo encounter"):
                call()
            self.assertEqual(left, [])
            self.assertEqual(entered, [])

            # The owned trial scope rejects a foreign owner before departure.
            db.progress = None
            with patch.object(
                owned_object_trials, "_scope", side_effect=ValueError("foreign owner")
            ), patch.object(transfers.dungeon_exit, "_leave") as rejected_leave:
                with self.assertRaisesRegex(ValueError, "foreign owner"):
                    call()
                rejected_leave.assert_not_called()
