"""Dispatcher deadline coverage using the live nested helper AST, no socket loop."""
import ast
import copy
import os
from pathlib import Path
import struct
import textwrap
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase

from wakfu_server import exploration_artifact_actions

SERVER = Path(
    os.environ.get(
        "WAKFU_DISPATCH_SERVER",
        str(Path(__file__).resolve().parents[1] / "local_game_server.py"),
    )
)
HELPER_NAMES = (
    "cancel_artifact_action",
    "artifact_owner_identity",
    "artifact_position_allowed",
    "admit_artifact_action",
    "complete_artifact_action",
    "publish_public_transport",
)


class FakeClock:
    def __init__(self):
        self.now = 50.0

    def monotonic(self):
        return self.now


class FakeWorld:
    def __init__(self, events):
        self.events = events

    def broadcast(self, *args):
        self.events.append(("broadcast", args))

    def leave(self, *args):
        self.events.append(("leave", args))


class FakeStore:
    def __init__(self, events, state):
        self.events = events
        self.state = state

    def current_character_session(self, *args):
        self.events.append(("session_check", args))
        return self.state["session_valid"]

    def character(self, *args):
        self.events.append(("fresh_character", args))
        return copy.deepcopy(self.state["fresh_owner"])

    def transition_map(self, account_id, generation, character_id, owner, destination):
        self.events.append(
            (
                "transition",
                account_id,
                generation,
                character_id,
                copy.deepcopy(destination),
            )
        )
        result = dict(owner)
        result.update(destination)
        return result


def fake_atomic_artifact_transition(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    expected_plan,
    source_allowed,
    position_allowed=None,
    blocked=False,
):
    """Keep resolver/plan comparisons live; replace only transactional I/O."""
    store.events.append(("atomic_transition", account_id, generation, character_id))
    if not store.current_character_session(account_id, generation, character_id):
        raise ValueError("Exploration action session expired")
    actual = store.character(account_id, character_id)
    if actual.get("id") != character_id or actual.get("account_id") != account_id:
        raise ValueError("Exploration action owner changed")
    current = exploration_artifact_actions.resolve(
        actual,
        body,
        source_allowed=source_allowed,
        position_allowed=position_allowed,
        blocked=blocked,
    )
    for key in (
        "origin",
        "destination",
        "direction",
        "delay_ms",
        "source_map",
        "interactive_element_id",
        "native_definition_id",
        "native_group_id",
        "native_action_id",
        "native_effect_reference",
        "artifact_reference",
    ):
        if current[key] != expected_plan.get(key):
            raise ValueError("Deferred exploration artifact action authority changed")
    return store.transition_map(
        account_id, generation, character_id, actual, current["destination"]
    )


