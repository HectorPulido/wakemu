"""Native difficulty bounds, owned selection and frozen reward authority."""
import unittest
import struct
from wakfu_server import dungeon_difficulty
from postgres_case import PostgresCase
import test_dungeon_progression as fixture_module


class DungeonDifficultyTests(unittest.TestCase):
    def test_native_update_body_is_exact_and_rejects_malformed_authority(self):
        body = struct.pack(">qiq", 7, 5, 123)
        self.assertEqual(
            dungeon_difficulty.decode_request(body),
            dict(character_id=7, stasis_level=5, instance_id=123),
        )
        for invalid in (
            body[:-1],
            body + b"x",
            struct.pack(">qiq", 7, 11, 123),
            struct.pack(">qiq", 0, 2, 123),
        ):
            with self.assertRaises(ValueError):
                dungeon_difficulty.decode_request(invalid)

    def test_native_competitive_ceiling_includes_at_level(self):
        for source, target in (
            (1, 20),
            (20, 20),
            (21, 35),
            (81, 95),
            (200, 200),
            (201, 215),
            (230, 230),
        ):
            self.assertEqual(dungeon_difficulty.ceiling_band(source), target)
        for invalid in (0, 231, True):
            with self.assertRaises(ValueError):
                dungeon_difficulty.ceiling_band(invalid)


