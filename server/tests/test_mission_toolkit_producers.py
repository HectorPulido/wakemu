"""Production mission-toolkit producers preserve transaction and event identity."""

import ast
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.application.session import Session

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server"


def module(relative):
    return ast.parse((ROOT / relative).read_text(encoding="utf-8"))


def function(relative, name, class_name=None):
    tree = module(relative)
    nodes = tree.body
    if class_name is not None:
        cls = next(
            n for n in nodes if isinstance(n, ast.ClassDef) and n.name == class_name
        )
        nodes = cls.body
    return next(
        n
        for n in nodes
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )


def call_named(root, dotted_name):
    return [
        n
        for n in ast.walk(root)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == dotted_name
    ]


def call_keywords(call):
    return {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}


def enclosing(root, target, kind):
    """Return the nearest syntactic transaction/success boundary containing target."""
    parents = {}
    for parent in ast.walk(root):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    node = target
    while node in parents:
        node = parents[node]
        if isinstance(node, kind):
            return node
    return None


def source_has(node, needle):
    return needle in ast.unparse(node)


class MissionToolkitProducerTests(unittest.TestCase):
    def assert_account_lock_precedes_lease(self, node):
        code = ast.unparse(node)
        lease = code.find("_lease(")
        if lease < 0:
            lease = code.find("_occupation(")
        self.assertGreaterEqual(lease, 0, code)
        self.assertLess(code.index("SELECT id FROM accounts"), lease)

    def test_planting_success_emits_seed_reference_once_inside_account_transaction(
        self,
    ):
        complete = function("maps/planting.py", "complete")
        self.assert_account_lock_precedes_lease(complete)
        (settlement,) = call_named(complete, "mission_toolkit.settle")
        kwargs = call_keywords(settlement)
        self.assertEqual(kwargs["kind"], "'planting'")
        self.assertEqual(kwargs["reference"], "item['reference']")
        self.assertEqual(
            ast.unparse(
                enclosing(complete, settlement, ast.With).items[0].context_expr
            ),
            "store.connection()",
        )
        success_guard = enclosing(complete, settlement, ast.If)
        self.assertIsNotNone(success_guard)
        self.assertEqual(ast.unparse(success_guard.test), "success")

    def test_monster_and_resource_harvest_emit_actual_product_quantities_after_success(
        self,
    ):
        monster = function("maps/monster_collect.py", "complete", "Harvests")
        self.assert_account_lock_precedes_lease(monster)
        (settle,) = call_named(monster, "mission_toolkit.settle")
        kwargs = call_keywords(settle)
        self.assertEqual(kwargs["kind"], "'monster_harvest'")
        self.assertEqual(kwargs["reference"], "reference")
        self.assertEqual(kwargs["quantity"], "quantity")
        monster_source = ast.unparse(monster)
        self.assertLess(
            monster_source.index("if result == 3"),
            monster_source.index("mission_toolkit.settle"),
        )
        self.assertLess(
            monster_source.index("self.cancel(character_id)"),
            monster_source.index("mission_toolkit.settle"),
        )

        resource = function("maps/resource_collect.py", "complete")
        self.assert_account_lock_precedes_lease(resource)
        settles = call_named(resource, "mission_toolkit.settle")
        self.assertEqual(len(settles), 2)
        by_kind = {call_keywords(call)["kind"]: call for call in settles}
        action_settle = by_kind["'resource_action_completed'"]
        product_settle = by_kind["'resource_harvest'"]
        action_kwargs = call_keywords(action_settle)
        self.assertEqual(action_kwargs["reference"], "rule['action_id']")
        self.assertEqual(action_kwargs["quantity"], "1")
        product_kwargs = call_keywords(product_settle)
        self.assertEqual(product_kwargs["reference"], "item_reference")
        self.assertEqual(product_kwargs["quantity"], "quantity")
        product_guard = enclosing(resource, product_settle, ast.If)
        self.assertTrue(source_has(product_guard, "product"))
        self.assertLess(action_settle.lineno, product_guard.lineno)
        self.assertTrue(
            source_has(enclosing(resource, action_settle, ast.With), "store.connection")
        )
        resource_source = ast.unparse(resource)
        self.assertLess(
            resource_source.index("if result == 3"),
            resource_source.index("resource_action_completed"),
        )

    def test_crafting_settlement_uses_completed_recipe_batch_inside_account_transaction(
        self,
    ):
        complete = function("items/crafting.py", "complete")
        self.assert_account_lock_precedes_lease(complete)
        (settle,) = call_named(complete, "mission_toolkit.settle")
        kwargs = call_keywords(settle)
        self.assertEqual(kwargs["kind"], "'craft_completed'")
        self.assertEqual(kwargs["reference"], "row['recipe_id']")
        self.assertEqual(kwargs["quantity"], "row['batch_count']")
        transaction = enclosing(complete, settle, ast.With)
        self.assertIsNotNone(transaction)
        self.assertEqual(
            ast.unparse(transaction.items[0].context_expr), "store.connection()"
        )
        self.assertLess(
            ast.unparse(complete).index("state='completed'"),
            ast.unparse(complete).index("mission_toolkit.settle"),
        )

    def test_fresh_combat_service_uses_committed_original_breeds_and_fight_id(self):
        settle = function("achievements/service.py", "settle")
        calls = call_named(settle, "mission_toolkit.settle_combat")
        self.assertEqual(len(calls), 1)
        (call,) = calls
        kwargs = call_keywords(call)
        self.assertEqual(kwargs["fight_id"], "event['fight_id']")
        self.assertEqual(kwargs["breeds"], "event['original_breeds']")
        fresh_guard = enclosing(settle, call, ast.If)
        self.assertEqual(ast.unparse(fresh_guard.test), "fresh")
        transaction = enclosing(settle, call, ast.With)
        self.assertEqual(
            ast.unparse(transaction.items[0].context_expr.func), "db.transaction"
        )

        (dungeon_call,) = [
            candidate
            for candidate in call_named(settle, "mission_toolkit.settle")
            if call_keywords(candidate).get("kind") == "'dungeon_completed'"
        ]
        dungeon = call_keywords(dungeon_call)
        self.assertEqual(dungeon["reference"], "event['completed_dungeon_id']")
        self.assertEqual(dungeon["token"], "f\"fight:{event['fight_id']}\"")
        self.assertEqual(
            ast.unparse(enclosing(settle, dungeon_call, ast.If).test),
            "event['completed_dungeon_id'] is not None",
        )
        self.assertTrue(source_has(fresh_guard, "mission_toolkit.settle("))
        self.assertIs(enclosing(settle, dungeon_call, ast.With), transaction)

        event = function("achievements/service.py", "_event")
        query = ast.unparse(event)
        self.assertIn("dungeon_room_encounters", query)
        self.assertIn("e.status='victory'", query)
        self.assertIn("e.result->>'completed'='true'", query)
        self.assertIn("dungeon_instance_members", query)
        self.assertNotIn("client", query.lower())

    def test_conversation_turnin_settles_only_after_payment_progress_and_reward_drain(
        self,
    ):
        turnin = function("achievements/conversation_turnin.py", "settle")
        (call,) = call_named(turnin, "mission_toolkit.settle")
        kwargs = call_keywords(call)
        self.assertEqual(kwargs["kind"], "'item_delivery'")
        self.assertEqual(kwargs["reference"], "requirement.reference")
        self.assertEqual(kwargs["quantity"], "requirement.quantity")
        self.assertEqual(kwargs["token"], "event_key")
        code = ast.unparse(turnin)
        positions = [
            code.index("_payment("),
            code.index("storage.record_event("),
            code.index("storage.store(db, character['id'], after)"),
            code.index("drain_rewards(db, store, character)"),
            code.index("mission_toolkit.settle("),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("if not objectives", code[: positions[-1]])
        self.assertIsNotNone(enclosing(turnin, call, ast.FunctionDef))

    def test_character_creation_and_map_transition_emit_map_enter_after_identity_commit(
        self,
    ):
        create = function("storage/store.py", "create_character", "Store")
        (call,) = call_named(create, "mission_toolkit.settle")
        kwargs = call_keywords(call)
        self.assertEqual(kwargs["kind"], "'map_enter'")
        self.assertEqual(kwargs["reference"], "created['map_id']")
        self.assertEqual(kwargs["token"], "f'character-created:{character_id}'")
        self.assertIsNotNone(enclosing(create, call, ast.With))
        self.assertLess(
            ast.unparse(create).index("created = self.character"),
            ast.unparse(create).index("mission_toolkit.settle"),
        )

        transition = function("maps/mission_transport.py", "transition")
        (call,) = call_named(transition, "mission_toolkit.settle")
        kwargs = call_keywords(call)
        self.assertEqual(kwargs["kind"], "'map_enter'")
        self.assertEqual(kwargs["reference"], "saved['map_id']")
        self.assertTrue(
            source_has(enclosing(transition, call, ast.If), "source['map_id']")
        )
        self.assertIsNotNone(enclosing(transition, call, ast.With))
        self.assertGreater(
            ast.unparse(transition).index("mission_toolkit.settle"),
            ast.unparse(transition).index("if (source['map_id']"),
        )

    def test_generic_dialogue_hook_is_plain_fallback_with_rollback_and_post_commit_publish(
        self,
    ):
        choose = function(
            "application/session_objectives.py",
            "choose_toolkit_dialogue",
            "ObjectivesSessionMixin",
        )
        (settle,) = call_named(choose, "mission_toolkit.settle")
        kwargs = call_keywords(settle)
        self.assertEqual(kwargs["kind"], "'dialogue'")
        self.assertEqual(kwargs["reference"], "request['choice_id']")
        conditional = next(
            n
            for n in ast.walk(choose)
            if isinstance(n, ast.IfExp) and n.orelse is settle
        )
        self.assertEqual(ast.unparse(conditional.test), "packet is None")
        transaction = enclosing(choose, settle, ast.With)
        self.assertEqual(
            ast.unparse(transaction.items[0].context_expr),
            "self.runtime.STORE.connection()",
        )
        source = ast.unparse(choose)
        self.assertLess(
            source.index("session.choose("), source.index("mission_toolkit.settle")
        )
        self.assertLess(
            source.index("except BaseException"),
            source.index("self.publish_settled_quest_packets(packets)"),
        )
        self.assertIn(
            "session.node_id, session.speaker_id, session.authorize_speaker", source
        )

    def test_actual_dialogue_toolkit_choice_rolls_back_session_and_publishes_only_after_commit(
        self,
    ):
        events = []
        statements = []

        class Db:
            def execute(self, sql, args):
                statements.append((sql, args))

        @contextmanager
        def transaction():
            events.append("begin")
            try:
                yield Db()
            except BaseException:
                events.append("rollback")
                raise
            else:
                events.append("commit")

        session = object.__new__(Session)
        dialogue = SimpleNamespace(
            node_id=4,
            speaker_id=9,
            authorize_speaker=True,
            previous_choice_id=3,
        )

        def choose(node_id, choice_id):
            events.append("choose")
            dialogue.node_id = node_id
            dialogue.previous_choice_id = choice_id
            return (13411, b"dialogue")

        dialogue.choose = choose
        store = SimpleNamespace(
            connection=transaction,
            lock_character=lambda *_args, **_kwargs: events.append("lease"),
        )
        session.runtime = SimpleNamespace(
            POSITIONS=SimpleNamespace(account_barrier=lambda *_: nullcontext()),
            flush_positions=lambda **_: None,
            STORE=store,
        )
        session.state = SimpleNamespace(
            npc_dialogue_session=dialogue,
            account_id=8,
            generation="lease",
            character={"id": 77, "account_id": 8},
            position={},
        )
        session.publish_settled_quest_packets = Mock(
            side_effect=lambda packets: events.append("publish")
        )
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle",
            side_effect=lambda *_args, **_kwargs: events.append("settle")
            or [(13371, b"journal")],
        ):
            packet = session.choose_toolkit_dialogue({"node_id": 12, "choice_id": 34})
        self.assertEqual(packet, (13411, b"dialogue"))
        self.assertEqual(
            events, ["begin", "lease", "choose", "settle", "commit", "publish"]
        )
        self.assertIn("SELECT id FROM accounts", statements[0][0])

        previous = (
            dialogue.node_id,
            dialogue.speaker_id,
            dialogue.authorize_speaker,
            dialogue.previous_choice_id,
        )
        session.publish_settled_quest_packets.reset_mock()
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle",
            side_effect=RuntimeError("settlement failed"),
        ), self.assertRaisesRegex(RuntimeError, "settlement failed"):
            session.choose_toolkit_dialogue({"node_id": 99, "choice_id": 100})
        self.assertEqual(
            (
                dialogue.node_id,
                dialogue.speaker_id,
                dialogue.authorize_speaker,
                dialogue.previous_choice_id,
            ),
            previous,
        )
        session.publish_settled_quest_packets.assert_not_called()
        self.assertEqual(events[-4:], ["begin", "lease", "choose", "rollback"])


if __name__ == "__main__":
    unittest.main()
