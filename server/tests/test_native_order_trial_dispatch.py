"""Bounded dispatcher tests for the native order admission adapter."""

from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server import native_order_trial_admission as admission
from wakfu_server.application import native_order_trial_dispatch as dispatch
from wakfu_server.application.dispatch_result import DispatchResult

_FIXTURE = (
    Path(__file__).parent / "fixtures" / "native_pizzlarva_admission_sources.json"
)


class NativeOrderTrialDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = admission.document()
        cls.sources = {row["id"]: row for row in json.loads(_FIXTURE.read_text())}

    def app(self, kind="entrance", *, enabled=False):
        profile = deepcopy(self.profile)
        profile["enabled"] = enabled
        selected = profile["sources"][kind]
        position = selected["approaches"][0]
        character = dict(
            id=17,
            account_id=4,
            map_id=selected["map_id"],
            x=position[0],
            y=position[1],
            z=position[2],
            instance_id=0 if kind == "entrance" else 901,
        )
        state = SimpleNamespace(
            opcode=12870,
            body=struct.pack(">qHH", selected["object_id"], 0, 0),
            character=dict(character),
            account_id=4,
            generation="lease-1",
            loaded=True,
            fight=None,
            combat_session=None,
            spectator_session=None,
            bag_session=None,
            environment_ticket=None,
            connection=object(),
            service="world",
        )
        db = Mock()
        store = Mock()
        store.connection.side_effect = lambda: nullcontext(db)
        store.lock_character.return_value = None
        store.character.side_effect = lambda *_args: dict(character)
        store.now.return_value = object()
        positions = Mock()
        positions.account_barrier.side_effect = lambda *_args: nullcontext()
        runtime = SimpleNamespace(
            STORE=store,
            POSITIONS=positions,
            flush_positions=Mock(),
            COMBAT_GROUPS=object(),
            send=Mock(),
            record=Mock(),
        )
        app = SimpleNamespace(
            state=state,
            runtime=runtime,
            environment_blocked=Mock(return_value=False),
            approach_actor=Mock(return_value=True),
            deliver_dungeon_transitions=Mock(),
        )
        return app, db, store, profile

    def test_disabled_and_unrelated_actions_fall_through_without_database_work(self):
        app, db, _store, profile = self.app(enabled=False)
        with patch.object(admission, "document", return_value=profile):
            self.assertIsNone(dispatch.handle(app))
        db.execute.assert_not_called()
        app.state.opcode = 999
        with patch.object(
            admission, "document", side_effect=AssertionError("unexpected profile load")
        ):
            self.assertIsNone(dispatch.handle(app))

    def test_public_entry_uses_original_body_configuration_fence_and_outbox(self):
        app, db, store, profile = self.app(enabled=True)
        proof = SimpleNamespace(
            effect_reference=1457,
            descriptor_sha256=admission.digest(
                profile["sources"]["entrance"]["descriptor"]
            ),
        )
        route = {
            "start_map_id": 885,
            "native_generic_entry": {
                "effect_reference": 1457,
                "approaches": profile["sources"]["entrance"]["approaches"],
                "program": profile["sources"]["entrance"]["descriptor"],
            },
        }
        sequence = []
        barrier = Mock(
            side_effect=lambda *_a, transition, **_k: transition(frozenset({4}))
        )
        with patch.object(admission, "document", return_value=profile):
            with patch.object(admission, "qualify", return_value=proof) as qualify:
                with patch(
                    "wakfu_server.dungeon_position_barrier.run_party_entry", barrier
                ):
                    with patch(
                        "wakfu_server.owned_story_generic_entry.configuration",
                        return_value={"route": route},
                    ):

                        def enter(*args, **kwargs):
                            sequence.append("enter")
                            self.assertIs(args[4], app.state.body)
                            self.assertEqual(
                                kwargs["allowed_position_accounts"], frozenset({4})
                            )
                            self.assertIs(kwargs["_db"], db)
                            kwargs["initialize_instance"](db, {"instance_id": 901})
                            return True

                        with patch(
                            "wakfu_server.owned_story_generic_entry.enter",
                            side_effect=enter,
                        ) as enter_mock:
                            with patch(
                                "wakfu_server.dungeon_runtime.initialize_instance"
                            ) as initialize:
                                with patch(
                                    "wakfu_server.dungeon_runtime.entry_destination",
                                    return_value=object(),
                                ):
                                    with patch(
                                        "wakfu_server.combat_terrain.map_geometry",
                                        return_value=885,
                                    ):
                                        result = dispatch.handle(app)
        self.assertEqual(result, DispatchResult.CONTINUE)
        qualify.assert_called_once()
        self.assertEqual(qualify.call_args.args[:4], (db, store, 4, "lease-1"))
        self.assertEqual(qualify.call_args.args[4]["id"], 17)
        self.assertEqual(qualify.call_args.args[5], app.state.body)
        self.assertEqual(
            qualify.call_args.kwargs,
            {"loaded": True, "blocked": False, "value": profile},
        )
        barrier.assert_called_once()
        enter_mock.assert_called_once()
        initialize.assert_called_once_with(
            db,
            {"instance_id": 901},
            groups=app.runtime.COMBAT_GROUPS,
            geometry=885,
            store=store,
        )
        app.deliver_dungeon_transitions.assert_called_once_with(before_action=True)

    def test_mode_start_and_publication_use_callbacks_around_commit_result(self):
        app, db, store, profile = self.app("hard", enabled=True)
        proof = object()
        accepted = DispatchResult.FALLTHROUGH
        sequence = []

        def run_party_entry(_store, _positions, _account, _character, *, transition):
            with _store.connection() as connection:
                value = transition(frozenset({4}))
            sequence.append("committed")
            return value

        def mode_start(*args):
            self.assertIs(args[0], db)
            self.assertIs(args[3], proof)
            self.assertIs(args[4], profile)
            sequence.append("start")
            return accepted

        def mode_publish(target_app, result):
            self.assertIs(target_app, app)
            self.assertIs(result, accepted)
            sequence.append("publish")
            return DispatchResult.FALLTHROUGH

        with patch.object(admission, "document", return_value=profile):
            with patch.object(admission, "qualify", return_value=proof):
                with patch(
                    "wakfu_server.dungeon_position_barrier.run_party_entry",
                    side_effect=run_party_entry,
                ):
                    result = dispatch.handle(
                        app, mode_start=mode_start, mode_publish=mode_publish
                    )
        self.assertEqual(result, DispatchResult.FALLTHROUGH)
        self.assertEqual(sequence, ["start", "committed", "publish"])
        app.deliver_dungeon_transitions.assert_not_called()

    def test_missing_mode_callbacks_and_qualification_rejection_do_not_start_or_transition(
        self,
    ):
        app, _db, _store, profile = self.app("normal", enabled=True)
        with patch.object(admission, "document", return_value=profile):
            result = dispatch.handle(app)
        self.assertEqual(result, DispatchResult.CONTINUE)
        app.runtime.record.assert_called_once()
        app.runtime.send.assert_called_once()
        app.deliver_dungeon_transitions.assert_not_called()

        app, _db, _store, profile = self.app("entrance", enabled=True)
        with patch.object(admission, "document", return_value=profile):
            with patch.object(
                admission, "qualify", side_effect=ValueError("source changed")
            ):

                def invoke_transition(
                    _store, _positions, _account, _character, *, transition
                ):
                    with _store.connection() as db:
                        return transition(frozenset({4}))

                with patch(
                    "wakfu_server.dungeon_position_barrier.run_party_entry",
                    side_effect=invoke_transition,
                ):
                    result = dispatch.handle(app)
        self.assertEqual(result, DispatchResult.CONTINUE)
        app.runtime.record.assert_called_once()
        app.deliver_dungeon_transitions.assert_not_called()

    def test_disabled_hook_continues_to_existing_world_interaction_dispatch(self):
        app, _db, _store, _profile = self.app(enabled=False)
        from wakfu_server.application.session_private_scenes import PrivateScenesMixin

        with patch(
            "wakfu_server.application.native_order_trial_dispatch.handle",
            return_value=None,
        ):
            with patch(
                "wakfu_server.application.owned_story_dispatch.handle_interaction",
                return_value=True,
            ):
                self.assertEqual(
                    PrivateScenesMixin.handle_world_interaction(app),
                    DispatchResult.CONTINUE,
                )

    def test_dispatch_uses_production_default_mode_callback_factory(self):
        app, db, store, profile = self.app("hard", enabled=True)
        proof = object()
        sequence = []

        def run_party_entry(_store, _positions, _account, _character, *, transition):
            with _store.connection() as connection:
                accepted = transition(frozenset({4}))
            sequence.append("committed")
            return accepted

        def start(connection, selected_store, current, current_proof, capability):
            self.assertIs(connection, db)
            self.assertIs(selected_store, store)
            self.assertEqual(current["id"], 17)
            self.assertIs(current_proof, proof)
            self.assertIs(capability, profile)
            sequence.append("default-start")
            return True

        def publish(target_app, accepted):
            self.assertIs(target_app, app)
            self.assertTrue(accepted)
            sequence.append("default-publish")
            return DispatchResult.CONTINUE

        with patch.object(admission, "document", return_value=profile):
            with patch.object(admission, "qualify", return_value=proof):
                with patch(
                    "wakfu_server.application.native_order_trial_mode.callbacks",
                    return_value=(start, publish),
                ) as factory:
                    with patch(
                        "wakfu_server.dungeon_position_barrier.run_party_entry",
                        side_effect=run_party_entry,
                    ):
                        result = dispatch.handle(app)
        factory.assert_called_once_with(app)
        self.assertEqual(sequence, ["default-start", "committed", "default-publish"])
        self.assertEqual(result, DispatchResult.CONTINUE)
        app.deliver_dungeon_transitions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
