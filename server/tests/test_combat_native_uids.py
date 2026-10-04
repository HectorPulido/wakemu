import unittest
from wakfu_server.combat_effects import direct_damage
from wakfu_server.combat_healing_effect import direct_healing
from wakfu_server.combat_stat_effects import owned_effect_payload
from wakfu_server.combat_state_carrier import state_carrier_payload
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_effect_dispatch import EffectInvocation


class NativeUIDTests(unittest.TestCase):
    def test_native_fresh_damage_heal_stat_and_carrier_use_own_base_uid(self):
        payloads = [
            direct_damage(
                77,
                1,
                uid=901,
                generic_effect=123,
                element=1,
                caster_id=7,
                target_id=-7,
                damage=3,
            )[19:],
            direct_healing(
                77,
                1,
                uid=901,
                generic_effect=123,
                effect_class=25,
                caster_id=7,
                target_id=-7,
                restored=3,
            )[19:],
            owned_effect_payload(
                uid=901,
                base_uid=None,
                generic_effect=123,
                caster_id=7,
                target_id=-7,
                value=3,
            ),
            state_carrier_payload(
                uid=901,
                base_uid=None,
                caster_id=7,
                target_id=-7,
                state_id=3442,
                level=1,
                native_turn_clock=-1,
                native_realtime_remaining=0,
            ),
        ]
        for payload in payloads:
            fields = _identity_fields(payload)
            self.assertEqual((fields[1], fields[2]), (901, 901))

    def test_clone_base_uid_and_state_ownership_are_distinct_contracts(self):
        clone = EffectInvocation(123, 1, 7, -7, (0, 0, 0), base_uid=800, state_uid=700)
        fields = _identity_fields(
            owned_effect_payload(
                uid=901,
                base_uid=clone.base_uid,
                generic_effect=123,
                caster_id=7,
                target_id=-7,
                value=3,
            )
        )
        self.assertEqual((fields[1], fields[2]), (901, 800))
        self.assertEqual(clone.state_uid, 700)
        fresh_child = EffectInvocation(123, 1, 7, -7, (0, 0, 0), state_uid=700)
        fields = _identity_fields(
            owned_effect_payload(
                uid=902,
                base_uid=fresh_child.base_uid,
                generic_effect=123,
                caster_id=7,
                target_id=-7,
                value=3,
            )
        )
        self.assertEqual((fields[1], fields[2]), (902, 902))
        self.assertEqual(fresh_child.state_uid, 700)


if __name__ == "__main__":
    unittest.main()
