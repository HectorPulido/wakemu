"""Strict native eXw death provenance without catalog or engine startup."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat_ordinary_death import registered_ordinary_death as registered


class Native830DeathTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(id=-201, hp=0)
        cause = dict(
            kind="hp_minimum_update",
            effect_class=830,
            uid=51,
            source_id=-200,
            target_id=-201,
            hp_before=300,
            hp=0,
            minimum=0,
            sequence=100,
        )
        death = dict(kind="death", actor_id=-201, sequence=101)
        fight = SimpleNamespace(
            actors={-201: actor, -200: object()}, events=[cause, death]
        )
        return fight, actor

    def test_native830_adjacent_owned_transition_registers_corpse(self):
        fight, actor = self.fixture()
        self.assertTrue(registered(fight, actor))

    def test_malformed_or_unowned_native830_transition_is_rejected(self):
        mutations = {
            "kind": "kill",
            "effect_class": 28,
            "uid": 0,
            "hp_before": 0,
            "hp": False,
            "minimum": False,
            "source_id": -999,
            "target_id": 7,
            "sequence": 99,
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                fight, actor = self.fixture()
                fight.events[0][key] = value
                with self.assertRaises(ValueError):
                    registered(fight, actor)

    def test_intervening_event_or_forged_actor_identity_is_rejected(self):
        fight, actor = self.fixture()
        fight.events.insert(1, dict(kind="cleanup", sequence=100))
        with self.assertRaises(ValueError):
            registered(fight, actor)
        fight, actor = self.fixture()
        with self.assertRaises(ValueError):
            registered(fight, SimpleNamespace(id=actor.id, hp=0))