class DungeonDifficultyPostgresTests(PostgresCase):
    install_context_policy = (
        fixture_module.DungeonProgressionPostgresTests.install_context_policy
    )
    player = fixture_module.DungeonProgressionPostgresTests.player
    party = fixture_module.DungeonProgressionPostgresTests.party
    create = fixture_module.DungeonProgressionPostgresTests.create
    make_fight = fixture_module.DungeonProgressionPostgresTests.make_fight

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        from types import SimpleNamespace
        from wakfu_server import dungeon_progression

        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        self.plan = fixture_module._Plan(
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            )
        )
        with self.store.connection() as db:
            dungeon_progression.initialize_run(
                db, self.instance_id, self.party_id, self.plan
            )
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=ANY(%s)",
                (self.instance_id, [m["character"]["id"] for m in self.members]),
            )

    def select(self, member=None, **options):
        member = self.members[0] if member is None else member
        return dungeon_difficulty.select(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            **options,
        )

    def test_selection_owned_leader_bounds_and_reconnection_persistence(self):
        with self.assertRaisesRegex(ValueError, "leader"):
            self.select(self.members[1], stasis_level=5, competitive=True)
        for invalid in (0, 11, True):
            with self.assertRaises(ValueError):
                self.select(stasis_level=invalid, competitive=False)
        selected = self.select(stasis_level=5, competitive=True)
        self.assertTrue(selected["competitive"])
        self.assertGreater(selected["competitive_max_level"], 0)
        same = self.select(stasis_level=5, competitive=True)
        self.assertEqual(selected["revision"], same["revision"])
        with self.reopen().connection() as db:
            self.assertEqual(
                dungeon_difficulty.selection(db, self.instance_id)["stasis_level"], 5
            )

    def test_actual_binding_freezes_stasis_and_competitive_at_level_entitlement(self):
        from wakfu_server import dungeon_progression

        selected = self.select(stasis_level=5, competitive=True)
        fight = self.make_fight(self.members[0])
        with self.store.connection() as db:
            dungeon_progression.bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                self.members[0]["character"]["id"],
                fight,
                player_team=0,
            )
            frozen = dungeon_difficulty.encounter_context(
                db, fight, effective_level=selected["competitive_max_level"]
            )
            self.assertEqual(
                frozen,
                dict(
                    in_dungeon=True,
                    in_infinite_waves=False,
                    stasis_level=5,
                    downscaled=True,
                    dungeon_drop_rate_bp=40000,
                ),
            )
            self.assertFalse(
                dungeon_difficulty.encounter_context(
                    db, fight, effective_level=selected["competitive_max_level"] + 1
                )["downscaled"]
            )
        with self.assertRaisesRegex(ValueError, "frozen"):
            self.select(stasis_level=10, competitive=False)

    def test_normal_mode_does_not_award_competitive_rows_for_numeric_reduction(self):
        from wakfu_server import dungeon_progression

        self.select(stasis_level=3, competitive=False)
        fight = self.make_fight(self.members[0])
        with self.store.connection() as db:
            dungeon_progression.bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                self.members[0]["character"]["id"],
                fight,
                player_team=0,
            )
            context = dungeon_difficulty.encounter_context(db, fight, effective_level=1)
            self.assertFalse(context["downscaled"])
            self.assertEqual(context["stasis_level"], 3)
            with self.assertRaises(Exception), db.transaction():
                db.execute(
                    "UPDATE dungeon_encounter_difficulties SET snapshot='{}'::jsonb WHERE fight_id=%s",
                    (fight,),
                )

    def test_request_instance_identity_is_checked_inside_owned_transaction(self):
        with self.assertRaisesRegex(ValueError, "another instance"):
            self.select(
                stasis_level=5,
                competitive=True,
                expected_instance_id=self.instance_id + 1,
            )
        selected = self.select(
            stasis_level=5, competitive=True, expected_instance_id=self.instance_id
        )
        self.assertEqual(selected["instance_id"], self.instance_id)

    def test_native_forced_competitive_cannot_be_disabled(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,ARRAY['definitions','90','forced_competitive'],'true'::jsonb) WHERE name='dungeon_difficulty_catalog'"
            )
        selected = self.select(stasis_level=4, competitive=False)
        self.assertTrue(selected["competitive"])
        self.assertEqual(selected["competitive_max_level"], 20)

    def test_actor_scaling_and_binding_reject_stale_selection_atomically(self):
        from wakfu_server import dungeon_progression

        self.select(stasis_level=4, competitive=True)
        with self.store.connection() as db:
            profile = dungeon_difficulty.encounter_scaling(db, self.instance_id)
        self.assertEqual(profile["hp_percent"], 210)
        self.assertEqual(profile["damage_percent"], 190)
        self.select(stasis_level=5, competitive=True)
        fight = self.make_fight(self.members[0])
        with self.assertRaisesRegex(
            ValueError, "revision changed"
        ), self.store.connection() as db:
            dungeon_progression.bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                self.members[0]["character"]["id"],
                fight,
                player_team=0,
                expected_selection_revision=profile["selection_revision"],
            )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_room_encounters WHERE fight_id=%s", (fight,)
                ).fetchone()
            )

    def test_native_reduction_between_encounters_preserves_past_reward_profile(self):
        from types import SimpleNamespace
        from wakfu_server import dungeon_progression

        selected = self.select(stasis_level=5, competitive=True)
        fight = self.make_fight(self.members[0])
        with self.store.connection() as db:
            dungeon_progression.bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                self.members[0]["character"]["id"],
                fight,
                player_team=0,
            )
        with self.assertRaisesRegex(ValueError, "active encounter"):
            self.select(stasis_level=3)
        with self.store.connection() as db:
            dungeon_progression.settle_encounter(
                db, SimpleNamespace(id=fight, phase="finished", winner=0)
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
            )
        reduced = self.select(stasis_level=3)
        self.assertGreater(reduced["revision"], selected["revision"])
        self.assertTrue(reduced["competitive"])
        for options in (dict(stasis_level=4), dict(stasis_level=2, competitive=False)):
            with self.assertRaisesRegex(ValueError, "frozen"):
                self.select(**options)
        future = self.make_fight(self.members[0])
        with self.store.connection() as db:
            dungeon_progression.bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                self.members[0]["character"]["id"],
                future,
                player_team=0,
                expected_selection_revision=reduced["revision"],
            )
            before = dungeon_difficulty.encounter_context(db, fight, effective_level=20)
            after = dungeon_difficulty.encounter_context(db, future, effective_level=20)
        self.assertEqual(before["stasis_level"], 5)
        self.assertEqual(before["dungeon_drop_rate_bp"], 40000)
        self.assertEqual(after["stasis_level"], 3)
        self.assertEqual(after["dungeon_drop_rate_bp"], 14000)

    def test_entry_configuration_commits_native_cap_with_new_run(self):
        with self.store.connection() as db:
            configured = dungeon_difficulty.configure_entry(
                db,
                self.instance_id,
                self.members[0]["character"]["id"],
                stasis_level=4,
                competitive=True,
            )
            self.assertEqual(configured["stasis_level"], 4)
            self.assertEqual(configured["competitive_max_level"], 20)