def _dispatcher_helper_harness(state, events, clock):
    tree = ast.parse(SERVER.read_text())
    nodes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in HELPER_NAMES:
            nodes[node.name] = node
    if set(nodes) != set(HELPER_NAMES):
        raise AssertionError(
            f"dispatcher helper AST missing: {set(HELPER_NAMES) - set(nodes)}"
        )

    helper_source = textwrap.indent(
        "\n\n".join(ast.unparse(nodes[name]) for name in HELPER_NAMES), "    "
    )
    source = f"""\
def build(env):
    account_id = env["account_id"]
    generation = env["generation"]
    loaded = env["loaded"]
    character = env["character"]
    pending_artifact_action = None
    environment_ticket = env["environment_ticket"]
    position = dict(character)
    movement_state = env["movement_state"]
    connection = env["connection"]
    service = env["service"]
    time = env["time"]
    STORE = env["STORE"]
    WORLD = env["WORLD"]
    POSITIONS = env["POSITIONS"]
    Movement = env["Movement"]
    cancel_crafting = env["cancel_crafting"]
    send = env["send"]
    record = env["record"]
    environment_blocked = env["environment_blocked"]
    flush_positions = env["flush_positions"]
    owned_native_bootstrap = env["owned_native_bootstrap"]
    transports = env["transports"]
    publish_entry_inventory = env["publish_entry_inventory"]
    join_world = env["join_world"]
    mark_static_sync_pending = env["mark_static_sync_pending"]
    def set_loaded(value):
        nonlocal loaded
        loaded = value
    def set_character(value):
        nonlocal character
        character = value
    def set_environment_ticket(value):
        nonlocal environment_ticket
        environment_ticket = value
{helper_source}
    def snapshot():
        return dict(character=character, position=position, pending=pending_artifact_action)
    return dict(admit=admit_artifact_action, complete=complete_artifact_action,
                cancel=cancel_artifact_action, snapshot=snapshot,
                set_loaded=set_loaded, set_character=set_character,
                set_environment_ticket=set_environment_ticket)
"""
    namespace = {}
    exec(compile(source, str(SERVER), "exec"), namespace)
    return namespace["build"](
        dict(
            account_id=7,
            generation="lease-a",
            loaded=True,
            character=copy.deepcopy(state["character"]),
            environment_ticket=None,
            movement_state=state["movement_state"],
            connection="connection",
            service="dispatcher",
            time=clock,
            STORE=FakeStore(events, state),
            WORLD=FakeWorld(events),
            POSITIONS=SimpleNamespace(
                attach=lambda *args: events.append(("attach", args))
            ),
            Movement=lambda position: SimpleNamespace(approved=[]),
            cancel_crafting=lambda: events.append(("cancel_crafting",)),
            send=lambda conn, service, opcode, body: events.append(
                ("send", opcode, body)
            ),
            record=lambda **fields: events.append(("record", fields)),
            environment_blocked=lambda: state["blocked"],
            flush_positions=lambda **fields: events.append(("flush", fields)),
            owned_native_bootstrap=lambda owner, direction=None: [
                (13974, bytes([direction or 0]))
            ],
            transports=SimpleNamespace(
                bootstrap=lambda owner, route: [(13974, b"ordinary")]
            ),
            publish_entry_inventory=lambda before: events.append(
                ("inventory", before["id"])
            ),
            join_world=lambda *args, **kwargs: events.append(("join", args, kwargs)),
            mark_static_sync_pending=lambda: events.append(("static_sync",)),
        )
    )


def _publication_harness(function_node, route, saved, events, generic_route):
    helper_source = textwrap.indent(ast.unparse(function_node), "    ")
    function_name = function_node.name
    source = f"""\
def build(env):
    account_id = 7
    generation = "lease-a"
    character = copy.deepcopy(env["character"])
    position = {{key: character[key] for key in ("x", "y", "z")}}
    movement_state = env["movement_state"]
    connection = "connection"
    service = "dispatcher"
    WORLD = env["WORLD"]
    POSITIONS = env["POSITIONS"]
    Movement = env["Movement"]
    cancel_crafting = env["cancel_crafting"]
    owned_native_bootstrap = env["owned_native_bootstrap"]
    transports = env["transports"]
    send = env["send"]
    publish_entry_inventory = env["publish_entry_inventory"]
    join_world = env["join_world"]
    mark_static_sync_pending = env["mark_static_sync_pending"]
    record = env["record"]
{helper_source}
    {function_name}({route!r}, {saved!r}, generic_route=env["generic_route"])
    def snapshot():
        return dict(character=character, position=position, approved=movement_state.approved)
    return snapshot()
"""
    namespace = {"copy": copy}
    exec(compile(source, str(SERVER), "exec"), namespace)
    env = dict(
        character=artifact_actor(x=-10, y=-5, map_id=527),
        movement_state=SimpleNamespace(approved=[(-10, -5, 0)]),
        WORLD=FakeWorld(events),
        POSITIONS=SimpleNamespace(attach=lambda *args: events.append(("attach", args))),
        Movement=lambda current: SimpleNamespace(approved=[]),
        cancel_crafting=lambda: events.append(("cancel_crafting",)),
        owned_native_bootstrap=lambda owner, direction=None: [
            (13974, bytes((direction or 0,)))
        ],
        transports=SimpleNamespace(
            bootstrap=lambda owner, current: [(13974, b"ordinary")]
        ),
        send=lambda conn, service, opcode, body: events.append(("send", opcode, body)),
        publish_entry_inventory=lambda before: events.append(
            ("inventory", before["id"])
        ),
        join_world=lambda *args, **kwargs: events.append(("join", args, kwargs)),
        mark_static_sync_pending=lambda: events.append(("static_sync",)),
        record=lambda **fields: events.append(("record", fields)),
        generic_route=generic_route,
    )
    return namespace["build"](env)


