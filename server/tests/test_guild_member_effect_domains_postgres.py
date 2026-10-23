"""Guild contributions survive food clearing and reach actual profession rewards."""
from datetime import datetime, timezone
import struct
import unittest
from unittest.mock import patch

import test_guild_progression_postgres as _fixture


class GuildMemberEffectDomainTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture.GuildProgressionPostgresTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.store = self.fixture.store

    def test_member_hp_foodclear_and_original_profession_effect_share_real_domains(
        self,
    ):
        from psycopg.types.json import Jsonb
        from wakfu_server.characters import guild_progression
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.inventory_items import grant
        from wakfu_server.inventory_consumable_effects import use
        from wakfu_server.consumable_world_lifecycle import clear_for_test
        from wakfu_server.profession_store import award

        owner = self.fixture.owner
        account, generation, identity = (
            owner["account"],
            owner["generation"],
            owner["character"],
        )
        original = self.store.character(account, identity)
        baseline = effective_character(original)["max_hp"]
        from wakfu_server.characters.health_store import sync

        sync(
            self.store,
            account,
            generation,
            identity,
            original["hp"],
            original["hp"] - 20,
        )
        pending = self.fixture._bonus(1, key="member-domain-hp")
        now = datetime.fromtimestamp(
            (pending["bonus"]["learned_at_ms"] + 1) / 1000, timezone.utc
        )
        with patch.object(self.store, "now", return_value=now):
            with patch(
                "wakfu_server.characters.guild_economy._save",
                side_effect=ValueError("failed settlement"),
            ):
                with self.assertRaisesRegex(ValueError, "failed settlement"):
                    guild_progression.tick(self.store)
            self.assertEqual(
                self.store.character(account, identity)["guild_member_effects"], ()
            )
            self.assertTrue(guild_progression.tick(self.store))
            self.assertEqual(guild_progression.tick(self.store), ())
            learned = self.store.character(account, identity)
            for food_flag in (False, True):
                self.assertEqual(
                    effective_character(learned, include_consumable_buffs=food_flag)[
                        "max_hp"
                    ],
                    baseline + 5,
                )
            self.assertEqual(effective_character(learned)["hp"], baseline + 5 - 20)
            from wakfu_server.health_store import initialize

            learned = initialize(
                self.store, account, generation, identity, exploration=True
            )
            with self.store.connection() as db:
                db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (account,))
            source = grant(
                self.store,
                account,
                generation,
                identity,
                reference=10376,
                quantity=1,
                container=learned["inventory_containers"][0]["uid"],
                slot=20,
                allowed_references={10376},
            )
            used = use(
                self.store,
                account,
                generation,
                identity,
                struct.pack(">qB", source["uid"], 0),
                expected_hp=learned["hp"],
                in_fight=False,
            )
            self.assertEqual(
                effective_character(used["character"], include_consumable_buffs=True)[
                    "max_hp"
                ],
                baseline + 25,
            )
            cleared = clear_for_test(self.store, account, generation, used["character"])
            self.assertEqual(
                effective_character(cleared, include_consumable_buffs=True)["max_hp"],
                baseline + 5,
            )
            with self.store.connection() as db:
                db.execute(
                    "UPDATE guilds SET level=10,current_points=100000 WHERE id=%s",
                    (self.fixture.guild_id,),
                )
                db.execute(
                    "INSERT INTO account_professions(account_id,profession_id) VALUES(%s,64)",
                    (account,),
                )
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='profession_xp'",
                    (Jsonb({"multiplier_basis_points": 10000}),),
                )
            pending = self.fixture._bonus(70, key="member-domain-profession")
            later = datetime.fromtimestamp(
                (pending["bonus"]["learned_at_ms"] + 1) / 1000, timezone.utc
            )
            with patch.object(self.store, "now", return_value=later):
                guild_progression.tick(self.store)
                with self.store.connection() as db:
                    first = award(
                        self.store,
                        db,
                        account,
                        generation,
                        identity,
                        64,
                        base_xp=100,
                        operation="guild-domain-craft",
                        action_category="recipe",
                    )
                    repeated = award(
                        self.store,
                        db,
                        account,
                        generation,
                        identity,
                        64,
                        base_xp=100,
                        operation="guild-domain-craft",
                        action_category="recipe",
                    )
                self.assertEqual(first["xp"], 105)
                self.assertFalse(repeated["applied"])
