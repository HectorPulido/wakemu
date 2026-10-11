"""Native BOMB_EFFECT31 preserves eXt damage and original source metadata."""
import unittest

import test_combat_damage_handler as damage_fixture
from wakfu_server.combat_damage_events import damage_event_ids
from wakfu_server.fight_checkpoint_store import snapshot


class BombDamageFlagTests(unittest.TestCase):
    def execute(self, family, flags):
        fixture = damage_fixture.DamageHandlerTests()
        fixture.setUp()
        effect = dict(
            fixture.effect,
            effect_class=family,
            native_effect_flags=list(flags),
            target_masks=[None] * 7,
        )
        phases = []

        class Events:
            def phase(_, source, invocation, **data):
                phases.append(
                    (
                        data["channel"],
                        data["value"],
                        tuple(source["native_effect_flags"]),
                    )
                )

        fixture.handler.event_lifecycle = Events()
        fixture.handler(effect, {}, fixture.invocation)
        events = [
            damage_event_ids(
                effect,
                container_type=11,
                phase=phase,
                blocked=False,
                localization="FRONT",
                context_is_native_fight=True,
            )
            for phase in (1, 2, 3, 4)
        ]
        return snapshot(fixture.fight), tuple(fixture.packets), phases, events, effect

    def test_bomb_tag_preserves_damage_absorption_events_and_wire(self):
        for family in (1, 2, 3, 4, 5):
            with self.subTest(element_family=family):
                plain = self.execute(family, ())
                bomb = self.execute(family, (31,))
                self.assertEqual(bomb[:2], plain[:2])
                self.assertEqual(bomb[3], plain[3])
                self.assertEqual(
                    [(p, v) for p, v, _ in bomb[2]], [(p, v) for p, v, _ in plain[2]]
                )
                self.assertTrue(bomb[2])
                self.assertTrue(all(flags == (31,) for _, _, flags in bomb[2]))
                self.assertEqual(bomb[4]["native_effect_flags"], [31])

    def test_known_bomb_tag_does_not_authorize_unknown_flags(self):
        fixture = damage_fixture.DamageHandlerTests()
        fixture.setUp()
        before = snapshot(fixture.fight)
        effect = dict(fixture.effect, native_effect_flags=[31, 123])
        with self.assertRaisesRegex(
            ValueError, "Unsupported native damage flags:.*123"
        ):
            fixture.handler(effect, {}, fixture.invocation)
        self.assertEqual(snapshot(fixture.fight), before)
        self.assertEqual(fixture.packets, [])
