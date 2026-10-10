"""Pure policy boundary tests; actual PvP acceptance is tested separately."""
from copy import deepcopy
from dataclasses import asdict
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_periodic_aptitude import (
    remember_periodic_aptitude,
    renew_periodic_aptitudes,
)


class PeriodicAptitudeTests(unittest.TestCase):
    def setUp(self):
        self.container = dict(
            present=True,
            type=36,
            id=(17 << 16) + 2,
            is_spell=False,
            native_kind="aptitude",
            level=2,
        )
        self.invocation = EffectInvocation(136452, 2, 7, 7, (0, 0, 0))
        self.state = dict(aptitudes=[(17, 2, 165201, self.container["id"])])
        self.fight = SimpleNamespace(
            current=SimpleNamespace(id=7),
            phase="active",
            turn_id=1,
            actors={7: SimpleNamespace(position=(1, 0, 0))},
            native_class_initializations={7: self.state},
            native_owned_group_effects={},
        )
        self.row = dict(
            invocation=asdict(self.invocation),
            native_retained_container=deepcopy(self.container),
            timer=dict(actor_id=7, expiration_round=2, phase="start"),
        )
        self.effect = dict(
            native_timing_definition=dict(
                ryE=1, ryF=0.0, clock_on_target=True, clock_on_caster=False
            )
        )
        self.definition = dict(
            subscription=True,
            event_execution_count=0,
            event_execution_count_per_level=1.0,
        )
        self.source = patch(
            "wakfu_server.combat_periodic_aptitude._source_effects",
            return_value={
                "165201": {"children": [136452]},
                "136452": {"children": []},
            },
        )
        self.source.start()
        self.addCleanup(self.source.stop)
        self.executed = []
        self.dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=self.fight),
            effects={"165201": {"criteria": ""}},
            condition_context=lambda invocation: None,
            execute=lambda invocation: self.executed.append(invocation) or True,
        )

    def remember(self):
        remember_periodic_aptitude(self.fight, self.row, self.effect, self.definition)

    def test_exhausted_listener_reconstructs_once_at_owned_start(self):
        self.remember()
        self.assertEqual(renew_periodic_aptitudes(self.dispatcher, actor_id=7), (True,))
        self.assertEqual(renew_periodic_aptitudes(self.dispatcher, actor_id=7), ())
        self.assertEqual(len(self.executed), 1)
        self.assertEqual(self.executed[0].level, 2)
        self.assertEqual(self.executed[0].cell, (1, 0, 0))
        self.assertEqual(self.executed[0].native_retained_container, self.container)

    def test_live_listener_budget_is_not_reset_or_duplicated(self):
        self.remember()
        self.fight.native_owned_group_effects[9] = dict(self.row, execution_count=1)
        self.assertEqual(renew_periodic_aptitudes(self.dispatcher, actor_id=7), ())
        self.assertEqual(self.fight.native_owned_group_effects[9]["execution_count"], 1)
        self.assertFalse(self.executed)

    def test_original_root_criterion_remains_authoritative(self):
        self.remember()
        self.dispatcher.effects["165201"]["criteria"] = "False"
        self.assertEqual(renew_periodic_aptitudes(self.dispatcher, actor_id=7), ())
        self.assertFalse(self.executed)

    def test_foreign_source_or_turn_rejected(self):
        self.remember()
        with self.assertRaises(ValueError):
            renew_periodic_aptitudes(self.dispatcher, actor_id=8)
        self.state["aptitude_periodic_recipes"]["136452"]["container"]["id"] += 1
        with self.assertRaises(ValueError):
            renew_periodic_aptitudes(self.dispatcher, actor_id=7)
        self.assertFalse(self.executed)

    def test_unlimited_or_non_unit_clock_has_no_renewal_recipe(self):
        self.definition["event_execution_count"] = -1
        self.remember()
        self.assertNotIn("aptitude_periodic_recipes", self.state)
        self.definition["event_execution_count"] = 0
        self.effect["native_timing_definition"]["ryE"] = 2
        self.remember()
        self.assertNotIn("aptitude_periodic_recipes", self.state)

    def test_recipe_and_duplicate_boundary_survive_primitive_checkpoint_roundtrip(self):
        self.remember()
        renew_periodic_aptitudes(self.dispatcher, actor_id=7)
        self.fight.native_class_initializations[7] = json.loads(json.dumps(self.state))
        self.assertEqual(renew_periodic_aptitudes(self.dispatcher, actor_id=7), ())
        self.fight.turn_id = 2
        self.assertEqual(renew_periodic_aptitudes(self.dispatcher, actor_id=7), (True,))
        self.assertEqual(len(self.executed), 2)
