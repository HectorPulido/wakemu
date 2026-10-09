"""Shared RANGE/category wire authority reaches the same casting calculation."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_casting_range import effective_range, int32, resolve_range
from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_snapshot_wire import snapshot_characteristics
from wakfu_server.combat_spell_cost_effect import NativeSpellCostHandler
from wakfu_server.combat_stat_handler import StatExecutionContext


class NativeCastingRangeWireParityTests(unittest.TestCase):
    def actor(self, bonus):
        values = {1: 20, 2: 6, 3: 3, 4: 6, 11: bonus, 35: 10}
        minima = {key: 0 for key in values}
        minima.update({11: -(1 << 31), 35: -(1 << 31)})
        maxima = {key: value for key, value in values.items()}
        maxima.update({11: (1 << 31) - 1, 35: (1 << 31) - 1})
        return SimpleNamespace(
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
            effect_base_maxima=maxima.copy(),
            effect_percentages={key: 0 for key in values},
            spell_ap_cost_modifiers={},
            spell_range_modifiers={},
        )

    def wire_range(self, actor):
        definitions = {
            str(key): dict(
                hard_minimum=actor.effect_minima[key],
                hard_maximum=actor.effect_maxima[key],
            )
            for key in actor.effect_stats
        }
        with patch(
            "wakfu_server.combat_snapshot_wire.native_actor_catalog",
            return_value=dict(characteristics=definitions),
        ):
            payload = snapshot_characteristics(actor)
        rows = [
            struct.unpack_from(">Biiii", payload, 2 + index * 17)
            for index in range(struct.unpack_from(">H", payload)[0])
        ]
        return next(row[1] for row in rows if row[0] == 11)

    def test_live_range_wire_matches_server_for_every_category(self):
        for category in range(1, 19):
            for bonus in (-2, 0, 3):
                with self.subTest(category=category, bonus=bonus):
                    actor = self.actor(bonus)
                    fight = SimpleNamespace(
                        id=8, phase="active", actors={7: actor}, owned_stat_effects={}
                    )
                    packets = []
                    handler = NativeSpellCostHandler(
                        fight,
                        packets,
                        action_id=1,
                        allocate_uid=lambda: 901,
                        context=lambda *args: StatExecutionContext(
                            True, True, None, False, b"\x08\x00"
                        ),
                    )
                    handler(
                        dict(
                            effect_class=1066,
                            parameters=[2.0, 0.0, float(category), 0.0],
                        ),
                        {},
                        EffectInvocation(123, 1, 7, 7, (0, 0, 0)),
                    )
                    messages = {}
                    fields = _identity_fields(packets[0][1][18:], messages=messages)
                    additional = _identity_fields(messages[8], integer_fields=(10,))
                    self.assertEqual(additional[10], category)
                    self.assertEqual(fields[4], 2)
                    client_range = self.wire_range(actor)
                    context = ConditionContext(
                        {
                            "caster": ConditionActor(
                                characteristics={"RANGE": actor.effect_stats[11]},
                                is_carried=False,
                                fight_properties=frozenset(),
                            )
                        }
                    )
                    rule = dict(
                        minimum=2,
                        maximum=6,
                        categories=(category,),
                        range_modifiable=True,
                    )
                    actual = resolve_range(rule, actor, context)
                    expected = effective_range(
                        2, int32(6 + fields[4]), True, client_range, False, False
                    )
                    self.assertEqual((actual["minimum"], actual["maximum"]), expected)

    def test_changed_live_range_is_serialized_without_replaying_equipment(self):
        actor = self.actor(1)
        self.assertEqual(self.wire_range(actor), 1)
        actor.effect_stats[11] = -3
        self.assertEqual(self.wire_range(actor), -3)

    def test_owned_player_actor_packet_preserves_live_range_with_native_metadata(self):
        from test_combat_actor_snapshot import ActorSnapshotTests
        from wakfu_server.combat_actor import actual_actor_stats
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_wire import actor_state, decode_actor_state

        character, actor = ActorSnapshotTests().player()
        character.update(account_id=1, map_id=1134, x=0, y=0, z=0)
        build_player_snapshot(
            character, actor, wp_current=6, wp_maximum=6, running_effects=()
        ).install(actor)
        for live_bonus in (actor.effect_stats[11], 3, -2, 0):
            with self.subTest(live_bonus=live_bonus):
                actor.effect_stats[11] = live_bonus
                payload = actual_actor_stats(
                    character, actor, 8, wp_current=6, wp_maximum=6
                )
                # Production format3: XP8 + position20 + fight10 after tag.
                count = struct.unpack_from(">H", payload, 39)[0]
                rows = [
                    struct.unpack_from(">Biiii", payload, 41 + index * 17)
                    for index in range(count)
                ]
                self.assertEqual(
                    next(row[1] for row in rows if row[0] == 11), live_bonus
                )
                envelope = actor_state(12873, 8, actor.id, payload)
                self.assertEqual(decode_actor_state(12873, envelope)["state"], payload)


if __name__ == "__main__":
    unittest.main()
