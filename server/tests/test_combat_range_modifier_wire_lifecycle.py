"""Pure lifecycle regression for category range modifiers and actor wire state."""
import unittest
import struct
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_casting_range import resolve_range
from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_spell_cost_effect import NativeSpellCostHandler
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_snapshot_wire import snapshot_characteristics


class RangeModifierWireLifecycleTests(unittest.TestCase):
    def test_removal_changes_next_cast_range_and_clears_retained_payload(self):
        values = {1: 20, 2: 6, 3: 3, 4: 6, 11: 0, 35: 10}
        minima = {key: 0 for key in values}
        minima.update({11: -(1 << 31), 35: -(1 << 31)})
        maxima = {key: value for key, value in values.items()}
        maxima.update({11: (1 << 31) - 1, 35: (1 << 31) - 1})
        actor = SimpleNamespace(
            id=7,
            hp=20,
            max_hp=20,
            ap=6,
            max_ap=6,
            mp=3,
            max_mp=3,
            initiative=10,
            effect_stats=values,
            effect_minima=minima,
            effect_base_minima=minima.copy(),
            effect_maxima=maxima,
            effect_percentages={key: 0 for key in values},
            effect_base_maxima=maxima.copy(),
            spell_ap_cost_modifiers={},
            spell_range_modifiers={},
        )

        def wire_range():
            definitions = {
                str(key): dict(hard_minimum=minima[key], hard_maximum=maxima[key])
                for key in values
            }
            with patch(
                "wakfu_server.combat_snapshot_wire.native_actor_catalog",
                return_value=dict(characteristics=definitions),
            ):
                payload = snapshot_characteristics(actor)
            count = struct.unpack_from(">H", payload)[0]
            rows = [
                struct.unpack_from(">Biiii", payload, 2 + index * 17)
                for index in range(count)
            ]
            return next(row[1] for row in rows if row[0] == 11)

        fight = SimpleNamespace(
            id=8,
            phase="active",
            actors={7: actor},
            owned_stat_effects={},
        )
        packets = []
        range_rule = dict(minimum=2, maximum=6, categories=(8,), range_modifiable=True)
        condition_context = ConditionContext(
            {
                "caster": ConditionActor(
                    characteristics={"RANGE": 0},
                    is_carried=False,
                    fight_properties=frozenset(),
                )
            }
        )
        effect = dict(effect_class=1066, parameters=[2.0, 0.0, 8.0, 0.0])
        invocation = EffectInvocation(123, 1, 7, 7, (0, 0, 0))
        handler = NativeSpellCostHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 901,
            context=lambda *_: StatExecutionContext(
                True, True, None, True, b"\x08\x00"
            ),
        )

        self.assertTrue(handler(effect, [], invocation))
        self.assertEqual(actor.spell_range_modifiers, {8: 2})
        self.assertEqual(
            resolve_range(range_rule, actor, condition_context)["maximum"], 8
        )
        self.assertEqual(wire_range(), 0)
        self.assertEqual(actor.ap, 6)

        remover = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        )
        remover.remove(901)

        # The next cast reads the current eHl mapping; a removed owned payload
        # cannot keep applying its former category bonus.
        self.assertEqual(actor.spell_range_modifiers, {8: 0})
        self.assertEqual(
            resolve_range(range_rule, actor, condition_context)["maximum"], 6
        )
        self.assertEqual(wire_range(), 0)
        self.assertEqual(actor.ap, 6)
        self.assertEqual([opcode for opcode, _ in packets], [13497, 13560])
        self.assertEqual(fight.owned_stat_effects, {})


if __name__ == "__main__":
    unittest.main()
