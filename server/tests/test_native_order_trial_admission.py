"""Focused source-proof and admission tests for the disabled native order trial."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server import native_order_trial_admission as admission
from wakfu_server.achievements import native_order_trials


_FIXTURE = (
    Path(__file__).parent / "fixtures" / "native_pizzlarva_admission_sources.json"
)


class NativeOrderTrialAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = admission.document()
        cls.sources = {row["id"]: row for row in json.loads(_FIXTURE.read_text())}

    def character(self, kind):
        source = self.document["sources"][kind]
        point = source["approaches"][0]
        return dict(
            id=17,
            account_id=4,
            map_id=source["map_id"],
            x=point[0],
            y=point[1],
            z=point[2],
            instance_id=0 if kind == "entrance" else 901,
        )

    def body(self, kind, action=0, parameter=0):
        return struct.pack(
            ">qHH", self.document["sources"][kind]["object_id"], action, parameter
        )

    def test_original_three_native_sources_plan_to_fixed_server_modes(self):
        entrance = admission.plan(
            self.document,
            self.character("entrance"),
            self.body("entrance"),
            native_source=self.sources[23626],
        )
        self.assertEqual(
            (entrance.mode, entrance.effect_reference, entrance.source_map_id),
            ("entrance", 1457, 546),
        )
        self.assertEqual(entrance.hard_mode, None)

        normal = admission.plan(
            self.document,
            self.character("normal"),
            self.body("normal"),
            native_source=self.sources[23619],
        )
        hard = admission.plan(
            self.document,
            self.character("hard"),
            self.body("hard"),
            native_source=self.sources[23620],
        )
        self.assertEqual(
            (normal.mode, normal.hard_mode, normal.effect_reference),
            ("normal", False, 1451),
        )
        self.assertEqual(
            (hard.mode, hard.hard_mode, hard.effect_reference), ("hard", True, 1452)
        )
        self.assertEqual((normal.generation, hard.generation), (None, None))

    def test_wrong_wire_map_position_instance_or_source_proof_is_rejected(self):
        cases = (
            (
                self.character("normal"),
                self.body("normal", action=1),
                self.sources[23619],
            ),
            (
                self.character("normal"),
                self.body("normal", parameter=1),
                self.sources[23619],
            ),
            (
                dict(self.character("normal"), map_id=546),
                self.body("normal"),
                self.sources[23619],
            ),
            (
                dict(self.character("normal"), x=99),
                self.body("normal"),
                self.sources[23619],
            ),
            (
                dict(self.character("normal"), instance_id=0),
                self.body("normal"),
                self.sources[23619],
            ),
            (
                self.character("normal"),
                self.body("normal"),
                dict(self.sources[23619], type="Other"),
            ),
            (
                self.character("normal"),
                self.body("normal"),
                dict(self.sources[23619], x=99),
            ),
        )
        for character, body, native_source in cases:
            with self.subTest(character=character, body=body, source=native_source):
                with self.assertRaises(ValueError):
                    admission.plan(
                        self.document, character, body, native_source=native_source
                    )

    def test_wrong_packet_size_unknown_object_and_tampered_capability_are_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            admission.plan(
                self.document,
                self.character("normal"),
                b"short",
                native_source=self.sources[23619],
            )
        with self.assertRaises(ValueError):
            admission.plan(
                self.document,
                self.character("normal"),
                struct.pack(">qHH", 9, 0, 0),
                native_source=self.sources[23619],
            )
        changed = deepcopy(self.document)
        changed["sources"]["hard"]["approaches"] = [[9, 9, 9]]
        with self.assertRaises(ValueError):
            admission.plan(
                changed,
                self.character("hard"),
                self.body("hard"),
                native_source=self.sources[23620],
            )

    def test_disabled_profile_rejects_before_database_or_store_access(self):
        self.assertFalse(self.document["enabled"])
        db, store = Mock(), Mock()
        with self.assertRaisesRegex(ValueError, "not enabled"):
            admission.qualify(
                db,
                store,
                4,
                "lease",
                self.character("entrance"),
                self.body("entrance"),
                loaded=True,
                blocked=False,
                value=self.document,
            )
        db.execute.assert_not_called()
        store.lock_character.assert_not_called()

    def test_enabled_fixture_qualification_refreshes_lease_and_native_source(self):
        enabled = deepcopy(self.document)
        enabled["enabled"] = True
        character = self.character("entrance")
        db, store = Mock(), Mock()
        store.lock_character.return_value = None
        store.character.return_value = dict(character)
        store.now.return_value = object()
        static = Mock(objects=Mock(return_value=[self.sources[23626]]))
        with patch("wakfu_server.world_static", static):
            with patch("wakfu_server.simple_item_actions._idle"):
                with patch(
                    "wakfu_server.achievements.storage.load_locked", return_value={}
                ):
                    with patch(
                        "wakfu_server.dungeon_achievement_authority.queries_from_state",
                        return_value={},
                    ):
                        with patch(
                            "wakfu_server.dungeon_criteria.evaluate", return_value=True
                        ):
                            proof = admission.qualify(
                                db,
                                store,
                                4,
                                "fresh-lease",
                                character,
                                self.body("entrance"),
                                loaded=True,
                                blocked=False,
                                value=enabled,
                            )
        self.assertEqual(proof.generation, "fresh-lease")
        store.lock_character.assert_called_once_with(
            db, 4, "fresh-lease", 17, selected=True
        )
        self.assertEqual(static.objects.call_args.args, (546,))

        store.character.return_value = dict(character, x=-3)
        with patch("wakfu_server.world_static", static):
            with patch("wakfu_server.simple_item_actions._idle"):
                with self.assertRaisesRegex(ValueError, "position"):
                    admission.qualify(
                        db,
                        store,
                        4,
                        "fresh-lease",
                        character,
                        self.body("entrance"),
                        loaded=True,
                        blocked=False,
                        value=enabled,
                    )

    def test_mode_start_binds_original_mode_and_replay_cannot_reroll(self):
        source = admission.plan(
            self.document,
            self.character("hard"),
            self.body("hard"),
            native_source=self.sources[23620],
        )
        proof = replace(source, generation="lease-2")
        trial = native_order_trials.OrderTrial(
            17, 77, True, (("blue", "tomato"), ("red", "cheese"), ("green", "pepper"))
        )
        orders = (("blue", "tomato"), ("red", "cheese"), ("green", "pepper"))
        with patch.object(native_order_trials, "start", return_value=trial) as start:
            self.assertIs(
                admission.start_trial(proof, encounter_id=77, orders=orders), trial
            )
            start.assert_called_once_with(
                owner_id=17, encounter_id=77, hard_mode=True, orders=orders
            )
            self.assertIs(
                admission.start_trial(
                    proof, encounter_id=77, orders=(), existing=trial
                ),
                trial,
            )
            start.assert_called_once()
            for changed in (
                replace(proof, owner_id=18),
                replace(proof, hard_mode=False),
            ):
                with self.assertRaises(ValueError):
                    admission.start_trial(
                        changed, encounter_id=77, orders=(1, 2, 3), existing=trial
                    )
        with self.assertRaises(ValueError):
            admission.start_trial(source, encounter_id=77, orders=(1, 2, 3))

    def test_private_mode_requires_original_owned_entry_and_pinned_source(self):
        enabled = deepcopy(self.document)
        enabled["enabled"] = True
        character = self.character("hard")
        entrance = enabled["sources"]["entrance"]
        entry_effect = entrance["descriptor"]["groups"][0]["actions"][0]["effects"][0]
        metadata = {
            "effect_reference": 1457,
            "wire_action": 0,
            "approaches": entrance["approaches"],
            "program": entrance["descriptor"],
            "source": self.sources[23626],
        }
        route = {
            "entry_map_id": 546,
            "entry_object_id": 23626,
            "destination_id": 1457,
            "start_map_id": 885,
            "registration_policy": "native_generic_choice",
            "native_generic_entry": metadata,
        }
        instance_config = {"route": route}
        member = {"character_id": 17}
        membership = {
            "start_map_id": 885,
            "entry_map_id": 546,
            "entry_object_id": 23626,
            "entry_destination_id": 1457,
        }

        def qualify(*, db_members=None, db_membership=None, current_config=None):
            db = Mock()
            db.execute.return_value.fetchone.return_value = db_membership or membership
            db.execute.return_value.fetchall.return_value = (
                db_members if db_members is not None else [member]
            )
            store = Mock()
            store.character.return_value = dict(character)
            store.now.return_value = object()
            with patch(
                "wakfu_server.world_static.objects", return_value=[self.sources[23620]]
            ):
                with patch("wakfu_server.simple_item_actions._idle"):
                    with patch(
                        "wakfu_server.achievements.storage.load_locked", return_value={}
                    ):
                        with patch(
                            "wakfu_server.dungeon_achievement_authority.queries_from_state",
                            return_value={},
                        ):
                            with patch(
                                "wakfu_server.dungeon_criteria.evaluate",
                                return_value=True,
                            ):
                                with patch(
                                    "wakfu_server.dungeon_runtime.configuration_for_instance",
                                    return_value=(
                                        None,
                                        current_config or instance_config,
                                    ),
                                ):
                                    result = admission.qualify(
                                        db,
                                        store,
                                        4,
                                        "current-lease",
                                        character,
                                        self.body("hard"),
                                        loaded=True,
                                        blocked=False,
                                        value=enabled,
                                    )
            return result

        proof = qualify()
        self.assertEqual(
            (proof.mode, proof.hard_mode, proof.generation),
            ("hard", True, "current-lease"),
        )
        self.assertEqual(
            route["native_generic_entry"]["effect_reference"],
            entry_effect["action_reference"],
        )

        foreign_source = deepcopy(instance_config)
        foreign_source["route"]["native_generic_entry"]["source"][
            "payload_hex"
        ] = self.sources[23619]["payload_hex"]
        invalid = (
            {"db_membership": dict(membership, entry_object_id=999)},
            {"db_members": [{"character_id": 18}]},
            {"current_config": foreign_source},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    qualify(**kwargs)


if __name__ == "__main__":
    unittest.main()
