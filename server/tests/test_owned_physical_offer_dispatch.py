"""Real native NPC actions keep original source, movement and entry authority."""

from contextlib import ExitStack, nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout
from wakfu_server import owned_physical_offers as offers
from wakfu_server.application import owned_physical_offer_dispatch as dispatch
from wakfu_server.application.session_objectives import ObjectivesSessionMixin
from wakfu_server.application.dispatch_result import DispatchResult


class OwnedPhysicalOfferDispatchTests(unittest.TestCase):
    def fixture(self):
        actor = offers.actor_id("quest-map-889-19411-1249", "a" * 64, "b" * 64)
        character = dict(
            id=7,
            account_id=2,
            hp=100,
            map_id=527,
            instance_id=0,
            x=54,
            y=85,
            z=0,
            direction=5,
        )
        source = dict(
            id=19411,
            map_id=527,
            x=53,
            y=85,
            z=0,
            approach_positions=[
                dict(x=54, y=85, z=0),
                dict(x=52, y=85, z=0),
                dict(x=53, y=86, z=0),
            ],
        )
        route = SimpleNamespace(
            key="quest-map-889-19411-1249",
            start_map_id=889,
            criterion="IsAchievementActive(2160) and not IsAchievementComplete(2161)",
        )
        resolved = dict(
            route=route,
            source=source,
            native_destination=dict(cyW=1, item_reference=999),
            difficulty_selection=None,
            destination=dict(map_id=889, x=0, y=14, z=0, direction=7),
        )
        state = SimpleNamespace(
            opcode=13222,
            body=struct.pack(">qq", actor, 61),
            character=character,
            account_id=2,
            generation="lease",
            loaded=True,
            fight=None,
            combat_session=None,
            spectator_session=None,
            bag_session=None,
            environment_ticket=None,
            movement_state=object(),
            connection=object(),
            service="world",
        )
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        store = Mock()
        store.connection.side_effect = lambda: nullcontext(db)
        store.character.side_effect = lambda *args: dict(character)
        store.now.return_value = datetime.now(timezone.utc)
        positions = Mock()
        positions.account_barrier.side_effect = lambda *args: nullcontext()
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
            approach_actor=Mock(return_value=False),
            deliver_dungeon_transitions=Mock(),
        )
        return app, db, resolved

    def patches(
        self, app, db, resolved, *, allowed=True, resolve_error=None, entry_error=None
    ):
        stack = ExitStack()
        self.addCleanup(stack.close)
        row = dict(actor_id=struct.unpack(">qq", app.state.body)[0], action_ids=[61])
        resolver = stack.enter_context(
            patch.object(
                offers,
                "resolve",
                side_effect=resolve_error,
                return_value=(row, resolved),
            )
        )
        approach = Mock(return_value=allowed)
        stack.enter_context(
            patch("wakfu_server.teleporter_approach.callback", return_value=approach)
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_geometry.prepare_geometry", side_effect=lambda x: x
            )
        )
        geometry = stack.enter_context(
            patch("wakfu_server.combat_terrain.map_geometry", side_effect=lambda m: m)
        )
        initializer = stack.enter_context(
            patch("wakfu_server.dungeon_runtime.initialize_instance")
        )
        barrier = stack.enter_context(
            patch(
                "wakfu_server.dungeon_position_barrier.run_party_entry",
                side_effect=lambda *a, **kw: kw["transition"](frozenset({2})),
            )
        )

        def enter(*args, **kwargs):
            if entry_error is not None:
                raise entry_error
            self.assertIs(args[4], resolved)
            self.assertEqual(
                args[4]["native_destination"], dict(cyW=1, item_reference=999)
            )
            self.assertEqual(kwargs["allowed_position_accounts"], frozenset({2}))
            self.assertIs(kwargs["_db"], db)
            self.assertTrue(
                kwargs["source_allowed"](app.state.character, resolved["source"])
            )
            self.assertFalse(
                kwargs["source_allowed"](
                    app.state.character, dict(resolved["source"], id=1)
                )
            )
            kwargs["initialize_instance"](db, {"instance_id": 123})
            return {"instance_id": 123}

        entry = stack.enter_context(
            patch("wakfu_server.dungeon_transport.enter_resolved", side_effect=enter)
        )
        return SimpleNamespace(
            resolver=resolver,
            approach=approach,
            initializer=initializer,
            barrier=barrier,
            entry=entry,
            geometry=geometry,
        )

    def test_real_action_fences_party_revalidates_source_and_preserves_native_fee(self):
        app, db, resolved = self.fixture()
        proof = self.patches(app, db, resolved)
        self.assertTrue(dispatch.handle(app))
        self.assertEqual(proof.resolver.call_count, 2)
        self.assertEqual(app.runtime.STORE.lock_character.call_count, 2)
        self.assertTrue(
            all(
                call.kwargs == {"selected": True}
                for call in app.runtime.STORE.lock_character.call_args_list
            )
        )
        proof.entry.assert_called_once()
        proof.initializer.assert_called_once_with(
            db,
            {"instance_id": 123},
            groups=app.runtime.COMBAT_GROUPS,
            geometry=889,
            store=app.runtime.STORE,
        )
        app.deliver_dungeon_transitions.assert_called_once_with(before_action=True)
        app.runtime.send.assert_not_called()

    def test_remote_click_walks_only_to_actual_native_approaches_without_entry(self):
        for walked in (True, False):
            app, db, resolved = self.fixture()
            app.approach_actor.return_value = walked
            proof = self.patches(app, db, resolved, allowed=False)
            self.assertTrue(dispatch.handle(app))
            accepts = app.approach_actor.call_args.args[0]
            for point in ((54, 85, 0), (52, 85, 0), (53, 86, 0)):
                self.assertTrue(accepts(point))
            self.assertFalse(accepts((53, 85, 0)))
            proof.entry.assert_not_called()
            proof.barrier.assert_not_called()
            app.deliver_dungeon_transitions.assert_not_called()
            self.assertEqual(bool(app.runtime.send.call_count), not walked)

    def test_wrong_action_stale_generation_foreign_owner_and_cost_failure_stay_safe(
        self,
    ):
        for failure in (
            "action",
            "lease",
            "foreign",
            "offmap",
            "fee",
            "database",
            "pool",
        ):
            app, db, resolved = self.fixture()
            kwargs = {}
            if failure == "action":
                actor = struct.unpack(">qq", app.state.body)[0]
                app.state.body = struct.pack(">qq", actor, 62)
                kwargs["resolve_error"] = ValueError("wrong action")
            elif failure == "lease":
                app.runtime.STORE.lock_character.side_effect = ValueError("stale lease")
            elif failure == "foreign":
                app.runtime.STORE.character.side_effect = lambda *a: dict(
                    app.state.character, account_id=99
                )
            elif failure == "offmap":
                kwargs["resolve_error"] = ValueError("offmap")
            elif failure == "fee":
                kwargs["entry_error"] = ValueError("native fee missing")
            elif failure == "database":
                kwargs["resolve_error"] = DatabaseError("PRIVATE SQL TEXT")
            else:
                kwargs["resolve_error"] = PoolTimeout("PRIVATE SQL TEXT")
            proof = self.patches(app, db, resolved, **kwargs)
            with self.subTest(failure=failure):
                self.assertTrue(dispatch.handle(app))
                app.deliver_dungeon_transitions.assert_not_called()
                app.runtime.send.assert_called_once()
                self.assertNotIn("PRIVATE SQL TEXT", str(app.runtime.send.call_args))
                if failure != "fee":
                    proof.entry.assert_not_called()

    def test_replayed_click_after_durable_entry_never_pays_or_enters_again(self):
        app, db, resolved = self.fixture()
        proof = self.patches(app, db, resolved)
        app.runtime.STORE.character.side_effect = [
            dict(app.state.character),
            dict(app.state.character, map_id=889, instance_id=123),
        ]
        self.assertTrue(dispatch.handle(app))
        proof.entry.assert_not_called()
        app.deliver_dungeon_transitions.assert_not_called()
        app.runtime.send.assert_called_once()

    def test_unrelated_npc_and_unloaded_owner_never_start_transition(self):
        app, db, resolved = self.fixture()
        proof = self.patches(app, db, resolved)
        app.state.body = struct.pack(">qq", -1234, 61)
        self.assertFalse(dispatch.handle(app))
        proof.resolver.assert_not_called()
        app.state.body = struct.pack(
            ">qq", offers.actor_id("quest-map-889-19411-1249", "a" * 64, "b" * 64), 61
        )
        app.state.loaded = False
        self.assertTrue(dispatch.handle(app))
        app.runtime.STORE.lock_character.assert_not_called()
        proof.entry.assert_not_called()

    def test_actual_session_hook_precedes_ordinary_dialogue_handlers(self):
        app, _, _ = self.fixture()
        with patch.object(dispatch, "handle", return_value=True) as owned, patch(
            "wakfu_server.application.npc_owned_entry_dispatch.handle"
        ) as ordinary:
            self.assertEqual(
                ObjectivesSessionMixin.handle_world_dialogue(app),
                DispatchResult.CONTINUE,
            )
        owned.assert_called_once_with(app)
        ordinary.assert_not_called()


if __name__ == "__main__":
    unittest.main()
