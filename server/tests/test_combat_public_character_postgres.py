"""Fresh minimal public-character reads used by external fight markers."""
import ast
import unittest
import uuid
from unittest.mock import call, patch

from postgres_case import PostgresCase
from wakfu_server.combat.combat_actor import actual_actor_stats, actor_effects
from wakfu_server.combat.combat_multiplayer_wire import added
from wakfu_server.combat.combat_public_fighter_stats import public_player_fighter_stats
from wakfu_server.combat.combat_state import Actor, Fight


def _public_member_packet(store):
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1].joinpath("local_game_server.py").read_text()
    )
    module = ast.parse(source)
    owner = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_publish_external_marker_locked"
    )
    function = next(
        node
        for node in ast.walk(owner)
        if isinstance(node, ast.FunctionDef) and node.name == "public_member_packet"
    )
    namespace = {"STORE": store}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            "local_game_server.py",
            "exec",
        ),
        namespace,
    )
    return namespace["public_member_packet"]


class CombatPublicCharacterPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "pub" + uuid.uuid4().hex[:10], "test-password"
        )["id"]
        self.other_account = self.store.register(
            "pub" + uuid.uuid4().hex[:10], "test-password"
        )["id"]
        self.character = self.store.create_character(self.account, "PubMarker", breed=8)
        self.character_id = self.character["id"]
        from wakfu_server.health import maximum
        from wakfu_server.characters.progression import level_xp

        max_hp = maximum(8, 12)
        self.xp = level_xp(12) + 1234
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,level=12,max_hp=%s,hp=%s,x=18,y=-23,z=2 WHERE id=%s",
                (max_hp, max_hp, self.character_id),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (self.xp, self.character_id),
            )
            db.execute(
                "UPDATE account_wallets SET kamas=7654321 WHERE account_id=%s",
                (self.account,),
            )

    def test_minimal_read_is_fresh_and_contains_only_public_identity_and_progression(
        self,
    ):
        current = self.store.combat_public_character(self.account, self.character_id)
        self.assertEqual(
            {"id", "account_id", "level", "breed", "map_id", "xp"}, set(current)
        )
        self.assertEqual(
            (self.character_id, self.account, 12, 8, 1134, self.xp),
            tuple(
                current[key]
                for key in ("id", "account_id", "level", "breed", "map_id", "xp")
            ),
        )

    def test_foreign_and_deleted_characters_are_not_publicly_readable(self):
        with self.assertRaisesRegex(ValueError, "Personaje no encontrado"):
            self.store.combat_public_character(self.other_account, self.character_id)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET deleted_at=now() WHERE id=%s",
                (self.character_id,),
            )
        with self.assertRaisesRegex(ValueError, "Personaje no encontrado"):
            self.store.combat_public_character(self.account, self.character_id)

    def test_missing_progression_or_wallet_fails_closed(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_progression WHERE character_id=%s",
                (self.character_id,),
            )
        with self.assertRaisesRegex(
            ValueError, "Missing character progression or account wallet"
        ):
            self.store.combat_public_character(self.account, self.character_id)

        replacement = self.store.create_character(self.account, "PubWallet", breed=8)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_wallets WHERE account_id=%s", (self.account,)
            )
        with self.assertRaisesRegex(
            ValueError, "Missing character progression or account wallet"
        ):
            self.store.combat_public_character(self.account, replacement["id"])

    def _fight(self):
        from wakfu_server.breed_resources import base_resources
        from wakfu_server.combat.combat_actor_snapshot import build_player_snapshot

        character = self.store.character(self.account, self.character_id)
        resources = base_resources(character)
        actor = Actor(
            id=self.character_id,
            team=0,
            position=(18, -23, 2),
            hp=character["hp"],
            max_hp=character["max_hp"],
            ap=resources["AP"],
            mp=resources["MP"],
            initiative=37,
            effective_level=character["level"],
            owner_id=self.account,
            controlled=True,
        )
        enemy = Actor(
            id=-90,
            team=1,
            position=(20, -23, 2),
            hp=40,
            max_hp=40,
            ap=3,
            mp=3,
            initiative=1,
            effective_level=1,
        )
        fight = Fight(
            321,
            [actor, enemy],
            {(18, -23, 2), (20, -23, 2)},
            {0: {(18, -23, 2)}, 1: {(20, -23, 2)}},
        )
        snapshot = build_player_snapshot(
            character,
            actor,
            wp_current=resources["WP"],
            wp_maximum=resources["WP"],
            running_effects=(),
        )
        snapshot.install(actor)
        from wakfu_server.combat.combat_hp_raw import set_hp_raw_current

        set_hp_raw_current(actor, max(1, character["hp"] - 11))
        actor.position = (19, -22, 2)
        return character, actor, fight

    def test_full_and_narrow_sources_serialize_identical_live_member_bytes(self):
        from wakfu_server.breed_resources import live_wp

        _character, actor, fight = self._fight()
        full = self.store.character(self.account, actor.id)
        narrow = self.store.combat_public_character(self.account, actor.id)
        wp_current, wp_maximum = live_wp(fight, actor.id)
        full_stats = actual_actor_stats(
            full,
            actor,
            fight.id,
            wp_current=wp_current,
            wp_maximum=wp_maximum,
            fight=fight,
        )
        narrow_stats = actual_actor_stats(
            narrow,
            actor,
            fight.id,
            wp_current=wp_current,
            wp_maximum=wp_maximum,
            fight=fight,
        )
        self.assertEqual(full_stats, narrow_stats)
        expected = added(
            fight.id,
            actor.id,
            actor_type=0,
            team=actor.team,
            stats=public_player_fighter_stats(
                full_stats, actor_id=actor.id, fight_id=fight.id
            ),
            effects=actor_effects(),
        )
        self.assertEqual(
            expected,
            added(
                fight.id,
                actor.id,
                actor_type=0,
                team=actor.team,
                stats=public_player_fighter_stats(
                    narrow_stats, actor_id=actor.id, fight_id=fight.id
                ),
                effects=actor_effects(),
            ),
        )
        with patch.object(
            self.store, "character", wraps=self.store.character
        ) as full_read, patch.object(
            self.store,
            "combat_public_character",
            wraps=self.store.combat_public_character,
        ) as narrow_read:
            self.assertEqual(expected, _public_member_packet(self.store)(actor, fight))
        full_read.assert_not_called()
        self.assertEqual(2, narrow_read.call_count)
        self.assertEqual(call(self.account, actor.id), narrow_read.call_args_list[0])

    def test_marker_legacy_fallback_uses_full_hydration_and_keeps_missing_wp_fail_closed(
        self,
    ):
        _character, actor, fight = self._fight()
        actor.effect_stats = None
        with patch.object(
            self.store, "character", wraps=self.store.character
        ) as full_read, patch.object(
            self.store,
            "combat_public_character",
            wraps=self.store.combat_public_character,
        ) as narrow_read:
            with self.assertRaisesRegex(
                ValueError, "Missing authoritative combat WP snapshot"
            ):
                _public_member_packet(self.store)(actor, fight)
        self.assertGreater(full_read.call_count, 0)
        self.assertEqual(call(self.account, actor.id), full_read.call_args_list[0])
        narrow_read.assert_not_called()
