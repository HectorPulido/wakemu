"""Owner-scoped noncombat NPCs preserve native dialogue and event authority."""

import gzip
import json
import struct
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from wakfu_server import owned_story_npcs, npc_dialogue, npc_world
from wakfu_server.application import owned_story_npc_dispatch
from wakfu_server.achievements import mission_toolkit


ROOT = Path(__file__).resolve().parents[2]


def native_dialogue():
    with gzip.open(ROOT / "database/protocol/npc-dialogues.json.gz", "rt") as source:
        value = json.load(source)
    value["node_index"] = {node["id"]: node for node in value["nodes"]}
    return value


def profile():
    return json.loads(
        (
            ROOT
            / "server/wakfu_server/maps/owned_story_npc_profiles/zinit-shore-980.json"
        ).read_text()
    )


def state(*, running=(2684,), completed=(), objectives=()):
    return {
        "running": list(running),
        "completed": list(completed),
        "active": list(running),
        "active_periods": {},
        "active_unknown": [],
        "objectives": list(objectives),
        "variables": {},
        "tracking": list(running),
        "recent": [],
        "completion_dates": {},
    }


class _DB:
    def __init__(self, version=1):
        self.version = version

    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return {"context_policy_version": self.version}


class _Store:
    def __init__(self, character=None):
        self.db = _DB()
        self.current = character or {
            "id": 41,
            "account_id": 7,
            "map_id": 980,
            "instance_id": (1 << 57) + 47,
            "x": 0,
            "y": 0,
            "z": 0,
        }

    @contextmanager
    def connection(self):
        yield self.db

    def lock_character(self, *_args, **_kwargs):
        pass

    def character(self, *_args, **_kwargs):
        return dict(self.current)


