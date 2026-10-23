"""Owned native level facts survive pinning without substituting item levels."""
import json
from copy import deepcopy
from dataclasses import replace
import unittest

from wakfu_server.combat_equipment_dynamic_levels import (
    CompanionCustodyLevelFacts,
    OwnerLevelFacts,
    UnknownDynamicLevel,
    owner_child_levels,
    verify_source_level_facts,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_level_group import level_group_override

# Native eYm380193 operands, as exported from the complete equipment graph.
# Test data is not used by runtime admission or as an equipment qualifier.
FIXTURES = {
    "380193": dict(
        effect_class=999,
        parameter_count=10,
        native_effect_flags=[17],
        parameters=[
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            100.0,
            0.0,
            0.0,
            0.0,
            2.0,
            0.0,
        ],
        probability_base=100.0,
        probability_per_level=0.0,
    ),
    "64589": dict(effect_class=1020),
    "66439": dict(effect_class=430),
}


def fight_fixture():
    owner = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 42, owner_id=3, controlled=True)
    enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 30)
    fight = Fight(
        77,
        [owner, enemy],
        {owner.position, enemy.position},
        {0: {owner.position}, 1: {enemy.position}},
    )
    fight.ready(3)
    return fight


class OwnerLevelFactsTests(unittest.TestCase):
    def test_companion_custody_facts_qualify_real_999_graph_but_are_not_pin_authority(
        self,
    ):
        from types import SimpleNamespace
        from test_combat_equipment_operation_capability import (
            _effect,
            _runtime_binding,
            _provider,
        )
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.combat_equipment_operation_capability import validate_graph

        companion = dict(id=17, account_id=3, breed_ref=2828, xp=XP_BY_LEVEL[75])
        owner = dict(id=3, account_id=3, level=75)
        facts = CompanionCustodyLevelFacts.capture(companion, owner, 75)
        expected_level = owner_child_levels(FIXTURES["380193"], 75, facts).levels[0]
        group = _effect(999, FIXTURES["380193"]["parameters"])
        group["children"] = (2,)
        leaf = _effect(31, (2, 0, 1, 0, 0, 0))
        leaf["minimum_level"] = leaf["maximum_level"] = expected_level
        compiled = SimpleNamespace(
            effects={"1": group, "2": leaf},
            source_states={"states": {}, "effects": {}},
        )
        source = dict(
            roots=(1,),
            attachment_field=None,
            unplanned_passive_effect_ids=(),
            native_retained_container=dict(level=75),
        )
        bindings = {family: _runtime_binding(family) for family in (31, 330, 999)}
        result = validate_graph(
            source,
            compiled,
            {},
            runtime_bindings=bindings,
            criteria_capability=_provider,
            owner_level_facts=facts,
        )
        self.assertEqual("supported", result.status, result.reasons)
        self.assertEqual((expected_level,), result.parameters[0]["child_levels"])

        # Custody facts prove the preflight level formula only. They cannot be
        # serialized as a fight pin or passed off as an active owner actor.
        self.assertFalse(hasattr(facts, "plain"))
        self.assertFalse(hasattr(facts, "fight_id"))
        with self.assertRaises(ValueError):
            OwnerLevelFacts.from_plain(facts)
        with self.assertRaises(UnknownDynamicLevel):
            owner_child_levels(FIXTURES["380193"], 75, dict(facts.__dict__))
        with self.assertRaises(ValueError):
            CompanionCustodyLevelFacts.capture(dict(companion, account_id=4), owner, 75)
        with self.assertRaises(ValueError):
            CompanionCustodyLevelFacts.capture(companion, owner, 76)

    def test_real_owner_level_drives_native_child_and_survives_preview_copy(self):
        fight = fight_fixture()
        facts = OwnerLevelFacts.capture(fight, 7, 3)
        effect = FIXTURES["380193"]
        proof = owner_child_levels(effect, 10, facts)
        self.assertEqual(proof.levels, (level_group_override(effect, 10, 42),))
        self.assertNotEqual(proof.levels, (10,))
        restored = OwnerLevelFacts.from_plain(json.loads(json.dumps(facts.plain())))
        copied = deepcopy(fight)
        self.assertTrue(restored.verify(copied))
        self.assertEqual(owner_child_levels(effect, 10, restored), proof)
        copied.actors[7].effective_level += 1
        self.assertFalse(restored.verify(copied))

    def test_capture_uses_actual_ownership_and_cleanup_does_not_require_health(self):
        fight = fight_fixture()
        with self.assertRaises(UnknownDynamicLevel):
            OwnerLevelFacts.capture(fight, 7, 4)
        facts = OwnerLevelFacts.capture(fight, 7, 3)
        source = {"_generic_owner_level_facts": facts.plain()}
        self.assertTrue(
            verify_source_level_facts(source, fight, actor_id=7, owner_id=3)
        )
        self.assertFalse(verify_source_level_facts(source, fight, actor_id=8))
        self.assertFalse(verify_source_level_facts(source, fight, owner_id=4))
        fight.actors[7].hp = 0
        self.assertTrue(facts.verify(fight))
        with self.assertRaises(UnknownDynamicLevel):
            OwnerLevelFacts.capture(fight, 7, 3)
        del fight.actors[7]
        self.assertFalse(facts.verify(fight))
        self.assertTrue(facts.verify(fight, allow_missing=True))
        fight.id += 1
        self.assertFalse(facts.verify(fight, allow_missing=True))

    def test_target_dependent_or_unmapped_trigger_domains_stay_unknown(self):
        facts = OwnerLevelFacts.capture(fight_fixture(), 7, 3)
        effect = deepcopy(FIXTURES["380193"])
        effect["parameters"][12] = 0  # Native param6 selects target instead.
        with self.assertRaises(UnknownDynamicLevel):
            owner_child_levels(effect, 10, facts)
        effect = deepcopy(FIXTURES["380193"])
        effect["parameters"][10] = 1  # Native actor rebind precedes selection.
        with self.assertRaises(UnknownDynamicLevel):
            owner_child_levels(effect, 10, facts)
        for definition in (FIXTURES["64589"], FIXTURES["66439"]):
            with self.assertRaises(UnknownDynamicLevel):
                owner_child_levels(definition, 10, facts)
        with self.assertRaises(UnknownDynamicLevel):
            owner_child_levels(FIXTURES["380193"], 10, None)

    def test_graph_visits_derived_child_level_and_rejects_rebound_caster_facts(self):
        from types import SimpleNamespace
        from test_combat_equipment_operation_capability import (
            _effect,
            _runtime_binding,
            _provider,
        )
        from wakfu_server.combat_equipment_operation_capability import validate_graph

        facts = OwnerLevelFacts.capture(fight_fixture(), 7, 3)
        group = _effect(999, FIXTURES["380193"]["parameters"])
        group["children"] = (2,)
        leaf = _effect(31, (2, 0, 1, 0, 0, 0))
        # The real parser must visit84, not the equipment container's10.
        leaf["minimum_level"] = leaf["maximum_level"] = 84
        compiled = SimpleNamespace(
            effects={"1": group, "2": leaf}, source_states={"states": {}, "effects": {}}
        )
        source = dict(
            roots=(1,),
            attachment_field=None,
            unplanned_passive_effect_ids=(),
            native_retained_container=dict(level=10),
        )
        bindings = {family: _runtime_binding(family) for family in (31, 330, 999)}
        result = validate_graph(
            source,
            compiled,
            {},
            runtime_bindings=bindings,
            criteria_capability=_provider,
            owner_level_facts=facts,
        )
        self.assertEqual(result.status, "supported", result.reasons)
        self.assertIn("native_owned_actor_level", result.requires_context)
        self.assertEqual(result.parameters[0]["child_levels"], (84,))
        unknown = validate_graph(
            source,
            compiled,
            {},
            runtime_bindings=bindings,
            criteria_capability=_provider,
        )
        self.assertEqual(unknown.status, "unknown")
        parent = _effect(330, (0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0))
        parent["children"] = (1,)
        compiled.effects["3"] = parent
        source["roots"] = (3,)
        rebound = validate_graph(
            source,
            compiled,
            {},
            runtime_bindings=bindings,
            criteria_capability=_provider,
            owner_level_facts=facts,
        )
        self.assertEqual(rebound.status, "unknown", rebound.reasons)

    def test_facts_reject_untyped_or_incomplete_checkpoint_values(self):
        facts = OwnerLevelFacts.capture(fight_fixture(), 7, 3)
        for change in (
            {"effective_level": True},
            {"version": 2},
            {"actor_id": 0},
            {"effective_level": 32768},
            {"unknown": 1},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                OwnerLevelFacts.from_plain(dict(facts.plain(), **change))
        self.assertEqual(
            owner_child_levels(
                FIXTURES["380193"], 10, replace(facts, effective_level=32767)
            ).levels,
            (level_group_override(FIXTURES["380193"], 10, 32767),),
        )


if __name__ == "__main__":
    unittest.main()
