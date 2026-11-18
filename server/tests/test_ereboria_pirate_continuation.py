"""Focused Ereboria source-continuation admission and native movie boundary."""

from contextlib import nullcontext
from datetime import datetime, timezone
from copy import deepcopy
import json
import struct
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.achievements import (
    conversation,
    mission_toolkit_contract,
    source_quest_encounters as source,
)
from wakfu_server.application import source_quest_encounter_dispatch


class EreboriaPirateContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = source.registered_documents()
        cls.legacy = cls.documents[0]
        cls.ereboria = cls.documents[1]
        cls.ambush = next(
            row
            for row in cls.ereboria["bindings"]
            if row["id"] == "ereboria-5045-10389"
        )

    def test_registered_continuation_is_additive_and_keeps_native_intro_receipts(self):
        self.assertIs(self.legacy, source.document())
        self.assertEqual(len(self.legacy["bindings"]), 14)
        self.assertEqual(len(self.ereboria["bindings"]), 5)
        self.assertEqual(source.digest(self.legacy), source.digest(source.document()))
        self.assertEqual(
            {row["source"]["id"] for row in self.ereboria["bindings"]},
            {33688, 33691, 33690, 33689, 33716},
        )
        ambush = self.ambush
        self.assertEqual((ambush["quest_id"], ambush["objective_id"]), (5045, 10389))
        self.assertEqual(ambush["prelude_objective_id"], 10422)
        self.assertEqual(ambush["scenario"]["id"], 2515)
        self.assertEqual(ambush["scenario"]["opening"]["event"], 22110)
        self.assertEqual(ambush["scenario"]["opening"]["duration_ms"], 16000)
        self.assertEqual(ambush["scenario"]["actor_slots"], 6)
        self.assertEqual(sum(row["count"] for row in ambush["roster"]), 6)
        self.assertEqual(
            [row["reference"] for row in ambush["roster"]], [5374, 5373, 5375]
        )
        profile_path = (
            Path(__file__).parents[1]
            / "wakfu_server"
            / "achievements"
            / "mission_profiles"
            / "ereboria-pirate-continuation.json"
        )
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        native_5046 = next(
            row for row in self.ereboria["definitions"] if row["d"] == 5046
        )
        # The profile links from the separately published 5059 harbor chapter;
        # only the referenced link objective is needed for contract validation.
        native_5059 = {
            "d": 5059,
            "native_class": "aJM",
            "aqb": False,
            "cjJ": [
                {"d": identity, "ckc": "", "cke": "", "ckf": []}
                for identity in (10464, 10465, 10466)
            ],
        }
        goomy_continuation = source._read_document(
            source.SOURCE.with_name("ereboria-goomy-continuation.v1.json")
        )
        native_5051 = next(
            row for row in goomy_continuation["definitions"] if row["d"] == 5051
        )
        native_5052 = {
            "d": 5052,
            "native_class": "aJM",
            "aqb": False,
            "cjJ": [
                {"d": 10417, "ckc": "", "cke": "", "ckf": []},
                {
                    "d": 10418,
                    "ckc": "IsAchievementObjectiveComplete(10417)",
                    "cke": "",
                    "ckf": [],
                },
                {
                    "d": 10419,
                    "ckc": "IsAchievementObjectiveComplete(10418)",
                    "cke": "",
                    "ckf": [],
                },
            ],
        }
        native_5048 = {
            "d": 5048,
            "native_class": "aJM",
            "aqb": False,
            "cjJ": [
                {"d": 10400, "ckc": "", "cke": "", "ckf": []},
                {"d": 10401, "ckc": "", "cke": "", "ckf": []},
                {
                    "d": 10402,
                    "ckc": "",
                    "cke": "",
                    "ckf": [
                        {
                            "ckm": 'GetAchievementVariable("nbNimbosKilled") >= 10',
                            "ckn": [748],
                        }
                    ],
                },
                {"d": 10403, "ckc": "", "cke": "", "ckf": []},
            ],
        }
        native_5047 = {
            "d": 5047,
            "native_class": "aJM",
            "aqb": False,
            "cjJ": [
                {"d": 10411, "ckc": "", "cke": "", "ckf": []},
                {"d": 10412, "ckc": "", "cke": "", "ckf": []},
            ],
        }
        native_5049 = {
            "d": 5049,
            "native_class": "aJM",
            "aqb": False,
            "cjJ": [
                {"d": identity, "ckc": "", "cke": "", "ckf": []}
                for identity in (10405, 10429, 10430, 10406)
            ],
        }
        native_5050 = {
            "d": 5050,
            "native_class": "aJM",
            "aqb": False,
            "cjJ": [
                {"d": 10408, "ckc": "", "cke": "", "ckf": []},
                {"d": 10409, "ckc": "", "cke": "", "ckf": []},
            ],
        }
        validated = mission_toolkit_contract.validate(
            profile,
            [
                native_5046,
                native_5047,
                native_5048,
                native_5049,
                native_5050,
                native_5051,
                native_5052,
                native_5059,
            ],
        )
        self.assertEqual(validated["id"], "ereboria-pirate-continuation")

    def test_goomy_position_trigger_keeps_exact_polygon_and_real_native_winner_boundary(
        self,
    ):
        continuation = source._read_document(
            source.SOURCE.with_name("ereboria-goomy-continuation.v1.json")
        )
        trigger = next(
            row for row in continuation["bindings"] if row["source"]["id"] == 33740
        )
        search = next(
            row for row in continuation["bindings"] if row["source"]["id"] == 33743
        )
        from wakfu_server import native_interactive_activation

        self.assertEqual(trigger["scenario"]["id"], 2519)
        self.assertEqual(trigger["scenario"]["opening"]["event"], 22144)
        self.assertEqual(trigger["scenario"]["begin_event"], 22145)
        self.assertEqual(trigger["scenario"]["win_event"], 22146)
        self.assertEqual(trigger["prelude_objective_id"], 10479)
        self.assertEqual(
            {tuple(row) for row in trigger["activation_cells"]},
            {
                tuple(row)
                for row in native_interactive_activation.decode(trigger["source"])
            },
        )
        self.assertEqual(search["action"]["effects"][0]["action_reference"], 3410)
        self.assertEqual(search["approaches"], [[-15, -171, -50]])

    def test_ancient_struggle_uses_native_beer_payment_and_guarded_bbf_choices(self):
        contract_path = (
            Path(__file__).parents[1]
            / "wakfu_server"
            / "maps"
            / "native_quest_conversation_contracts.json"
        )
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        definitions, bindings = conversation.validate_rules(contract)
        (placement,) = [
            row for row in contract["placements"] if row.get("quest_id") == 5048
        ]
        berylbell = placement["row"]
        self.assertEqual(
            (
                berylbell["reference_id"],
                berylbell["action_ids"],
                berylbell["map_id"],
                berylbell["dialogue_root"],
            ),
            (5409, [1211], 1364, 5559),
        )
        self.assertEqual(placement["interaction_anchor"], {"x": 0, "y": -156, "z": -34})
        self.assertIn([5559, 12946, 5563], placement["graph"])
        for choice in (12945, 12946, 12947, 12948, 12949):
            self.assertTrue(
                any(
                    row["node_id"] == 5559 and row["choice_id"] == choice
                    for row in placement["choice_criteria"]
                )
            )
        self.assertEqual(
            [
                row
                for row in contract["turnins"]
                if (
                    row["reference_id"],
                    row["action_id"],
                    row["node_id"],
                    row["choice_id"],
                )
                == (5409, 1211, 5563, 12960)
            ],
            [
                {
                    "reference_id": 5409,
                    "action_id": 1211,
                    "node_id": 5563,
                    "choice_id": 12960,
                    "item_reference": 10332,
                    "quantity": 1,
                }
            ],
        )
        self.assertEqual(
            {
                (row.quest_id, row.objective_id)
                for key, row in bindings.items()
                if key[0] == 5409 and row.quest_id in (5048, 5049, 5050)
            },
            {(5048, 10401), (5048, 10403), (5049, 10406), (5050, 10409)},
        )
        self.assertTrue({5048, 5049, 5050} <= set(definitions))
        (goomy,) = [
            row for row in contract["placements"] if row.get("quest_id") == 5047
        ]
        self.assertEqual(
            {
                (row["quest_id"], row["objective_id"])
                for row in goomy["spoken_objectives"]
            },
            {(5051, 10416), (5052, 10419)},
        )
        profile_path = (
            Path(__file__).parents[1]
            / "wakfu_server"
            / "achievements"
            / "mission_profiles"
            / "ereboria-pirate-continuation.json"
        )
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        room_routes = {
            (row["objective_id"], row["event"]["reference"])
            for row in profile["bindings"]
            if row["quest_id"] == 5049 and row["event"]["kind"] == "transport_entered"
        }
        self.assertEqual(room_routes, {(10405, 4534), (10429, 4535), (10430, 4536)})

    def test_real_source_read_precedes_once_only_movie_and_suppression_has_no_delay(
        self,
    ):
        row = self.ambush
        character = dict(
            id=71,
            account_id=72,
            map_id=1358,
            instance_id=0,
            x=-35,
            y=133,
            z=-51,
        )
        db = Mock()
        store = SimpleNamespace(
            connection=lambda: nullcontext(db),
            character=Mock(return_value=character),
            now=lambda: datetime.fromtimestamp(100, timezone.utc),
        )
        advance_order = []

        def advance(_db, _store, _character, selected, **_kwargs):
            advance_order.append((selected["objective_id"], selected["mode"]))
            return []

        with (
            patch("wakfu_server.paid_containers._leased_owner"),
            patch("wakfu_server.environment_interactions._guard"),
            patch.object(source, "_owner"),
            patch.object(source, "_publication", return_value={}),
            patch.object(source, "_source_position"),
            patch.object(source, "_feedback", side_effect=lambda *_: []),
            patch.object(source, "_advance", side_effect=advance),
            patch.object(
                source, "_eligible", return_value=({}, self.ereboria["definitions"][0])
            ),
            patch.object(source.storage, "record_event", return_value=True),
            patch(
                "wakfu_server.achievements.tutorial_presentation_once.claim",
                side_effect=(True, False),
            ),
        ):
            first = source.interact(
                store,
                SimpleNamespace(lock=nullcontext()),
                72,
                "lease-a",
                character,
                struct.pack(">qHH", 33689, 0, 0),
                loaded=True,
                blocked=False,
            )
            second = source.interact(
                store,
                SimpleNamespace(lock=nullcontext()),
                72,
                "lease-a",
                character,
                struct.pack(">qHH", 33689, 0, 0),
                loaded=True,
                blocked=False,
            )

        self.assertEqual(advance_order, [(10422, "gather"), (10422, "gather")])
        self.assertEqual(first["packets"][0][0], 13411)
        self.assertEqual(
            struct.unpack(">BiiB", first["packets"][0][1]), (0, 22110, 2515, 0)
        )
        self.assertTrue(first["ticket"]["opening_shown"])
        self.assertEqual(first["ticket"]["due_ms"], 116250)
        self.assertFalse(second["ticket"]["opening_shown"])
        self.assertEqual(second["packets"], [])
        self.assertEqual(second["ticket"]["due_ms"], 100000)

    def test_only_a_durable_six_actor_victory_receipt_advances_the_native_ambush(self):
        row = self.ambush
        character = dict(id=81, account_id=82, map_id=1358, instance_id=0)
        group_key = [1358, 0, 556677]
        members = []
        for member in row["roster"]:
            for _ in range(member["count"]):
                members.append(dict(id=-101 - len(members), ref=member["reference"]))
        self.assertEqual(len(members), 6)
        payload = dict(
            schema=source.SCHEMA,
            owner=character["id"],
            binding=row["id"],
            source_sha256=source._source_digest(row),
            group_key=group_key,
            members=members,
            fight_id=909,
        )
        enemies = {
            actor["id"]: SimpleNamespace(
                controlled=False, team=1, hp=0, ref=actor["ref"]
            )
            for actor in members
        }
        fight = SimpleNamespace(
            id=909,
            phase="finished",
            winner=0,
            actors={
                character["id"]: SimpleNamespace(controlled=True, team=0),
                **enemies,
            },
            events=[dict(kind="death", actor_id=actor["id"]) for actor in members],
        )

        unowned_db = Mock()
        unowned_db.execute.return_value.fetchone.return_value = None
        with patch.object(source, "_advance") as advance:
            self.assertEqual(
                source.settle(unowned_db, object(), character, fight, members), []
            )
            advance.assert_not_called()

        scenario_db = Mock()
        scenario_db.execute.return_value.fetchone.return_value = dict(payload=payload)
        opcode, body = source.scenario_begin(scenario_db, character, row["id"], fight)
        tag, event, scenario_id, argument_count = struct.unpack_from(">BiiB", body)
        self.assertEqual(
            (opcode, tag, event, scenario_id, argument_count),
            (13411, 0, 22117, 2515, 9),
        )
        arguments = struct.unpack_from(">" + "q" * argument_count, body, 10)
        self.assertEqual(
            arguments,
            (
                group_key[2],
                *(actor["id"] for actor in members),
                fight.id,
                character["id"],
            ),
        )

        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            dict(payload=payload),
            dict(members=members, status="defeated"),
            dict(team=0, status="finished"),
        ]
        with patch.object(
            source, "_advance", return_value=[(13832, b"native objective")]
        ) as advance:
            packets = source.settle(db, object(), character, fight, members)
        self.assertEqual([opcode for opcode, _ in packets], [13411, 13832])
        self.assertEqual(
            struct.unpack(">BiiBq", packets[0][1]), (0, 22118, 2515, 1, group_key[2])
        )
        self.assertEqual(
            advance.call_args.kwargs["evidence"]["original_actor_ids"],
            sorted(actor["id"] for actor in members),
        )

    def test_pohl_source_rejects_a_different_or_missing_owned_dungeon_run(self):
        pohl = next(
            row for row in self.ereboria["bindings"] if row["source"]["id"] == 33716
        )
        character = dict(
            id=91,
            account_id=92,
            map_id=1369,
            instance_id=777,
            x=-10,
            y=-67,
            z=-15,
        )
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        with self.assertRaisesRegex(ValueError, "different original dungeon run"):
            source._source_position(
                character,
                pohl,
                struct.pack(">qHH", 33716, 0, 0),
                db=db,
                generation="lease",
            )

    def test_pohl_read_defers_dungeon_exit_only_for_eligible_unread_owned_objective(
        self,
    ):
        pohl = next(
            row for row in self.ereboria["bindings"] if row["source"]["id"] == 33716
        )
        document = source._document_for(pohl)
        definition = next(
            row for row in document["definitions"] if row["d"] == pohl["quest_id"]
        )
        published = {
            "schema": source.SCHEMA,
            "enabled": True,
            "source_sha256": source.digest(document),
            "native_revision": document["native_metadata_revision"],
            "sources": {
                source.digest(value): value["native_metadata_revision"]
                for value in source.registered_documents()
            },
        }
        scope = pohl["owned_dungeon"]
        character = {
            "id": 501,
            "account_id": 502,
            "map_id": pohl["source"]["map_id"],
            "instance_id": 503,
            "level": 36,
            "effective_level": 36,
            "inventory_items": [],
            "quest_items": [],
            "account_quest_items": [],
            "read_definition_id": scope["definition_id"],
            "read_entry_map_id": scope["entry_map_id"],
            "read_entry_source_id": scope["entry_source_id"],
            "read_destination_id": scope["destination_id"],
            "read_asset_map_id": pohl["source"]["map_id"],
        }
        state = {
            "running": [5046],
            "completed": [],
            "objectives": [10394],
            "active": [5046],
            "active_periods": {},
            "active_unknown": [],
            "variables": {},
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }

        class ReadOnlyDB:
            def __init__(self, *, members=True, publication=True):
                self.members = members
                self.publication = publication
                self.queries = []

            def execute(self, sql, params=None):
                self.queries.append(sql)
                if sql == "SELECT value FROM settings WHERE name=%s":
                    return SimpleNamespace(
                        fetchone=lambda: {"value": published}
                        if self.publication
                        else {"value": {"enabled": False}}
                    )
                if "SELECT c.*,i.definition_id AS read_definition_id" in sql:
                    return SimpleNamespace(
                        fetchall=lambda: [character] if self.members else []
                    )
                if "SELECT data FROM native_quest_metadata_definitions" in sql:
                    return SimpleNamespace(
                        fetchone=lambda: {"data": {"native": definition}}
                    )
                if "SELECT leader_id FROM account_hero_rosters" in sql:
                    return SimpleNamespace(fetchone=lambda: None)
                raise AssertionError(f"Unexpected read-only test query: {sql}")

        def check(*, selected_state=state, members=True, publication=True, owned=True):
            db = ReadOnlyDB(members=members, publication=publication)
            with patch.object(
                source.storage, "load_locked", return_value=selected_state
            ), patch.object(
                source,
                "_all_bindings",
                return_value=(pohl if owned else {**pohl, "owned_dungeon": None},),
            ), patch.object(
                source, "_eligible", wraps=source._eligible
            ) as eligible:
                result = source.defer_dungeon_completion(
                    db, object(), character["instance_id"]
                )
            return result, eligible.call_count, db.queries

        result, calls, queries = check()
        self.assertTrue(result)
        self.assertEqual(calls, 1)
        self.assertTrue(
            any("native_quest_metadata_definitions" in sql for sql in queries)
        )

        # Objective 10394 is the native prerequisite; the unread gather is
        # 10399. Each false condition is checked through the real _eligible guard.
        for label, kwargs in (
            (
                "quest not running",
                {"selected_state": {**state, "running": [], "active": []}},
            ),
            (
                "read already claimed",
                {"selected_state": {**state, "objectives": [10394, 10399]}},
            ),
            ("different owned run", {"members": False}),
            ("publication disabled", {"publication": False}),
            ("binding is not owned dungeon content", {"owned": False}),
        ):
            with self.subTest(case=label):
                result, _calls, _queries = check(**kwargs)
                self.assertFalse(result)

    def test_pohl_gather_honors_native_item_group_operands_and_payment_once(self):
        pohl = next(
            row for row in self.ereboria["bindings"] if row["source"]["id"] == 33716
        )
        character = {"id": 501, "account_id": 502, "inventory_items": []}
        db, store = object(), object()
        progress_packet = (13832, b"gather objective")

        # The published Pohl group is free: preserve its old behavior.
        with patch.object(
            source, "_advance", return_value=[progress_packet]
        ) as advance, patch(
            "wakfu_server.combat_inventory_date_conditions.complete_owned_item_quantity"
        ) as quantity, patch(
            "wakfu_server.native_generic_rewards._payment"
        ) as payment:
            free = source._finish_action(db, store, object(), character, pohl)
        self.assertEqual(free["packets"], [progress_packet])
        quantity.assert_not_called()
        payment.assert_not_called()
        self.assertNotIn("native_item_payment", advance.call_args.kwargs["evidence"])

        paid_row = deepcopy(pohl)
        paid_row["group"].update(cod=17829, coe=10, cof=True)
        updated = dict(character, inventory_items=[])
        debit_packet = (12470, b"debit")
        debit_receipt = [dict(uid=44, reference=17829, consumed=10)]
        with patch(
            "wakfu_server.combat_inventory_date_conditions.complete_owned_item_quantity",
            return_value=10,
        ) as quantity, patch(
            "wakfu_server.native_generic_rewards._payment",
            return_value=(updated, [debit_packet], debit_receipt),
        ) as payment, patch.object(
            source, "_advance", return_value=[progress_packet]
        ) as advance:
            paid = source._finish_action(db, store, object(), character, paid_row)
        self.assertEqual(paid["character"], updated)
        self.assertEqual(paid["packets"], [debit_packet, progress_packet])
        quantity.assert_called_once_with(character, (17829,))
        payment.assert_called_once_with(
            db, store, character, dict(group_cod=17829, group_coe=10)
        )
        self.assertEqual(
            advance.call_args.kwargs["evidence"]["native_item_payment"], debit_receipt
        )

        for consume, quantity_owned in ((True, 9), (False, 10)):
            with self.subTest(consume=consume, quantity=quantity_owned):
                row = deepcopy(paid_row)
                row["group"]["cof"] = consume
                with patch(
                    "wakfu_server.combat_inventory_date_conditions.complete_owned_item_quantity",
                    return_value=quantity_owned,
                ), patch(
                    "wakfu_server.native_generic_rewards._payment",
                    return_value=(character, [], debit_receipt),
                ) as payment, patch.object(
                    source, "_advance", return_value=[progress_packet]
                ) as advance:
                    if consume:
                        with self.assertRaisesRegex(ValueError, "actual native item"):
                            source._finish_action(db, store, object(), character, row)
                        payment.assert_not_called()
                        advance.assert_not_called()
                    else:
                        result = source._finish_action(
                            db, store, object(), character, row
                        )
                        payment.assert_not_called()
                        self.assertEqual(result["packets"], [progress_packet])
                        self.assertEqual(
                            advance.call_args.kwargs["evidence"]["native_item_payment"],
                            [],
                        )

        failing_advance = Mock(side_effect=RuntimeError("advance failed"))
        with patch(
            "wakfu_server.combat_inventory_date_conditions.complete_owned_item_quantity",
            return_value=10,
        ), patch(
            "wakfu_server.native_generic_rewards._payment",
            return_value=(updated, [debit_packet], debit_receipt),
        ) as payment, patch.object(
            source, "_advance", failing_advance
        ):
            with self.assertRaisesRegex(RuntimeError, "advance failed"):
                source._finish_action(db, store, object(), character, paid_row)
        payment.assert_called_once()
        failing_advance.assert_called_once()

    def test_native_movie_skip_callback_is_bound_to_its_issued_owner_and_event(self):
        row = self.ambush
        character = dict(
            id=111,
            account_id=112,
            map_id=1358,
            instance_id=0,
            x=-35,
            y=133,
            z=-51,
        )
        ticket = dict(
            schema=source.SCHEMA,
            token="issued-native-movie",
            owner=character["id"],
            account_id=character["account_id"],
            generation="lease-native-movie",
            binding=row["id"],
            source_sha256=source._source_digest(row),
            position={
                key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
            },
            due_ms=999999,
            opening_shown=True,
        )
        db = Mock()
        db.execute.return_value.fetchone.return_value = dict(payload=ticket)
        store = SimpleNamespace(
            connection=lambda: nullcontext(db),
            character=Mock(return_value=character),
        )
        with (
            patch("wakfu_server.paid_containers._leased_owner"),
            patch.object(source, "_source_position") as source_position,
            patch.object(source.storage, "record_event", return_value=True) as record,
        ):
            source.acknowledge_opening(
                store,
                character["account_id"],
                "lease-native-movie",
                character,
                ticket,
                22110,
            )
            source_position.assert_called_once()
            self.assertEqual(
                record.call_args.args[2],
                "quest-source-opening-ended:issued-native-movie",
            )
            with self.assertRaisesRegex(ValueError, "offered to this owner"):
                source.acknowledge_opening(
                    store,
                    character["account_id"],
                    "lease-native-movie",
                    dict(character, id=character["id"] + 1),
                    ticket,
                    22110,
                )
            with self.assertRaisesRegex(ValueError, "original end"):
                source.acknowledge_opening(
                    store,
                    character["account_id"],
                    "lease-native-movie",
                    character,
                    ticket,
                    22117,
                )
            self.assertEqual(record.call_count, 1)

    def test_native_clue_feedback_replays_only_its_original_running_script(self):
        from wakfu_server.exploration_artifact_actions import _script_packet

        feedback_rows = [
            row for row in self.ereboria["bindings"] if row.get("native_feedback")
        ]
        self.assertEqual(
            {
                reference
                for row in feedback_rows
                for reference in row["native_feedback"]
            },
            {3384, 3385, 3386, 3387, 3390},
        )
        for row in feedback_rows:
            quest_id = row["quest_id"]
            character = {"id": 701, "account_id": 702}
            db = Mock()
            with patch.object(
                source.storage,
                "load_locked",
                return_value={"running": [quest_id], "completed": [], "objectives": []},
            ), patch.object(source, "_hero", return_value=False):
                packets = source._feedback(db, character, row)
            reference = row["native_feedback"][0]
            self.assertEqual(
                packets,
                [_script_packet(character["id"], row["source"]["id"], reference)],
            )

            for running in ([], [quest_id + 100000]):
                with patch.object(
                    source.storage,
                    "load_locked",
                    return_value={
                        "running": running,
                        "completed": [],
                        "objectives": [],
                    },
                ), patch.object(source, "_hero", return_value=False):
                    self.assertEqual(source._feedback(db, character, row), [])

        # The publication rejects a fabricated feedback reference even if it
        # points to another known script. The guard must bind the exact type-1
        # native effect in the authored source action.
        malformed = deepcopy(self.ereboria)
        malformed["bindings"][0]["native_feedback"] = [999999]
        source_path = source.SOURCE.with_name("ereboria-pirate-ambush.v1.json")
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / source_path.name
            candidate.write_text(json.dumps(malformed))
            source._read_document.cache_clear()
            try:
                with self.assertRaisesRegex(ValueError, "exact native type1 effect"):
                    source._read_document(candidate)
            finally:
                source._read_document.cache_clear()

    def test_completed_movie_rebinds_the_selected_position_at_its_native_endpoint(self):
        character = dict(
            id=101,
            account_id=102,
            map_id=1358,
            instance_id=0,
            x=-35,
            y=133,
            z=-51,
        )
        db = Mock()
        db.execute.return_value.rowcount = 1
        with patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(cells={(-42, 126, -51)}),
        ):
            packet = source._finish_opening(db, character, self.ambush)
        self.assertEqual(character["x"], -42)
        self.assertEqual((character["y"], character["z"]), (126, -51))
        self.assertEqual(
            packet,
            (13530, struct.pack(">qiihBi", 101, -42, 126, -51, 7, -1)),
        )

        state = SimpleNamespace(
            account_id=102, generation="lease", character=dict(id=101)
        )
        timeline = []

        class PositionRegistry:
            def rebind_selected(self, *args):
                timeline.append(("rebind", args))

        positions = PositionRegistry()
        world = SimpleNamespace(
            update=lambda *args, **kwargs: timeline.append(("world", args, kwargs))
        )
        runtime = SimpleNamespace(
            POSITIONS=positions,
            WORLD=world,
            Movement=lambda position: timeline.append(("movement", position))
            or dict(position),
        )
        session = SimpleNamespace(
            state=state,
            runtime=runtime,
            mark_static_sync_pending=lambda: timeline.append(("static_sync",)),
            publish_settled_quest_packets=lambda packets: timeline.append(
                ("publish", packets)
            ),
        )
        source_quest_encounter_dispatch._apply(
            session,
            dict(
                character=character,
                relocated=True,
                packets=[packet],
                target=None,
                ticket=None,
            ),
        )
        self.assertEqual(state.position, {"x": -42, "y": 126, "z": -51})
        self.assertEqual(state.movement_state, {"x": -42, "y": 126, "z": -51})
        self.assertEqual(timeline[0][0], "movement")
        self.assertEqual(timeline[1], ("rebind", (102, "lease", 101)))
        self.assertEqual(timeline[2][0], "world")
        self.assertEqual(timeline[3], ("static_sync",))
        self.assertEqual(timeline[4], ("publish", [packet]))


if __name__ == "__main__":
    unittest.main()
