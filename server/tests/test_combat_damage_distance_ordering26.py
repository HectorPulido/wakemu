"""Original flag26 ordering reaches eXt without changing damage consumption."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_combat_damage_handler as fixture_module
from wakfu_server.combat_target_ordering import order_native_targets
from wakfu_server.combat_damage_events import damage_event_ids
from wakfu_server.fight_checkpoint_store import snapshot

SOURCE = json.loads(
    (Path(__file__).with_name("fixtures") / "native-damage-ordering26.json").read_text()
)
METADATA = SOURCE["ordering"]
LOOKUP = "wakfu_server.combat_target_ordering.native_target_ordering"


class DamageDistanceOrdering26Tests(unittest.TestCase):
    def fixture(self, reference, *, ordered=True):
        fixture = fixture_module.DamageHandlerTests()
        fixture.setUp()
        effect = deepcopy(SOURCE["records"]["effects"][str(reference)])
        if not ordered:
            effect["native_effect_flags"].remove(26)
        invocation = replace(fixture.invocation, reference=reference, level=73)
        events = []

        class Lifecycle:
            def phase(self, effect, invocation, **data):
                events.append(
                    (
                        data["channel"],
                        data["value"],
                        damage_event_ids(
                            effect,
                            container_type=11,
                            phase=data["channel"],
                            blocked=False,
                            localization="FRONT",
                            context_is_native_fight=True,
                        ),
                    )
                )

        fixture.handler.event_lifecycle = Lifecycle()
        return fixture, effect, invocation, events

    def execute(self, reference, ordered):
        fixture, effect, invocation, events = self.fixture(reference, ordered=ordered)
        with patch(LOOKUP, return_value=METADATA):
            self.assertTrue(fixture.handler(effect, {}, invocation))
        return snapshot(fixture.fight), fixture.packets, events

    def test_exact_original_damage_sources_preserve_absorption_events_and_wire(self):
        for reference in map(int, METADATA):
            with self.subTest(reference=reference):
                self.assertEqual(
                    self.execute(reference, True), self.execute(reference, False)
                )

    def test_farthest_first_uses_effect_target_cell_and_stable_equal_distance(self):
        fixture, effect, invocation, _ = self.fixture(271865)
        invocation = replace(invocation, cell=(10, 10, 0))
        actors = [
            SimpleNamespace(id=1, position=(11, 10, 0)),
            SimpleNamespace(id=2, position=(15, 10, 0)),
            SimpleNamespace(id=3, position=(10, 15, 0)),
        ]
        with patch(LOOKUP, return_value=METADATA):
            ordered = order_native_targets(effect, invocation, actors)
        self.assertEqual([a.id for a in ordered], [2, 3, 1])
        self.assertEqual(METADATA["271865"]["maximum_targets"], -1)

    def test_missing_or_changed_native_identity_rejects_before_damage_mutation(self):
        variants = [{}, deepcopy(METADATA), deepcopy(METADATA)]
        variants[1]["271865"]["effect_class"] = 1
        variants[2]["271865"]["native_effect_flags"] = [26]
        for metadata in variants:
            fixture, effect, invocation, events = self.fixture(271865)
            before = snapshot(fixture.fight)
            with patch(LOOKUP, return_value=metadata), self.assertRaisesRegex(
                ValueError, "target ordering identity"
            ):
                fixture.handler(effect, {}, invocation)
            self.assertEqual(snapshot(fixture.fight), before)
            self.assertEqual((fixture.packets, events), ([], []))

    def test_ordering_authority_does_not_authorize_an_unknown_damage_flag(self):
        fixture, effect, invocation, events = self.fixture(271865)
        effect["native_effect_flags"].append(123)
        metadata = deepcopy(METADATA)
        metadata["271865"]["native_effect_flags"].append(123)
        before = snapshot(fixture.fight)
        with patch(LOOKUP, return_value=metadata), self.assertRaisesRegex(
            ValueError, "Unsupported native damage flags.*123"
        ):
            fixture.handler(effect, {}, invocation)
        self.assertEqual(snapshot(fixture.fight), before)
        self.assertEqual((fixture.packets, events), ([], []))


if __name__ == "__main__":
    unittest.main()
