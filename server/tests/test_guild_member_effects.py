"""Native guild member leaves share scalar/resource and profession arithmetic."""
import unittest

from wakfu_server.characters import guild_member_effects as member
from wakfu_server.characters.guild_progression import catalog


class GuildMemberEffectTests(unittest.TestCase):
    def _character(self, identities, *, now=1_000_000, activation=100):
        character = dict(guild_native=dict(guildId=9))
        records = {
            str(identity): dict(active=True, activated_at_ms=activation)
            for identity in identities
        }
        return member.load_from_records(character, records, now)

    def test_all_native_leaves_have_typed_projection_without_fake_food_states(self):
        natives = [
            row for row in catalog()["bonuses"] if row["effect_type"] == "MEMBER_EFFECT"
        ]
        self.assertEqual(len(natives), 49)
        self.assertEqual(
            sum(member.qualified_descriptor(row) is not None for row in natives), 47
        )
        character = self._character([row["id"] for row in natives])
        self.assertNotIn("consumable_states", character)
        self.assertEqual(member.bonuses(character)["unsupported"], [])
        self.assertEqual(len(character["guild_member_effects"]), 49)

    def test_self_hp_scalar_and_profession_effects_keep_separate_typed_paths(self):
        character = self._character([1, 3, 70, 71])
        projected = member.bonuses(character)
        self.assertEqual(projected["stats"], {1: 5, 7: 5})
        self.assertEqual(projected["stat_operations"], ((1, 5, False), (7, 5, False)))
        profession = member.profession_bonuses(character, 64)
        self.assertEqual(profession["craft_xp"], 10)
        self.assertEqual(
            sum(value for key, value in profession.items() if key != "craft_xp"), 0
        )

    def test_activation_expiry_membership_and_native_beta_condition(self):
        records = {
            "1": dict(active=False, activated_at_ms=100),
            "72": dict(active=True, activated_at_ms=100),
        }
        character = dict(guild_native=dict(guildId=9))
        self.assertEqual(len(member.projection(character, records, 21_600_099)), 1)
        self.assertEqual(member.projection(character, records, 21_600_100), ())
        self.assertEqual(member.projection(character, records, 99), ())
        self.assertEqual(member.projection({}, records, 101), ())
        from wakfu_server.combat_system_conditions import fresh_system_configuration

        configuration = fresh_system_configuration()
        configuration["overrides"]["beta.mode"] = True
        self.assertEqual(
            member.projection(
                character, records, 101, system_configuration=configuration
            ),
            (),
        )