class OwnedStoryNpcTests(unittest.TestCase):
    def _rows(
        self,
        *,
        completed=None,
        selected_id="zinit-reef-980",
        version=1,
        pending=None,
        progress=None,
    ):
        store = _Store()
        with (
            patch.object(owned_story_npcs, "profiles", return_value=(profile(),)),
            patch.object(
                owned_story_npcs.owned_story_controller,
                "recognizes_instance",
                return_value=True,
            ),
            patch.object(
                owned_story_npcs.owned_story_controller,
                "_scope",
                return_value=(
                    {"id": selected_id},
                    set({"voyage-stage-3-victory"} if completed is None else completed),
                ),
            ),
            patch.object(
                owned_story_npcs.owned_story_refresh, "pending", return_value=pending
            ),
            patch(
                "wakfu_server.achievements.storage.load_locked",
                return_value=progress or state(),
            ),
        ):
            store.db.version = version
            return owned_story_npcs.rows(store.db, store, store.current)

    def test_rows_require_the_exact_story_controller_flag_version_running_quest_and_no_refresh(
        self,
    ):
        accepted = self._rows()
        self.assertEqual(len(accepted), 1)
        row = accepted[0]
        self.assertEqual(
            (row["reference_id"], row["action_ids"], row["objective_id"]),
            (3801, [697], 5305),
        )
        for conditions in (
            {"selected_id": "other-controller"},
            {"version": 2},
            {"completed": set()},
            {"progress": state(running=())},
            {"pending": {"pending": True}},
        ):
            with self.subTest(conditions=conditions):
                self.assertEqual(self._rows(**conditions), [])
        # A genuinely completed stage retains its scoped native greeting, but
        # its objective edge is never re-enabled.
        self.assertEqual(
            len(self._rows(progress=state(running=(), completed=(2684,)))), 1
        )

    def test_actor_ids_are_instance_scoped_and_format11_spawn_uses_conversation_uid(
        self,
    ):
        first = owned_story_npcs.actor_id((1 << 57) + 47, 1)
        second = owned_story_npcs.actor_id((1 << 57) + 48, 1)
        self.assertNotEqual(first, second)
        native = native_dialogue()
        with patch.object(
            owned_story_npcs, "profiles", return_value=(profile(),)
        ), patch.object(
            owned_story_npcs.owned_story_controller,
            "recognizes_instance",
            return_value=True,
        ), patch.object(
            owned_story_npcs.owned_story_controller,
            "_scope",
            return_value=({"id": "zinit-reef-980"}, {"voyage-stage-3-victory"}),
        ), patch.object(
            owned_story_npcs.owned_story_refresh, "pending", return_value=None
        ), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=state()
        ):
            store = _Store()
            opcode, body = owned_story_npcs.spawn_packets(
                store.db, store, store.current, native=native
            )[0]
        self.assertEqual(opcode, 12608)
        self.assertEqual(body[:3], b"\x00\x01\x01")
        self.assertEqual(struct.unpack_from(">q", body, 3)[0], first)

    def test_native_actor_begin_and_accepted_choice_settle_one_spoken_objective(self):
        native = native_dialogue()
        store = _Store()
        current_state = state()
        actor = owned_story_npcs.actor_id((1 << 57) + 47, 1)

        def locked(_store, _db, _account, _generation, character, _identity, _action):
            row = dict(
                profile()["npcs"][0],
                actor_id=actor,
                map_id=980,
                instance_id=(1 << 57) + 47,
                enabled=True,
            )
            return dict(character, account_id=7), profile(), row, current_state

        with (
            patch.object(owned_story_npcs, "profiles", return_value=(profile(),)),
            patch.object(owned_story_npcs, "_locked", side_effect=locked),
            patch.object(owned_story_npcs.npc_dialogue, "catalog", return_value=native),
            patch.object(
                owned_story_npcs,
                "_criterion",
                side_effect=lambda _s, _c, _state, text: text
                == "GetInstanceId() == 980"
                or not text,
            ),
            patch.object(owned_story_npcs, "_nearby", return_value=True),
            patch.object(
                mission_toolkit, "settle", return_value=[(13405, b"objective")]
            ) as settle,
        ):
            session, packets = owned_story_npcs.begin(
                store, 7, "generation", store.current, actor, 697
            )
            self.assertEqual(len(packets), 1)
            settle.assert_not_called()
            choice_body = struct.pack(">ii", 3212, 7974)
            result = owned_story_npcs.choose(
                store, 7, "generation", store.current, session, choice_body
            )
            self.assertEqual(result["packets"][-1], (13405, b"objective"))
            self.assertEqual(len(result["packets"]), 2)
            self.assertEqual(settle.call_count, 1)
            self.assertEqual(settle.call_args.args[4:], ("npc_spoken", 5305))
            with self.assertRaises(ValueError):
                owned_story_npcs.choose(
                    store, 7, "generation", store.current, session, choice_body
                )
            self.assertEqual(settle.call_count, 1)

    def test_locked_gate_checks_selected_owner_and_live_range(self):
        store = _Store()
        row = dict(
            profile()["npcs"][0],
            actor_id=owned_story_npcs.actor_id((1 << 57) + 47, 1),
            map_id=980,
            instance_id=(1 << 57) + 47,
            enabled=True,
        )
        selected = (profile(), row, state())
        with (
            patch.object(owned_story_npcs, "_rows", return_value=[selected]),
            patch.object(owned_story_npcs, "_nearby", return_value=True),
            patch("wakfu_server.environment_interactions._guard"),
        ):
            current, _story, actual_row, _progress = owned_story_npcs._locked(
                store, store.db, 7, "generation", store.current, row["actor_id"], 697
            )
        self.assertEqual(current["account_id"], 7)
        self.assertEqual(actual_row["actor_id"], row["actor_id"])

        store.current["account_id"] = 8
        with patch("wakfu_server.environment_interactions._guard"):
            with self.assertRaisesRegex(ValueError, "selected owner"):
                owned_story_npcs._locked(
                    store,
                    store.db,
                    7,
                    "generation",
                    store.current,
                    row["actor_id"],
                    697,
                )
        store.current["account_id"] = 7
        with (
            patch.object(owned_story_npcs, "_rows", return_value=[selected]),
            patch.object(owned_story_npcs, "_nearby", return_value=False),
            patch("wakfu_server.environment_interactions._guard"),
        ):
            with self.assertRaisesRegex(ValueError, "outside interaction range"):
                owned_story_npcs._locked(
                    store,
                    store.db,
                    7,
                    "generation",
                    store.current,
                    row["actor_id"],
                    697,
                )

    def test_completed_stage_keeps_native_greeting_without_objective_replay(self):
        native = native_dialogue()
        store = _Store()
        actor = owned_story_npcs.actor_id((1 << 57) + 47, 1)
        completed = state(running=(), completed=(2684,), objectives=(5305,))

        def locked(_store, _db, _account, _generation, character, _identity, _action):
            row = dict(
                profile()["npcs"][0],
                actor_id=actor,
                map_id=980,
                instance_id=(1 << 57) + 47,
                enabled=True,
            )
            return dict(character, account_id=7), profile(), row, completed

        with (
            patch.object(owned_story_npcs, "_locked", side_effect=locked),
            patch.object(owned_story_npcs.npc_dialogue, "catalog", return_value=native),
            patch.object(owned_story_npcs, "_criterion", return_value=True),
            patch.object(owned_story_npcs, "_nearby", return_value=True),
            patch.object(mission_toolkit, "settle") as settle,
        ):
            session, packets = owned_story_npcs.begin(
                store, 7, "generation", store.current, actor, 697
            )
            self.assertEqual(len(packets), 1)
            self.assertEqual(session.graph[(3212, 7974)], None)
            result = owned_story_npcs.choose(
                store,
                7,
                "generation",
                store.current,
                session,
                struct.pack(">ii", 3212, 7974),
            )
            self.assertTrue(result["packets"])
            with self.assertRaises(ValueError):
                owned_story_npcs.choose(
                    store,
                    7,
                    "generation",
                    store.current,
                    session,
                    struct.pack(">ii", 3212, 7974),
                )
        settle.assert_not_called()

    def test_profile_source_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            real_path = Path
            source = real_path(directory) / "profile.json"
            source.write_text(json.dumps(profile()))

            class ProfilePath:
                def __init__(self, _value):
                    pass

                def with_name(self, _name):
                    return real_path(directory)

            owned_story_npcs.profiles.cache_clear()
            with (
                patch.object(
                    owned_story_npcs, "SOURCE_FILES", {"profile.json": "0" * 64}
                ),
                patch.object(owned_story_npcs, "Path", ProfilePath),
            ):
                with self.assertRaisesRegex(ValueError, "not been reviewed"):
                    owned_story_npcs.profiles()
            owned_story_npcs.profiles.cache_clear()

    def test_actual_profile_is_loaded_from_its_explicit_source_pin(self):
        owned_story_npcs.profiles.cache_clear()
        loaded = owned_story_npcs.profiles()
        selected = [row for row in loaded if row["id"] == "zinit-shore-980"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["npcs"][0]["objective_id"], 5305)
        owned_story_npcs.profiles.cache_clear()

    def test_pending_refresh_allows_only_context_bootstrap_render(self):
        store = _Store()
        native = native_dialogue()
        scope_calls = []

        def scope(_db, _store, _character, *, check_position=True):
            scope_calls.append(check_position)
            return {"id": "zinit-reef-980"}, {"voyage-stage-3-victory"}

        with (
            patch.object(owned_story_npcs, "profiles", return_value=(profile(),)),
            patch.object(
                owned_story_npcs.owned_story_controller,
                "recognizes_instance",
                return_value=True,
            ),
            patch.object(
                owned_story_npcs.owned_story_controller, "_scope", side_effect=scope
            ),
            patch.object(
                owned_story_npcs.owned_story_refresh,
                "pending",
                return_value={"pending": True},
            ),
            patch(
                "wakfu_server.achievements.storage.load_locked", return_value=state()
            ),
            patch("wakfu_server.environment_interactions._guard"),
        ):
            spawned = owned_story_npcs.spawn_packets(
                store.db, store, store.current, native=native, context_bootstrap=True
            )
            self.assertEqual(len(spawned), 1)
            actor = owned_story_npcs.actor_id(store.current["instance_id"], 1)
            self.assertEqual(struct.unpack_from(">q", spawned[0][1], 3)[0], actor)

            self.assertEqual(owned_story_npcs.rows(store.db, store, store.current), [])
            with self.assertRaisesRegex(ValueError, "actual scoped NPC"):
                owned_story_npcs.argument_actor(store.db, store, store.current, 3801)
            with self.assertRaisesRegex(ValueError, "unavailable or outside"):
                owned_story_npcs._locked(
                    store, store.db, 7, "generation", store.current, actor, 697
                )
            self.assertIn(False, scope_calls)
            self.assertIn(True, scope_calls)

            # Rendering never bypasses the genuine final-victory flag.
            with patch.object(
                owned_story_npcs.owned_story_controller,
                "_scope",
                return_value=({"id": "zinit-reef-980"}, set()),
            ):
                self.assertEqual(
                    owned_story_npcs.spawn_packets(
                        store.db,
                        store,
                        store.current,
                        native=native,
                        context_bootstrap=True,
                    ),
                    [],
                )

    def test_world_bootstrap_places_owned_npc_before_story_continuation_packets(self):
        from wakfu_server.application.world_publication import WorldPublication
        from wakfu_server import (
            dungeon_context,
            dungeon_native_flow,
            dungeon_object_states,
            dungeon_optional_continuations,
            dungeon_runtime,
            generic_transports,
            native_scene_start,
        )

        class BootstrapDB:
            def execute(self, sql, *_args):
                self.sql = sql
                return self

            def fetchone(self):
                if "fighting" in self.sql:
                    return {"fighting": False}
                return {"current_room": 1, "status": "active"}

        class BootstrapStore:
            @contextmanager
            def connection(self):
                yield BootstrapDB()

        events = []

        class NativeTransports:
            def bootstrap(self, _character, **_options):
                events.append("native")
                return ((1, b"native"),)

        class Runtime:
            STORE = BootstrapStore()
            native_transports = NativeTransports()

            @staticmethod
            def is_dungeon_run(_instance):
                return True

        configuration = {"topology": {}}
        with (
            patch.object(dungeon_context, "for_instance", return_value={}),
            patch.object(
                dungeon_runtime,
                "configuration_for_instance",
                return_value=({}, configuration),
            ),
            patch.object(
                owned_story_npcs,
                "spawn_packets",
                side_effect=lambda *_a, **_k: (
                    events.append("owned-npc") or ((12608, b"npc"),)
                ),
            ),
            patch.object(
                dungeon_optional_continuations,
                "packets",
                side_effect=lambda *_a, **_k: (
                    events.append("optional") or ((13900, b"optional"),)
                ),
            ),
            patch.object(
                native_scene_start,
                "packets",
                side_effect=lambda *_a, **_k: (
                    events.append("cinematic") or ((13901, b"cinematic"),)
                ),
            ),
            patch.object(dungeon_native_flow, "enabled", return_value=False),
            patch.object(
                dungeon_object_states,
                "packets",
                side_effect=lambda *_a, **_k: (
                    events.append("states") or ((13902, b"states"),)
                ),
            ),
            patch.object(generic_transports, "_CATALOG", []),
        ):
            packets = WorldPublication(Runtime()).owned_native_bootstrap(
                {"id": 41, "map_id": 980, "instance_id": (1 << 57) + 47}
            )
        self.assertEqual(
            [payload for _opcode, payload in packets],
            [b"native", b"npc", b"states", b"optional", b"cinematic"],
        )
        self.assertLess(events.index("owned-npc"), events.index("optional"))
        self.assertLess(events.index("owned-npc"), events.index("cinematic"))

    def test_world_bootstrap_accepts_authenticated_roomless_885_and_rejects_mismatches(
        self,
    ):
        """The real publication consumer keeps roomless owned scenes on baseline bootstrap."""
        from wakfu_server.application.world_publication import WorldPublication
        from wakfu_server import (
            dungeon_context,
            dungeon_native_flow,
            dungeon_object_states,
            dungeon_optional_continuations,
            dungeon_runtime,
            generic_transports,
            native_scene_start,
            owned_noncombat_context,
            owned_story_controller,
        )

        configuration = json.loads(
            (
                ROOT
                / "server/wakfu_server/maps/owned_story_profiles/astrub-pizzlarva-885.configuration.json"
            ).read_text()
        )
        character = {
            "id": 41,
            "account_id": 7,
            "map_id": 885,
            "instance_id": (1 << 57) + 47,
            "x": 0,
            "y": 0,
            "z": 0,
        }
        policy = owned_story_controller.policy(configuration)
        self.assertEqual(configuration["topology"]["rooms"], [])
        self.assertEqual(
            configuration["topology"]["policy"], owned_noncombat_context.NARRATIVE
        )

        class DB:
            sql = ""

            def execute(self, sql, *_args):
                self.sql = sql
                return self

            def fetchone(self):
                if "fighting" in self.sql:
                    return {"fighting": False}
                if "dungeon_room_runs" in self.sql:
                    return None
                raise AssertionError(f"Unexpected bootstrap SQL: {self.sql}")

        db = DB()

        class Store:
            @contextmanager
            def connection(self):
                yield db

        class Transports:
            def bootstrap(self, _character, **_options):
                return ((13974, b"native-baseline"),)

        class Runtime:
            STORE = Store()
            native_transports = Transports()

            @staticmethod
            def is_dungeon_run(_instance):
                return True

        events = []
        publication = WorldPublication(Runtime())

        def run(scope):
            with (
                patch.object(dungeon_context, "for_instance", return_value={}),
                patch.object(
                    dungeon_runtime,
                    "configuration_for_instance",
                    return_value=({}, configuration),
                ),
                patch.object(
                    owned_story_controller, "_scope", return_value=(scope, set())
                ) as owner_scope,
                patch.object(
                    owned_story_npcs,
                    "spawn_packets",
                    side_effect=lambda *_a, **_k: (
                        events.append("npc") or ((12608, b"npc"),)
                    ),
                ),
                patch.object(
                    dungeon_optional_continuations,
                    "packets",
                    side_effect=lambda *_a, **_k: (
                        events.append("optional") or ((13900, b"optional"),)
                    ),
                ),
                patch.object(
                    native_scene_start,
                    "packets",
                    side_effect=lambda *_a, **_k: (
                        events.append("continuation") or ((13901, b"continuation"),)
                    ),
                ),
                patch.object(
                    dungeon_native_flow,
                    "enabled",
                    side_effect=AssertionError("room progression queried"),
                ),
                patch.object(
                    dungeon_object_states,
                    "packets",
                    side_effect=AssertionError("room objects queried"),
                ),
                patch.object(generic_transports, "_CATALOG", []),
            ):
                result = publication.owned_native_bootstrap(character)
            return result, owner_scope

        result, owner_scope = run(policy)
        self.assertEqual(
            result,
            (
                (13974, b"native-baseline"),
                (12608, b"npc"),
                (13900, b"optional"),
                (13901, b"continuation"),
            ),
        )
        self.assertEqual(events, ["npc", "optional", "continuation"])
        owner_scope.assert_called_once_with(
            db, Runtime.STORE, character, check_position=False, lock=False
        )

        wrong_scope = dict(policy, instance_id=policy.get("instance_id", 0) + 1)
        with self.assertRaisesRegex(ValueError, "pinned owner scope"):
            run(wrong_scope)

        # An unqualified ordinary dungeon still needs committed room progress.
        ordinary = {"topology": {"asset_map_id": 885, "rooms": []}}
        with (
            patch.object(dungeon_context, "for_instance", return_value={}),
            patch.object(
                dungeon_runtime,
                "configuration_for_instance",
                return_value=({}, ordinary),
            ),
            patch.object(
                owned_story_controller,
                "_scope",
                side_effect=AssertionError("ordinary path authenticated as owned"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "no committed room progress"):
                publication.owned_native_bootstrap(character)

    def test_dispatcher_flushes_positions_before_begin_and_rejects_nonidle_session(
        self,
    ):
        class Barrier:
            def __enter__(self):
                events.append("barrier-in")

            def __exit__(self, *_args):
                events.append("barrier-out")

        class Positions:
            def account_barrier(self, _account):
                return Barrier()

        class State:
            account_id = 7
            generation = "generation"
            character = {"id": 41, "account_id": 7, "map_id": 980, "instance_id": 55}
            opcode = 13222
            body = struct.pack(">qq", owned_story_npcs.actor_id((1 << 57) + 47, 1), 697)
            npc_dialogue_session = None
            loaded = True
            fight = spectator_session = environment_ticket = None

        class Runtime:
            STORE = _Store()
            POSITIONS = Positions()

            def flush_positions(self, **_kwargs):
                events.append("flush")

        class Session:
            state = State()
            runtime = Runtime()
            approach_pending = True

            @staticmethod
            def environment_blocked():
                return False

            def approach_actor(self, _predicate, *, geometry):
                self.geometry = geometry
                events.append("approach")
                return self.approach_pending

            @staticmethod
            def publish_settled_quest_packets(_packets):
                events.append("publish")

        events = []
        with (
            patch(
                "wakfu_server.owned_story_actor_operations.handle", return_value=False
            ),
            patch.object(owned_story_npcs, "recognizes", return_value=True),
            patch.object(
                owned_story_npcs,
                "rows",
                return_value=[
                    {
                        "actor_id": owned_story_npcs.actor_id((1 << 57) + 47, 1),
                        "action_ids": [697],
                        "map_id": 980,
                    }
                ],
            ),
            patch(
                "wakfu_server.npc_approach_target.approach_cells", return_value={(1, 2)}
            ),
            patch(
                "wakfu_server.combat_geometry.prepare_geometry", return_value="prepared"
            ),
            patch("wakfu_server.combat_terrain.map_geometry", return_value="raw"),
            patch.object(
                owned_story_npcs, "begin", return_value=(object(), [b"open"])
            ) as begin,
        ):
            self.assertTrue(owned_story_npc_dispatch.handle(Session()))
            self.assertEqual(events, ["barrier-in", "flush", "approach", "barrier-out"])
            begin.assert_not_called()

            # Once the same native approach is complete, begin and packet
            # publication happen in order after the buffered move flush.
            events.clear()
            Session.approach_pending = False
            self.assertTrue(owned_story_npc_dispatch.handle(Session()))
            self.assertEqual(
                events, ["barrier-in", "flush", "approach", "publish", "barrier-out"]
            )
            begin.assert_called_once()

        Session.state.fight = object()
        with patch.object(owned_story_npcs, "recognizes", return_value=True), patch(
            "wakfu_server.owned_story_actor_operations.handle", return_value=False
        ):
            with self.assertRaisesRegex(ValueError, "ready idle owner"):
                owned_story_npc_dispatch.handle(Session())


if __name__ == "__main__":
    unittest.main()
