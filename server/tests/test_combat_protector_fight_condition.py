"""Exact native eOK registry, constructor and checkpoint authority tests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_protector_fight_condition import (
    capture_published_registry,
    capture_world_registry,
    protector_in_fight,
    selector,
    query_fight_condition,
)
from wakfu_server import npc_protectors, protector_ecosystem


def record(actor=-1706442046308330, protector=424):
    import struct

    return struct.pack(">iBiiiBiq", protector, 1, 0, 0, 93601, 1, 22193, actor) + bytes(
        11
    )


class ProtectorFightConditionTests(unittest.TestCase):
    def test_exact_published_actor_join_includes_enemy_dead_and_offplay(self):
        registry = capture_published_registry([record()], 1385, 0)
        caster = SimpleNamespace(id=7, hp=50, team=0)
        protector = SimpleNamespace(
            id=-1706442046308330, hp=0, team=1, is_in_play=False
        )
        fighters = {caster.id: caster, protector.id: protector}
        constructors = {caster.id: "biB", protector.id: "bje"}
        self.assertTrue(
            protector_in_fight(caster, fighters, registry, lambda a: constructors[a.id])
        )
        # The same species or protector reference on a different physical actor
        # cannot manufacture the native bLO.cXS()/eGj.Sn association.
        other = SimpleNamespace(id=-8, ref=5459, hp=50, team=1)
        self.assertFalse(
            protector_in_fight(
                caster,
                {7: caster, -8: other},
                registry,
                lambda a: "biB" if a.id == 7 else "bje",
            )
        )
        # Even an impossible registry entry with the PC ID cannot replace the
        # PC class's actual inherited null dsH implementation.
        pc_registry = capture_published_registry([record(7)], 1385, 0)
        self.assertFalse(
            protector_in_fight(caster, {7: caster}, pc_registry, lambda a: "biB")
        )

    def test_world_bridge_reuses_existing_publication_authority(self):
        db = object()
        character = dict(id=7, map_id=1385, instance_id=0)
        with patch.object(
            npc_protectors, "bootstrap_records", return_value=(record(),)
        ) as publisher, patch.object(
            protector_ecosystem, "bootstrap_records", return_value=(record(),)
        ) as enriched:
            registry = capture_world_registry(db, character)
        publisher.assert_called_once_with(db, character)
        enriched.assert_called_once_with(db, 1385, (record(),), instance_id=0)
        self.assertEqual(registry.associations, ((-1706442046308330, 424),))
        self.assertEqual(registry.map_id, 1385)
        with patch.object(
            npc_protectors,
            "bootstrap_records",
            side_effect=ValueError("invalid capture"),
        ):
            with self.assertRaisesRegex(ValueError, "invalid capture"):
                capture_world_registry(db, character)

    def test_native_nulls_selectors_and_unknown_authority(self):
        self.assertFalse(protector_in_fight(None, None, None, None))
        self.assertFalse(protector_in_fight(SimpleNamespace(id=7), None, None, None))
        self.assertEqual(selector([]), "caster")
        self.assertEqual(selector(["TaRgEt"]), "target")
        self.assertEqual(selector(["anythingElse"]), "caster")
        with self.assertRaises(ValueError):
            selector([True])
        registry = capture_published_registry([], 1385, 0)
        actor = SimpleNamespace(id=7)
        with self.assertRaisesRegex(ValueError, "constructor"):
            protector_in_fight(actor, {7: actor}, registry, lambda a: "unproven")
        with self.assertRaisesRegex(ValueError, "roster"):
            protector_in_fight(actor, {}, registry, lambda a: "biB")
        with self.assertRaises(ValueError):
            capture_published_registry([record(), record()], 1385, 0)
        with self.assertRaises(ValueError):
            capture_published_registry([record()[:-1]], 1385, 0)

    def test_checkpoint_receipt_roundtrip_and_unproven_new_actor_rejection(self):
        import json

        caster = SimpleNamespace(id=7)
        protector = SimpleNamespace(id=-1706442046308330, hp=0, is_in_play=False)
        value = dict(
            schema_version=1,
            fight_id=9,
            map_id=1385,
            instance_id=0,
            associations=[[-1706442046308330, 424]],
            constructors=[[7, "biB"], [-1706442046308330, "bje"]],
        )
        fight = SimpleNamespace(
            id=9,
            actors={7: caster, protector.id: protector},
            native_protector_condition=json.loads(json.dumps(value)),
        )
        self.assertTrue(query_fight_condition(fight, caster))
        del fight.actors[protector.id]
        self.assertFalse(query_fight_condition(fight, caster))
        fight.actors[-8] = SimpleNamespace(id=-8)
        with self.assertRaisesRegex(ValueError, "constructor provenance"):
            query_fight_condition(fight, caster)
        fight.native_protector_condition["fight_id"] = 10
        with self.assertRaisesRegex(ValueError, "receipt"):
            query_fight_condition(fight, caster)

    def test_tax_only_protector_record_does_not_create_a_fighter_association(self):
        import struct

        tax_only = struct.pack(">iBiii", 425, 1, 30, 30, 93602) + bytes(11 + 1)
        registry = capture_published_registry((record(), tax_only), 1385, 0)
        self.assertEqual(registry.associations, ((-1706442046308330, 424),))


def authority(player):
    from wakfu_server.combat_runtime_adapter import NativeActorAuthority

    return NativeActorAuthority(
        targeting={"is_eGj": True},
        is_player=player,
        deck_spell_ids=frozenset(),
        excluded_deck_spell_ids=frozenset(),
        is_carried=False,
        breed_id=0,
        summon_count=0,
        summon_counts_by_breed={},
        occupant_blocks=True,
        native_actor_type=0 if player else 1,
        native_ai_control_baseline=not player,
        native_npc_prototype_ref=None if player else 5459,
    )


class OwnedProtectorConditionTests(unittest.TestCase):
    def fight(self):
        from wakfu_server.combat_state import Actor, Fight

        pc = Actor(7, 0, (0, 0, 0), 50, 6, 3, 10, 10)
        npc = Actor(-1706442046308330, 1, (1, 0, 0), 50, 6, 3, 5, 10)
        fight = Fight(
            9, (pc, npc), {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.native_protector_registry = dict(
            schema_version=1,
            fight_id=9,
            map_id=1385,
            instance_id=0,
            associations=[[npc.id, 424]],
        )
        return fight

    def test_native_source_criterion_and_captured_constructor_roundtrip(self):
        import json
        from wakfu_server.combat_protector_fight_condition import query_owned_fight
        from wakfu_server.combat_conditions import ConditionContext, evaluate_condition
        from wakfu_server.fight_checkpoint_store import snapshot

        fight = self.fight()
        rows = {identity: authority(identity == 7) for identity in fight.actors}

        def query(_selector):
            return query_owned_fight(
                fight, fight.actors[7], lambda actor: rows[actor.id]
            )

        context = ConditionContext(actors={}, is_protector_in_fight_query=query)
        # Both native 9728/10632 graphs share state686 child36731 with this
        # exact expression. No source reference enters the runtime predicate.
        self.assertTrue(evaluate_condition("IsProtectorInFight()", context))
        state = json.loads(json.dumps(snapshot(fight)))
        restored = self.fight()
        restored.native_protector_registry = state["native_protector_registry"]
        self.assertTrue(
            query_owned_fight(restored, restored.actors[7], lambda a: rows[a.id])
        )
        restored.native_protector_registry["associations"] = []
        self.assertFalse(
            query_owned_fight(restored, restored.actors[7], lambda a: rows[a.id])
        )
        restored.actors[-8] = SimpleNamespace(id=-8)
        with self.assertRaises((KeyError, ValueError)):
            query_owned_fight(restored, restored.actors[7], lambda a: rows[a.id])
        delattr(fight, "native_protector_registry")
        with self.assertRaises(ValueError):
            query_owned_fight(fight, fight.actors[7], lambda a: rows[a.id])

    def test_typed_capability_requires_actual_callback_receipt_and_all_constructors(
        self,
    ):
        from wakfu_server.combat_protector_fight_condition import (
            bind_condition_capability,
            protector_condition_capability,
        )
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter

        # Static admission only inspects these production-owned objects. No
        # factory handlers or cast policy run during preflight.
        adapter = object.__new__(NativeServerRuntimeAdapter)
        adapter._actor = lambda fight, actor: authority(actor.id == 7)
        factory = object.__new__(NativeEffectRuntimeFactory)
        factory.contexts = SimpleNamespace(condition=adapter.condition)
        fight = self.fight()
        with patch(
            "wakfu_server.combat_protector_fight_condition.protector_in_fight",
            side_effect=AssertionError("preflight must not execute eOK"),
        ):
            self.assertIsNotNone(bind_condition_capability(factory, fight))
            self.assertIs(protector_condition_capability(factory), True)
        factory.contexts.condition = lambda *args: True
        self.assertIsNone(protector_condition_capability(factory))
        self.assertIsNone(bind_condition_capability(factory, fight))
        factory.contexts.condition = adapter.condition
        fight.native_protector_registry["fight_id"] = 10
        self.assertIsNone(bind_condition_capability(factory, fight))
        fight.native_protector_registry["fight_id"] = 9
        adapter._actor = lambda fight, actor: None
        self.assertIsNone(bind_condition_capability(factory, fight))

    def test_no_receipt_does_not_block_unrelated_condition_validation(self):
        from wakfu_server.combat_conditions import (
            ConditionContext,
            evaluate_condition,
            UnknownCondition,
        )

        self.assertTrue(evaluate_condition("True", ConditionContext(actors={})))
        evaluate_condition(
            "IsProtectorInFight('target')",
            ConditionContext(actors={}),
            validate_only=True,
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsProtectorInFight()", ConditionContext(actors={}))

    def test_actual_runtime_adapter_reads_registry_and_null_target_semantics(self):
        from dataclasses import replace
        from test_combat_runtime_adapter import ServerAdapterTests
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        ServerAdapterTests.setUpClass()
        fixture = ServerAdapterTests()
        fixture.setUp()
        original = fixture.adapter.actor_authority

        def owned(preview, actor):
            return replace(
                original(preview, actor),
                native_actor_type=0 if actor.id == 7 else 1,
                native_ai_control_baseline=actor.id != 7,
                native_npc_prototype_ref=None if actor.id == 7 else 5459,
            )

        fixture.adapter.actor_authority = owned
        preview = fixture.preview
        preview.native_protector_registry = dict(
            schema_version=1,
            fight_id=preview.id,
            map_id=1385,
            instance_id=0,
            associations=[[-7, 424]],
        )
        invocation = EffectInvocation(36731, 1, 7, -7, preview.actors[-7].position)
        context = fixture.adapter.condition(preview, {}, None, invocation)
        self.assertTrue(evaluate_condition("IsProtectorInFight()", context))
        self.assertTrue(evaluate_condition("IsProtectorInFight('target')", context))
        preview.native_protector_registry["associations"] = []
        self.assertFalse(evaluate_condition("IsProtectorInFight()", context))
        delattr(preview, "native_protector_registry")
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsProtectorInFight()", context)
        null_context = fixture.adapter.condition(
            preview, {}, None, replace(invocation, target_id=None)
        )
        self.assertFalse(
            evaluate_condition("IsProtectorInFight('target')", null_context)
        )
