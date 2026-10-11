import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_hupper_resource_binding import (
    install,
    maximum_changed,
    set_current,
)
from wakfu_server.combat_maximum_resource import _write as maximum_write
from wakfu_server.combat_parameter_maximum import _write as parameter_write


class HupperResourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.row = {"hard_minimum": 0, "hard_maximum": 999}
        self.patches = [
            patch(
                "wakfu_server.combat_actor_snapshot.native_actor_catalog",
                return_value={"characteristics": {"111": self.row}},
            ),
            patch(
                "wakfu_server.combat_character_copy_metadata.native_copy_characteristics",
                return_value={
                    "fresh_characteristics": {"111": {"over_max_current": True}}
                },
            ),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def actor(self):
        return SimpleNamespace(
            effect_stats={4: 6, 111: 0},
            effect_maxima={4: 6, 111: 50},
            effect_base_maxima={4: 6, 111: 50},
            effect_base_minima={4: 0, 111: 0},
            effect_minima={4: 0, 111: 0},
            effect_percentages={4: 0, 111: 0},
            effect_frozen=frozenset(),
        )

    def test_constructor_zero_wp_and_wp_maximum_setters(self):
        actor = self.actor()
        install(actor)
        self.assertEqual(actor.effect_maxima[111], 500)
        maximum_write(actor, 4, 6, 8, 8)
        self.assertEqual(actor.effect_maxima[111], 650)
        parameter_write(actor, 4, 0, 0, 0)
        self.assertEqual(actor.effect_maxima[111], 50)

    def test_expandable_raw_survives_decrease_and_recovers_on_increase(self):
        actor = self.actor()
        install(actor)
        set_current(actor, 500)
        actor.effect_maxima[4] = 2
        maximum_changed(actor, 4)
        self.assertEqual(actor.effect_stats[111], 200)
        self.assertEqual(actor.native_hupper_resource_raw_current, 500)
        actor.effect_maxima[4] = 6
        maximum_changed(actor, 4)
        self.assertEqual(actor.effect_stats[111], 500)

    def test_frozen_current_and_native_hard_maximum(self):
        actor = self.actor()
        install(actor)
        set_current(actor, 500)
        actor.effect_frozen = frozenset({111})
        set_current(actor, 0)
        self.assertEqual(actor.effect_stats[111], 500)
        actor.effect_maxima[4] = 100
        maximum_changed(actor, 4)
        self.assertEqual(actor.effect_maxima[111], 999)
        self.assertEqual(actor.effect_stats[111], 500)

    def test_preview_changes_preserve_original_raw_and_maximum(self):
        original = self.actor()
        install(original)
        set_current(original, 500)
        preview = deepcopy(original)
        preview.effect_maxima[4] = 1
        maximum_changed(preview, 4)
        set_current(preview, 100)
        self.assertEqual(original.effect_stats[111], 500)
        self.assertEqual(original.effect_maxima[111], 500)
        self.assertEqual(original.native_hupper_resource_raw_current, 500)