def _publication_functions():
    old_path = Path(
        os.environ.get(
            "WAKFU_FROZEN_ACTIVE_SERVER",
            str(
                Path(__file__).resolve().parents[2]
                / ".runtime/brumas-free-20261028/prepared/source/server/local_game_server.py"
            ),
        )
    )
    old_tree = ast.parse(old_path.read_text())
    old_dispatch = next(
        node
        for node in ast.walk(old_tree)
        if isinstance(node, ast.If)
        and node.lineno == 15742
        and "12296" in ast.unparse(node.test)
    )
    old_try = next(node for node in old_dispatch.body if isinstance(node, ast.Try))
    current_tree = ast.parse(SERVER.read_text())
    current = next(
        node
        for node in ast.walk(current_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "publish_public_transport"
    )
    old = ast.fix_missing_locations(
        ast.FunctionDef(
            name="function",
            args=current.args,
            body=[
                ast.Nonlocal(names=["character", "position", "movement_state"]),
                *old_try.orelse,
            ],
            decorator_list=[],
            returns=None,
            type_comment=None,
        )
    )
    return old, current


def artifact_actor(**changes):
    actor = dict(
        id=41,
        account_id=7,
        map_id=1120,
        instance_id=0,
        x=-92,
        y=-8,
        z=0,
        exploration_secrets={"account_item_refs": [18385]},
        account_quest_items=[],
    )
    actor.update(changes)
    return actor


def artifact_route(owner, body):
    # The action catalog and coordinate/criterion logic stay live. Only the
    # native-catalog DB and published terrain reads are external data seams.
    with patch.object(
        exploration_artifact_actions, "_verify_source", return_value=True
    ), patch.object(
        exploration_artifact_actions,
        "_walkable",
        return_value=True,
    ):
        return exploration_artifact_actions.resolve(
            owner,
            body,
            source_allowed=lambda *_: True,
            position_allowed=lambda current: current["x"] == -92,
            blocked=False,
        )


class ExplorationArtifactDispatcherTests(unittest.TestCase):
    BODY = struct.pack(">qHH", 27796, 0, 0)  # original S.I.D.; 1520 ms branch

    def setup_dispatcher(self):
        clock = FakeClock()
        owner = artifact_actor()
        state = dict(
            character=owner,
            fresh_owner=copy.deepcopy(owner),
            movement_state=SimpleNamespace(approved=[(-92, -8, 0)]),
            blocked=False,
            session_valid=True,
        )
        events = []
        with patch.object(
            exploration_artifact_actions, "_verify_source", return_value=True
        ), patch.object(
            exploration_artifact_actions,
            "_walkable",
            return_value=True,
        ):
            route = exploration_artifact_actions.resolve(
                owner,
                self.BODY,
                source_allowed=lambda *_: True,
                position_allowed=lambda current: current["x"] == -92,
                blocked=False,
            )
        self.assertEqual(route["delay_ms"], 1520)
        helpers = _dispatcher_helper_harness(state, events, clock)
        return helpers, state, events, clock, route

    def test_pending_deadline_does_not_block_and_due_transition_uses_fresh_owner_once(
        self,
    ):
        helpers, state, events, clock, route = self.setup_dispatcher()
        self.assertTrue(helpers["admit"](route, self.BODY, state["character"]))
        before = helpers["snapshot"]()
        self.assertIsNotNone(before["pending"])
        self.assertFalse(any(event[0] == "transition" for event in events))
        self.assertTrue(any(event[0] in ("send", "broadcast") for event in events))

        clock.now += 1.519
        helpers["complete"]()
        self.assertIsNotNone(helpers["snapshot"]()["pending"])
        self.assertFalse(any(event[0] == "transition" for event in events))

        # The due callback re-reads the account's current owner and current
        # policy/position through the actual resolver before committing once.
        state["fresh_owner"] = copy.deepcopy(state["character"])
        clock.now += 0.01
        with patch.object(
            exploration_artifact_actions, "_verify_source", return_value=True
        ), patch.object(
            exploration_artifact_actions,
            "_walkable",
            return_value=True,
        ), patch.object(
            exploration_artifact_actions,
            "transition",
            side_effect=fake_atomic_artifact_transition,
        ):
            helpers["complete"]()
            helpers["complete"]()
        self.assertEqual(sum(event[0] == "transition" for event in events), 1)
        self.assertEqual(sum(event[0] == "join" for event in events), 1)
        self.assertEqual(helpers["snapshot"]()["character"]["x"], -88)
        self.assertIsNone(helpers["snapshot"]()["pending"])
        names = [event[0] for event in events]
        self.assertLess(names.index("session_check"), names.index("transition"))
        self.assertLess(names.index("fresh_character"), names.index("transition"))
        self.assertLess(names.index("transition"), names.index("leave"))

    def test_stale_owner_move_private_instance_combat_logout_and_cancel_all_drop_pending(
        self,
    ):
        mutations = (
            ("stale-owner", lambda h, s: h["set_character"](artifact_actor(id=42))),
            ("moved", lambda h, s: h["set_character"](artifact_actor(x=-91))),
            (
                "instance",
                lambda h, s: h["set_character"](artifact_actor(instance_id=9)),
            ),
            ("combat", lambda h, s: s.update(blocked=True)),
            ("logout", lambda h, s: h["set_loaded"](False)),
            ("cancel", lambda h, s: h["cancel"]("test cancellation")),
        )
        for label, mutate in mutations:
            with self.subTest(case=label):
                helpers, state, events, clock, route = self.setup_dispatcher()
                self.assertTrue(helpers["admit"](route, self.BODY, state["character"]))
                mutate(helpers, state)
                clock.now += 10
                with patch.object(
                    exploration_artifact_actions, "_verify_source", return_value=True
                ), patch.object(
                    exploration_artifact_actions,
                    "_walkable",
                    return_value=True,
                ), patch.object(
                    exploration_artifact_actions,
                    "transition",
                    side_effect=fake_atomic_artifact_transition,
                ):
                    helpers["complete"]()
                self.assertIsNone(helpers["snapshot"]()["pending"])
                self.assertFalse(any(event[0] == "transition" for event in events))

    def test_second_action_cancels_first_and_repeat_due_cannot_duplicate_transition(
        self,
    ):
        helpers, state, events, clock, route = self.setup_dispatcher()
        self.assertTrue(helpers["admit"](route, self.BODY, state["character"]))
        helpers["cancel"]("Another interactive action started")
        self.assertIsNone(helpers["snapshot"]()["pending"])
        self.assertTrue(helpers["admit"](route, self.BODY, state["character"]))
        clock.now += 2
        state["fresh_owner"] = copy.deepcopy(state["character"])
        with patch.object(
            exploration_artifact_actions, "_verify_source", return_value=True
        ), patch.object(
            exploration_artifact_actions,
            "_walkable",
            return_value=True,
        ), patch.object(
            exploration_artifact_actions,
            "transition",
            side_effect=fake_atomic_artifact_transition,
        ):
            helpers["complete"]()
            helpers["complete"]()
        self.assertEqual(sum(event[0] == "transition" for event in events), 1)
        self.assertEqual(sum(event[0] == "join" for event in events), 1)
        self.assertEqual(
            sum(
                event[0] == "record"
                and event[1].get("event") == "exploration_artifact_cancelled"
                for event in events
            ),
            1,
        )

    def test_ordinary_12296_publication_matches_frozen_active_dispatcher(self):
        old, current = _publication_functions()
        destination = dict(map_id=527, instance_id=0, x=-31, y=-18, z=7)
        saved = dict(
            id=41,
            account_id=7,
            map_id=527,
            instance_id=0,
            x=-31,
            y=-18,
            z=7,
        )
        cases = (
            (True, False),
            (False, False),
            (True, True),
        )
        for generic_route, paid in cases:
            with self.subTest(generic_route=generic_route, paid=paid):
                route = dict(direction=4, destination=destination)
                if paid:
                    route["item_payment"] = dict(reference=33075, quantity=1)
                old_events, current_events = [], []
                old_state = _publication_harness(
                    old, route, saved, old_events, generic_route
                )
                current_state = _publication_harness(
                    current, route, saved, current_events, generic_route
                )
                self.assertEqual(current_events, old_events)
                self.assertEqual(current_state, old_state)

    def test_dispatcher_ast_wires_deadline_idle_and_second_action_cancel(self):
        tree = ast.parse(SERVER.read_text())
        source = ast.unparse(tree)
        self.assertIn(
            "elif loaded and (opcode == 12296 or artifact_action_request)", source
        )
        self.assertIn(
            "admit_artifact_action(destination_route, body, artifact_owner)", source
        )
        self.assertIn("complete_artifact_action()", source)
        second_action = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "pending_artifact_action is not None" in ast.unparse(node.test)
            and "opcode == 12870" in ast.unparse(node.test)
        )
        self.assertIn("cancel_artifact_action", ast.unparse(second_action.body[0]))


