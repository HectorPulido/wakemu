"""Real934 transition and live PC/NPC serializers in the private successor."""
import ast
from pathlib import Path
import unittest
import test_combat_forced_retirement as retirement_fixture
import test_combat_actor as actor_fixture
from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats


class RetirementWireIntegrationTests(unittest.TestCase):
    def fixture(self):
        factory = retirement_fixture.ForcedRetirementTests()
        fight, pc, npc, _, retention, _, _ = factory.fixture()
        actor = pc if self.kind == "pc" else npc
        factory.retire(fight, actor, retention)
        # This wire test uses the supported explicit scalar-resource snapshot
        # branch. Characteristics mutation algorithms are tested separately.
        actor.effect_stats = None
        actor.native_controlled_by_ai = not actor.controlled
        character = actor_fixture.CombatActorTests().character()
        monster = dict(
            id=npc.id,
            ref=2534,
            level=100,
            map_id=1134,
            hp=npc.hp,
            max_hp=npc.max_hp,
            ap=npc.ap,
            max_ap=npc.max_ap,
            mp=npc.mp,
            max_mp=npc.max_mp,
            wp=0,
            max_wp=0,
            initiative=npc.initiative,
            team=npc.team,
            x=npc.position[0],
            y=npc.position[1],
            z=npc.position[2],
        )
        return fight, actor, character, monster

    def serialize(self, current, actor, character, monster, **extra):
        if actor.controlled:
            return actual_actor_stats(
                character, actor, current.id, wp_current=0, wp_maximum=0, **extra
            )
        return actual_monster_actor_stats(
            monster, actor, current.id, wp_current=0, wp_maximum=0, **extra
        )

    def test_actual_retired_pc_and_npc_publish_absent_signed_byte(self):
        for self.kind, offset in [("pc", 37), ("npc", 29)]:
            with self.subTest(kind=self.kind):
                fight, actor, character, monster = self.fixture()
                payload = self.serialize(fight, actor, character, monster, fight=fight)
                self.assertEqual(payload[offset], 255)
                self.assertGreater(actor.hp, 0)
                with self.assertRaisesRegex(ValueError, "Invalid native obstacle byte"):
                    self.serialize(fight, actor, character, monster)

    def test_pc_and_npc_reject_crossfight_and_copied_actor_context(self):
        from copy import copy

        for self.kind in ["pc", "npc"]:
            with self.subTest(kind=self.kind):
                fight, actor, character, monster = self.fixture()
                other = copy(fight)
                other.id += 1
                with self.assertRaisesRegex(
                    ValueError, "Mismatched actual retirement serialization context"
                ):
                    self.serialize(fight, actor, character, monster, fight=other)
                with self.assertRaisesRegex(
                    ValueError, "Mismatched actual retirement serialization context"
                ):
                    self.serialize(fight, copy(actor), character, monster, fight=fight)

    def test_unretired_minus_one_pc_and_npc_are_rejected(self):
        for self.kind in ["pc", "npc"]:
            with self.subTest(kind=self.kind):
                fight, actor, character, monster = self.fixture()
                fight.native_forced_retirements = {}
                del actor.native_forced_retirement
                with self.assertRaisesRegex(ValueError, "Invalid native obstacle byte"):
                    self.serialize(fight, actor, character, monster, fight=fight)

    def test_commit_callback_source_passes_actual_detached_state(self):
        root = Path(__file__).resolve().parents[2]
        expected = [
            ("server/tools/validate_monster_spell_activation.py", "serialize", "state"),
            (
                "server/wakfu_server/combat/combat_session_adapter.py",
                "stats_serializer",
                "current",
            ),
            (
                "server/wakfu_server/combat/combat_session_adapter.py",
                "actor_payload",
                "fight",
            ),
        ]
        for relative, name, context in expected:
            tree = ast.parse((root / relative).read_text())
            functions = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name
            ]
            self.assertEqual(len(functions), 1)
            calls = [
                node
                for node in ast.walk(functions[0])
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("actual_actor_stats", "actual_monster_actor_stats")
            ]
            self.assertEqual(len(calls), 2)
            for call in calls:
                keyword = next(value for value in call.keywords if value.arg == "fight")
                self.assertEqual(
                    ast.dump(keyword.value),
                    ast.dump(ast.Name(id=context, ctx=ast.Load())),
                )

    def test_original_commit_serialize_callback_executes_real_pc_and_npc_wire(self):
        import sys
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        # Execute the actual nested production callback AST; only its surrounding
        # closure is supplied. Live serializers and snapshot validation stay real.
        root = Path(__file__).resolve().parents[2]
        tree = ast.parse(
            (root / "server/tools/validate_monster_spell_activation.py").read_text()
        )
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "serialize"
        )
        for self.kind in ["pc", "npc"]:
            with self.subTest(kind=self.kind):
                fight, actor, character, monster = self.fixture()
                actor.effect_stats = {
                    1: actor.hp,
                    2: actor.ap,
                    3: actor.mp,
                    4: 0,
                    35: actor.initiative,
                }
                actor.effect_maxima = {
                    1: actor.max_hp,
                    2: actor.max_ap,
                    3: actor.max_mp,
                    4: 0,
                    35: 2147483647,
                }
                actor.effect_minima = {key: 0 for key in actor.effect_stats}
                actor.effect_percentages = {key: 0 for key in actor.effect_stats}
                actor.effect_base_maxima = dict(actor.effect_maxima)
                actor.effect_base_minima = dict(actor.effect_minima)
                environment = dict(
                    character=character,
                    monsters={monster["id"]: monster},
                    actual_actor_stats=actual_actor_stats,
                    actual_monster_actor_stats=actual_monster_actor_stats,
                )
                exec(
                    compile(
                        ast.Module(body=[function], type_ignores=[]),
                        "<actual production serialize callback>",
                        "exec",
                    ),
                    environment,
                )
                payload = environment["serialize"](actor, fight)
                self.assertEqual(payload[37 if actor.controlled else 29], 255)
