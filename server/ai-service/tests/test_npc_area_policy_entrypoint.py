"""SDK NPC entrypoint uses the same policy; player casting keeps its producer."""
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_ai.native.native_oracle import NativeOracle


class NpcAreaPolicyEntrypointTests(unittest.TestCase):
    def fixture(self, *, player=False):
        actor = SimpleNamespace(
            id=-200,
            hp=100,
            effective_level=4,
            effect_stats={4: 6},
            spell_ap_cost_modifiers={},
            owner_id=7,
        )
        fight = SimpleNamespace(phase="active", current=actor)
        runtime = SimpleNamespace(fight=fight, action_id=11)
        oracle = object.__new__(NativeOracle)
        oracle.characters = {-200: {"id": -200}} if player else {}
        oracle.decks = {-200: b""}
        oracle.monsters = {-200: {"id": -200, "ref": 2617}}
        oracle.owned_spells = Mock(return_value={2794: 4})
        oracle.descriptor = Mock(return_value={"id": -200, "ref": 2617})
        oracle._rng = Mock(return_value=random.Random(0))
        oracle.visible = Mock(return_value=True)
        factory = Mock()
        adapter = SimpleNamespace(cast_condition=Mock())
        oracle.factory = Mock(return_value=(factory, adapter))
        action = dict(
            type="cast", spellId=2794, level=4, target=[0, 0, 0], targetId=-200
        )
        return oracle, runtime, action, factory, adapter

    def test_npc_shared_policy_receives_actual_factory_and_activation(self):
        oracle, runtime, action, factory, adapter = self.fixture()
        context = object()
        rule = dict(costs=dict(ap=3, mp=0, wp=0), roots=[64489])
        plan = dict(target_id=-200)
        transaction = object()
        with patch(
            "wakfu_server.combat_npc_attack.npc_spell_catalog", return_value={}
        ), patch("wakfu_server.combat_npc_attack.npc_runtime_catalog"), patch(
            "wakfu_server.combat_npc_activation.imports_enabled", return_value=True
        ), patch(
            "wakfu_server.combat_npc_area_preflight.npc_cast_condition",
            return_value=context,
        ) as policy, patch(
            "wakfu_server.combat_native_spell_casting.definition", return_value=rule
        ), patch(
            "wakfu_server.combat_cast._validate_target", return_value=plan
        ), patch(
            "wakfu_server.combat_npc_spell.prepare_validated_npc_spell",
            return_value=transaction,
        ):
            self.assertIs(oracle.cast(runtime, action), transaction)
        policy.assert_called_once_with(
            adapter,
            runtime.fight,
            dict(actor_id=-200, spell_uid=2794, target=(0, 0, 0)),
            factory=factory,
            enabled=True,
        )
        adapter.cast_condition.assert_not_called()

    def test_player_branch_never_enters_npc_policy(self):
        oracle, runtime, action, _factory, adapter = self.fixture(player=True)
        transaction = SimpleNamespace(plan=dict(target_id=-200))
        with patch(
            "wakfu_server.combat_spell_grant.granted_spells", return_value={}
        ), patch(
            "wakfu_server.combat_spell_transaction.prepare_spell_transaction",
            return_value=transaction,
        ) as prepare, patch(
            "wakfu_server.combat_npc_area_preflight.npc_cast_condition"
        ) as policy:
            self.assertIs(oracle.cast(runtime, action), transaction)
            prepare.call_args.kwargs["conditional_context"](
                dict(actor_id=-200), runtime.fight
            )
        policy.assert_not_called()
        adapter.cast_condition.assert_called_once()

    def test_unowned_npc_action_is_rejected_before_policy(self):
        oracle, runtime, action, _factory, _adapter = self.fixture()
        action["spellId"] = 999
        with patch(
            "wakfu_server.combat_npc_area_preflight.npc_cast_condition"
        ) as policy:
            with self.assertRaisesRegex(ValueError, "does not own"):
                oracle.cast(runtime, action)
        policy.assert_not_called()
        oracle.factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