class ExplorationArtifactAtomicTransitionPostgresTests(PostgresCase):
    BODY = struct.pack(">qHH", 27540, 0, 0)  # Original map1118 S.I.D. action.

    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "artifact-dispatch-" + uuid.uuid4().hex[:12], "test-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Artifact Actor")
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.set_location(3, -99, 10)

    def set_location(self, x, y, z, *, map_id=1118, instance_id=0):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (map_id, instance_id, x, y, z, self.character["id"]),
            )

    def actor(self):
        return self.store.character(self.account, self.character["id"])

    @staticmethod
    def source_allowed(actor, source):
        positions = {
            tuple(point[key] for key in ("x", "y", "z"))
            for point in source["approach_positions"]
        }
        return tuple(actor[key] for key in ("x", "y", "z")) in positions

    def admitted_plan(self):
        actor = self.actor()
        return exploration_artifact_actions.admit(
            self.store,
            self.account,
            self.generation,
            actor["id"],
            self.BODY,
            source_allowed=self.source_allowed,
        )

    def transition(self, plan):
        actor = self.actor()
        return exploration_artifact_actions.transition(
            self.store,
            self.account,
            self.generation,
            actor["id"],
            self.BODY,
            expected_plan=plan,
            source_allowed=self.source_allowed,
        )

    def snapshot(self):
        actor = self.actor()
        with self.store.connection() as db:
            xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["xp"]
            kamas = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (self.account,),
            ).fetchone()["kamas"]
            account_items = db.execute(
                "SELECT reference,quantity FROM account_quest_items WHERE account_id=%s ORDER BY reference",
                (self.account,),
            ).fetchall()
            inventory = db.execute(
                "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                "WHERE character_id=%s ORDER BY uid",
                (self.character["id"],),
            ).fetchall()
        return dict(
            location=tuple(
                actor[key] for key in ("map_id", "instance_id", "x", "y", "z")
            ),
            health=(actor["hp"], actor["health_dead"]),
            xp=xp,
            kamas=kamas,
            account_items=[tuple(row.values()) for row in account_items],
            inventory=[tuple(row.values()) for row in inventory],
        )

    def set_policy(self, enabled):
        from psycopg.types.json import Jsonb
        from wakfu_server.exploration_secrets import SETTING

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb(dict(version=1, unlock_all=enabled)), SETTING),
            )

    def insert_active_fight(self):
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight, self.character["id"], self.account),
            )
        return fight

    def clear_fight(self, fight):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM combat_fight_participants WHERE fight_id=%s", (fight,)
            )
            db.execute("DELETE FROM combat_fights WHERE id=%s", (fight,))

    def test_atomic_admit_and_deferred_transition_guard_matrix(self):
        # Original source/action/predicates stay live. Only the installed native
        # catalog DB and terrain-reader dependencies are stubbed in this matrix.
        with patch.object(
            exploration_artifact_actions, "_verify_source", return_value=True
        ), patch.object(
            exploration_artifact_actions,
            "_walkable",
            return_value=True,
        ):
            initial = self.snapshot()
            plan = self.admitted_plan()
            self.assertEqual(plan["delay_ms"], 3000)
            self.assertEqual(self.snapshot(), initial)

            self.transition(plan)
            after_success = self.snapshot()
            self.assertEqual(
                after_success["location"],
                tuple(
                    plan["destination"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ),
            )
            for key in ("health", "xp", "kamas", "account_items", "inventory"):
                self.assertEqual(after_success[key], initial[key], key)
            with self.assertRaises(ValueError):
                self.transition(plan)
            self.assertEqual(self.snapshot(), after_success)

            self.set_location(3, -99, 10)
            policy_plan = self.admitted_plan()
            self.set_policy(False)
            before_reject = self.snapshot()
            with self.assertRaisesRegex(ValueError, "owned by this account"):
                self.transition(policy_plan)
            self.assertEqual(self.snapshot(), before_reject)
            self.set_policy(True)

            self.set_location(3, -99, 10)
            source_plan = self.admitted_plan()
            self.set_location(1, -99, 10)
            before_reject = self.snapshot()
            with self.assertRaises(ValueError):
                self.transition(source_plan)
            self.assertEqual(self.snapshot(), before_reject)

            self.set_location(3, -99, 10)
            stale_plan = self.admitted_plan()
            old_generation = self.generation
            self.generation = self.store.begin_session(self.account, ttl=7200)
            self.store.select_character(
                self.account, self.generation, self.character["id"]
            )
            before_reject = self.snapshot()
            with self.assertRaises(ValueError):
                exploration_artifact_actions.transition(
                    self.store,
                    self.account,
                    old_generation,
                    self.character["id"],
                    self.BODY,
                    expected_plan=stale_plan,
                    source_allowed=self.source_allowed,
                )
            self.assertEqual(self.snapshot(), before_reject)

            fight_plan = self.admitted_plan()
            fight = self.insert_active_fight()
            before_reject = self.snapshot()
            with self.assertRaisesRegex(ValueError, "combate"):
                self.transition(fight_plan)
            self.assertEqual(self.snapshot(), before_reject)
            self.clear_fight(fight)

            dead_plan = self.admitted_plan()
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET hp=0,hp_damage=max_hp,health_dead=TRUE,hp_zero_valid=FALSE "
                    "WHERE id=%s",
                    (self.character["id"],),
                )
            before_reject = self.snapshot()
            with self.assertRaisesRegex(ValueError, "living owned actor"):
                self.transition(dead_plan)
            self.assertEqual(self.snapshot(), before_reject)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET hp=max_hp,hp_damage=0,health_dead=FALSE "
                    "WHERE id=%s",
                    (self.character["id"],),
                )

            occupation_plan = self.admitted_plan()
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO environment_interaction_tickets "
                    "(token,account_id,generation,character_id,map_id,object_id,x,y,z,due_at,is_hero,state) "
                    "VALUES(%s,%s,%s,%s,1134,27704,0,0,0,%s,FALSE,'active')",
                    (
                        uuid.uuid4(),
                        self.account,
                        self.generation,
                        self.character["id"],
                        datetime.now(timezone.utc) + timedelta(minutes=1),
                    ),
                )
            before_reject = self.snapshot()
            with self.assertRaisesRegex(ValueError, "environment occupation"):
                self.transition(occupation_plan)
            self.assertEqual(self.snapshot(), before_reject)

            # DB combat admission rejects before any dispatcher script is staged.
            self.set_location(3, -99, 10)
            fight = self.insert_active_fight()
            before_reject = self.snapshot()
            with self.assertRaisesRegex(ValueError, "combate"):
                self.admitted_plan()
            self.assertEqual(self.snapshot(), before_reject)
            self.clear_fight(fight)


if __name__ == "__main__":
    unittest.main()
