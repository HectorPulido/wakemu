"""Frozen role/terminal composition; synthetic admission, real native934 primitive.

These tests qualify orchestration and ownership guards, not an original story
scene. The eleven source-recovery declarations remain deliberately unadmitted.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_encounter_actor_contract import (
    ActorRoleSpec,
    EncounterActorContract,
    actor_contract_admission_digest,
    bind_actor_role,
    freeze_actor_contract,
    validate_actor_bindings,
)
from wakfu_server.combat_encounter_actor_contract_terminal import (
    NativeSceneRetirementExecution,
    prepare_actor_terminal,
)


MODULE = "wakfu_server.combat_encounter_actor_contract_terminal"


class Intent(SimpleNamespace):
    def to_record(self):
        return dict(vars(self))


class EncounterActorContractTests(unittest.TestCase):
    def spec(self):
        return EncounterActorContract(
            policy="qualification.actor-contract-v1",
            version=1,
            authority="explicit synthetic component admission; no live activation",
            map_id=529,
            initial_references=(3143, 3975),
            catalog_revision="a" * 64,
            source_paths=("combat-state-definitions.json",),
            roles=(
                ActorRoleSpec(
                    "helper",
                    3143,
                    minimum_hp=1,
                    retire_on_success=True,
                    retirement_effect_reference=101,
                ),
                ActorRoleSpec("other", 3975),
            ),
            terminal_policies=("qualification.objective-v1",),
        )

    def freeze(self, fight, spec=None):
        from wakfu_server.combat_encounter_source_revision import (
            source_revision_matches,
        )

        # A separate placement-admission record binds the same future fightID;
        # the real lifecycle fixture below is already active when returned.
        admission = SimpleNamespace(id=fight.id, phase="placement")
        with patch(
            "wakfu_server.combat_encounter_source_revision.source_revision_matches",
            return_value=True,
        ) as guard:
            freeze_actor_contract(
                admission,
                spec or self.spec(),
                map_id=529,
                initial_references=(3975, 3143),
            )
        guard.assert_called_once()
        fight.native_encounter_actor_contract = (
            admission.native_encounter_actor_contract
        )

    def fixture(self):
        from test_combat_forced_retirement import ForcedRetirementTests

        fight, pc, target, other, _, _, _ = ForcedRetirementTests().fixture()
        target.effect_minima = {1: 1}
        target.effect_maxima = {1: target.max_hp}
        target.effect_frozen = frozenset()
        for actor in (target, other):
            actor.native_controlled_by_ai = True
        fight.native_npc_initialization_receipts = {
            actor.id: dict(
                ref=reference,
                descriptor_level=actor.effective_level,
                raw_triples=[],
                resolved_states=[],
                applications=[],
                initialized=True,
            )
            for actor, reference in ((target, 3143), (other, 3975))
        }
        self.freeze(fight)
        bind_actor_role(fight, "helper", target.id)
        bind_actor_role(fight, "other", other.id)
        record = fight.native_encounter_actor_contract
        intent = Intent(
            policy="qualification.objective-v1",
            fight_id=fight.id,
            map_id=529,
            result="success",
            scene_contract_policy=record["policy"],
            admission_digest=record["admission_digest"],
            catalog_revision="a" * 64,
        )
        return fight, pc, target, other, intent

    def executor(self, candidate, role, binding, intent):
        """Execute the existing native handler, including its actual13497 packet."""
        from random import Random
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_forced_retirement_handler import (
            NativeForcedRetirementHandler,
        )
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_stat_handler import (
            NativeStatHandler,
            StatExecutionContext,
        )

        packets = []
        retention = NativeRetainedRuntime(
            candidate,
            packets,
            plan={
                "native_retained_container": dict(
                    present=True, type=11, id=123, is_spell=True, protected=False
                )
            },
            state_catalog={},
            action_id=1,
            timing=None,
            metadata={},
        )
        context = lambda *args: StatExecutionContext(True, True, None, False, b"")
        retention.stat_handler = NativeStatHandler(
            candidate,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: 900,
            context=context,
            rng=Random(1).random,
        )
        handler = NativeForcedRetirementHandler(
            candidate,
            packets,
            action_id=1,
            allocate_uid=lambda: 900,
            context=context,
            retention=retention,
            rng=Random(1).random,
        )
        actor = candidate.actors[binding["actor_id"]]
        effect = dict(
            effect_class=934, parameters=[], target_masks=[[] for _ in range(7)]
        )
        invocation = EffectInvocation(
            role.retirement_effect_reference,
            1,
            7,
            actor.id,
            actor.position,
            native_context_hex=constructed_execution_context().payload().hex(),
        )
        self.assertTrue(handler(effect, {}, invocation))
        return NativeSceneRetirementExecution(
            actor.id, role.retirement_effect_reference, 900, tuple(packets)
        )

    def test_frozen_scope_digest_checkpoint_and_unknown_declarations(self):
        import json
        from wakfu_server.combat_encounter_actor_contract_inventory import (
            DECLARATIONS,
            require_actor_integration_admitted,
        )

        fight, _, _, _, _ = self.fixture()
        digest = actor_contract_admission_digest(fight)
        fight.native_encounter_actor_contract = json.loads(
            json.dumps(fight.native_encounter_actor_contract)
        )
        self.assertEqual(actor_contract_admission_digest(fight), digest)
        self.assertEqual(len(DECLARATIONS), 11)
        for reference, declaration in DECLARATIONS.items():
            self.assertFalse(declaration.admitted)
            with self.assertRaisesRegex(ValueError, "unresolved"):
                require_actor_integration_admitted(reference)
        fight.native_encounter_actor_contract["map_id"] += 1
        with self.assertRaises(ValueError):
            actor_contract_admission_digest(fight)

    def test_binding_preserves_original_identity_under_real_current_transfer(self):
        from wakfu_server.combat_controller_registry import transfer_native_controller
        from wakfu_server.combat_ai_control import set_native_ai_control

        fight, pc, target, _, _ = self.fixture()
        before = deepcopy(fight.native_encounter_actor_contract["bindings"])
        transfer_native_controller(fight, target.id, pc.id)
        set_native_ai_control(target, False)
        self.assertEqual(validate_actor_bindings(fight), before)
        self.assertFalse(target.controlled)
        self.assertIsNone(target.owner_id)
        target.owner_id = pc.owner_id
        with self.assertRaisesRegex(ValueError, "ownership"):
            validate_actor_bindings(fight)

    def test_wrong_birth_rebinding_missing_floor_and_unresolved_scope_reject(self):
        fight, _, target, other, _ = self.fixture()
        with self.assertRaises(ValueError):
            bind_actor_role(fight, "helper", other.id)
        fight.native_npc_initialization_receipts[target.id]["ref"] = 3144
        with self.assertRaises(ValueError):
            validate_actor_bindings(fight)
        with self.assertRaisesRegex(ValueError, "unresolved"):
            replace(self.spec(), unresolved=("original scene missing",)).validate()
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            replace(
                self.spec(),
                roles=(
                    ActorRoleSpec("a", 1, scene_parent_role="b"),
                    ActorRoleSpec("b", 2, scene_parent_role="a"),
                ),
            ).validate()

    def test_real_native_retirement_keeps_hp_floor_and_unrelated_actor_in_play(self):
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_snapshot_actor_visibility import (
            hidden_snapshot_actor_ids,
        )
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, _, target, other, intent = self.fixture()
        original = snapshot(fight)
        slot = target.native_obstacle_id
        with patch(MODULE + "._qualified_terminal_intent", side_effect=lambda f, i: i):
            plan = prepare_actor_terminal(
                fight, intent, retirement_executor=self.executor
            )
        candidate = plan.candidate
        self.assertEqual(snapshot(fight), original)
        retired = candidate.actors[target.id]
        self.assertEqual((retired.hp, retired.effect_minima[1]), (target.hp, 1))
        self.assertEqual(
            global_fighter_guards(candidate, target.id),
            dict(baF=False, baG=False, baK=True),
        )
        self.assertTrue(global_fighter_guards(candidate, other.id)["baF"])
        self.assertIsNone(current_registry(candidate).slots[slot])
        self.assertNotIn(target.id, candidate.order)
        self.assertIn(target.id, hidden_snapshot_actor_ids(candidate))
        self.assertEqual(plan.retired_actor_ids, (target.id,))
        self.assertTrue(any(opcode == 13497 for opcode, _ in plan.packets))
        saved = snapshot(candidate)
        self.assertEqual(saved["actors"][str(target.id)]["effect_minima"]["1"], 1)
        self.assertTrue(saved["native_encounter_actor_contract"]["terminal_receipts"])
        self.assertFalse(
            any(row["kind"] in ("damage", "death") for row in candidate.events)
        )
        with patch(MODULE + "._qualified_terminal_intent", side_effect=lambda f, i: i):
            duplicate = prepare_actor_terminal(
                candidate, intent, retirement_executor=self.executor
            )
        self.assertEqual(duplicate.packets, ())
        self.assertEqual(len(duplicate.candidate.native_forced_retirement_order), 1)

    def test_unearned_foreign_and_failed_native_executor_leave_source_intact(self):
        fight, _, _, _, intent = self.fixture()
        from wakfu_server.fight_checkpoint_store import snapshot

        before = snapshot(fight)
        with patch(
            MODULE + "._qualified_terminal_intent", side_effect=ValueError("unearned")
        ):
            with self.assertRaisesRegex(ValueError, "unearned"):
                prepare_actor_terminal(fight, intent, retirement_executor=self.executor)
        for field, value in (
            ("admission_digest", "b" * 64),
            ("map_id", 530),
            ("policy", "another-objective"),
        ):
            bad = Intent(**dict(vars(intent), **{field: value}))
            with patch(
                MODULE + "._qualified_terminal_intent", side_effect=lambda f, i: i
            ):
                with self.assertRaisesRegex(ValueError, "outside"):
                    prepare_actor_terminal(
                        fight, bad, retirement_executor=self.executor
                    )

        def fails(candidate, role, binding, receipt):
            self.executor(candidate, role, binding, receipt)
            raise ValueError("later native failure")

        with patch(MODULE + "._qualified_terminal_intent", side_effect=lambda f, i: i):
            with self.assertRaisesRegex(ValueError, "later native failure"):
                prepare_actor_terminal(fight, intent, retirement_executor=fails)
        self.assertEqual(snapshot(fight), before)


if __name__ == "__main__":
    unittest.main()
