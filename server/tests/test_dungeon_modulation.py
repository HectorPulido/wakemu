import unittest

from wakfu_server.characters import dungeon_modulation


class DungeonModulationContextTests(unittest.TestCase):
    class Database:
        def __init__(self, row):
            self.row = row
            self.calls = []

        def execute(self, query, values):
            self.calls.append((query, values))
            return self

        def fetchone(self):
            return self.row

    def test_context_reads_current_active_membership_without_selection_writes(self):
        db = self.Database(
            dict(instance_id=91, competitive=True, competitive_max_level=50, revision=4)
        )
        character = dict(id=3, instance_id=91, level=200)
        context = dungeon_modulation.load_context(db, character)
        self.assertEqual(
            context,
            dict(
                instance_id=91, competitive=True, maximum_level=50, selection_revision=4
            ),
        )
        query, values = db.calls[0]
        self.assertEqual(values, (91, 3))
        self.assertIn("i.status IN ('active','completed')", query)
        self.assertIn("m.status='active'", query)
        self.assertNotIn("FOR UPDATE", query)
        self.assertEqual(character, dict(id=3, instance_id=91, level=200))

    def test_no_context_outside_instance_or_after_membership_ends(self):
        db = self.Database(None)
        self.assertIsNone(
            dungeon_modulation.load_context(db, dict(id=3, instance_id=0))
        )
        self.assertEqual(db.calls, [])
        self.assertIsNone(
            dungeon_modulation.load_context(db, dict(id=3, instance_id=91))
        )
        missing = self.Database(
            dict(
                instance_id=91,
                competitive=None,
                competitive_max_level=None,
                revision=None,
            )
        )
        self.assertIsNone(
            dungeon_modulation.load_context(missing, dict(id=3, instance_id=91))
        )

    def test_missing_or_invalid_authority_fails_closed(self):
        base = dict(
            instance_id=91, competitive=True, competitive_max_level=50, revision=4
        )
        for change in (
            dict(competitive="true"),
            dict(competitive_max_level=49),
            dict(competitive_max_level=True),
            dict(revision=-1),
            dict(competitive=False),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                dungeon_modulation.load_context(
                    self.Database(dict(base, **change)), dict(id=3, instance_id=91)
                )

    def test_all_native_bands_bound_without_upscaling_or_replacing_owned_level(self):
        for cap in dungeon_modulation.NATIVE_BANDS:
            context = dict(competitive=True, maximum_level=cap)
            for level in (1, 49, 50, 51, 200):
                self.assertEqual(
                    dungeon_modulation.capped_level(level, context), min(level, cap)
                )
        self.assertEqual(dungeon_modulation.capped_level(51, None), 51)
        self.assertEqual(
            dungeon_modulation.capped_level(51, dict(competitive=False)), 51
        )


class DungeonAutomaticProfileTests(unittest.TestCase):
    def character(self):
        from wakfu_server.wire import proto_field
        from wakfu_server.spells import available_spells, encode_deck
        from wakfu_server.health import maximum
        from wakfu_server.progression import level_xp

        spells = available_spells(8, 200)
        deck = encode_deck(
            [row["id"] for row in spells if row["kind"] == "active"][:12],
            [row["id"] for row in spells if row["kind"] == "passive"][:6],
        )
        return dict(
            id=31,
            account_id=9,
            breed=8,
            level=200,
            effective_level=200,
            active_build_index=1,
            build_selection_revision=7,
            hp=maximum(8, 200) - 17,
            max_hp=maximum(8, 200),
            hp_damage=17,
            health_dead=False,
            x=0,
            y=0,
            z=0,
            direction=0,
            map_id=1134,
            instance_id=91,
            xp=level_xp(200),
            inventory_items=[],
            builds={
                1: dict(
                    sheet=b"".join(
                        proto_field(tag, value)
                        for tag, value in (
                            (8, 1),
                            (18, b"Original"),
                            (24, (1 << 64) - 1),
                            (56, 1),
                            (64, 0),
                        )
                    ).hex(),
                    equipment="",
                    deck=deck.hex(),
                    aptitudes="",
                )
            },
        )

    def projected(self, level=50):
        return dungeon_modulation.project(
            self.character(),
            dict(
                instance_id=91,
                competitive=True,
                maximum_level=level,
                selection_revision=3,
            ),
            dungeon_modulation.DEFAULT_POLICY,
        )

    def test_projection_preserves_owned_metadata_and_publishes_native_auto_sheet(self):
        import copy
        from wakfu_server import builds
        from wakfu_server.wire import proto_fields
        from wakfu_server.spells import validate_deck

        original = self.character()
        before = copy.deepcopy(original)
        context = dict(
            instance_id=91, competitive=True, maximum_level=50, selection_revision=3
        )
        projected = dungeon_modulation.project(
            original, context, dungeon_modulation.DEFAULT_POLICY
        )
        self.assertEqual(original, before)
        self.assertEqual(projected["builds"][1], before["builds"][1])
        self.assertEqual(
            (
                projected["level"],
                projected["effective_level"],
                projected["active_build_index"],
            ),
            (200, 50, 127),
        )
        self.assertEqual(projected["build_selection_revision"], 7)
        auto = projected["builds"][127]
        sheet = dict(proto_fields(bytes.fromhex(auto["sheet"])))
        self.assertEqual((sheet[24], sheet[56], sheet[64]), (50, 0, 1))
        self.assertEqual(
            list(proto_fields(bytes.fromhex(auto["equipment"]))), [(424, 50)]
        )
        self.assertEqual(
            list(proto_fields(bytes.fromhex(auto["aptitudes"]))), [(24, 50)]
        )
        decoded = validate_deck(bytes.fromhex(auto["deck"]), 8, 50)
        self.assertEqual(decoded["level_cap"], 50)
        self.assertTrue(any(spell == 0 for spell in decoded["active"][10:]))
        published = dict(proto_fields(builds.build_set(projected, b"")))
        self.assertEqual(published[8], 127)
        self.assertIn(127, builds.catalog_indices(projected))
        self.assertEqual(builds.effective_sheet_level(projected, 1), 200)

    def test_free_slot_does_not_replace_owned_high_index_and_projection_is_single_use(
        self,
    ):
        character = self.character()
        character["builds"][127] = dict(character["builds"][1])
        projected = dungeon_modulation.project(
            character,
            dict(
                instance_id=91, competitive=True, maximum_level=35, selection_revision=3
            ),
            dungeon_modulation.DEFAULT_POLICY,
        )
        self.assertEqual(projected["active_build_index"], 126)
        self.assertEqual(projected["builds"][127], character["builds"][127])
        with self.assertRaisesRegex(ValueError, "twice"):
            dungeon_modulation.project(
                projected,
                projected["dungeon_modulation"],
                dungeon_modulation.DEFAULT_POLICY,
            )

    def test_custom_policy_is_validated_and_resources_change_at_defined_thresholds(
        self,
    ):
        import copy

        policy = dungeon_modulation.DEFAULT_POLICY
        for level, ap, mp in (
            (20, 0, 0),
            (49, 0, 0),
            (50, 1, 0),
            (79, 1, 0),
            (80, 1, 1),
            (124, 1, 1),
            (125, 2, 1),
            (200, 2, 1),
        ):
            stats = dungeon_modulation.profile_stats(level, policy)
            self.assertEqual((stats[2], stats[3]), (ap, mp))
            self.assertEqual(
                (stats[1], stats[21], stats[28]), (10 * level, 4 * level, level // 2)
            )
        for change in (
            dict(version=True),
            dict(hp_per_level=-1),
            dict(resistance_divisor=0),
            dict(ap_thresholds=[50, 50]),
            dict(mp_thresholds=[True]),
            dict(extra=0),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                dungeon_modulation.validate_policy(
                    dict(copy.deepcopy(policy), **change)
                )
        self.assertEqual(
            dungeon_modulation.project(self.character(), None, policy), self.character()
        )

    def test_world_characteristics_and_actual_combat_snapshot_use_identical_profile(
        self,
    ):
        import struct
        from wakfu_server.equipment_stats import (
            effective_character,
            combat_resources,
            bonuses,
        )
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.wire import owned_public_characteristics

        character = effective_character(self.projected())
        resources = combat_resources(character)
        self.assertEqual(bonuses(character)["equipped_uids"], [])
        self.assertEqual(bonuses(character, build_index=1)["stats"], {})
        actor = Actor(
            31,
            0,
            (0, 0, 0),
            character["hp"],
            resources["ap"],
            resources["mp"],
            resources["initiative"],
            50,
            owner_id=9,
            controlled=True,
            max_hp=character["max_hp"],
        )
        snapshot = build_player_snapshot(
            character,
            actor,
            wp_current=resources["wp"],
            wp_maximum=resources["wp"],
            running_effects=(),
        )
        snapshot.install(actor)
        public = owned_public_characteristics(character)
        count = struct.unpack_from(">H", public)[0]
        rows = {
            row[0]: row
            for row in (
                struct.unpack_from(">Biiii", public, 2 + 17 * index)
                for index in range(count)
            )
        }
        for identity in (1, 2, 3, 9, 21, 22, 23, 24, 28, 29, 30, 31, 35):
            self.assertEqual(rows[identity][1], actor.effect_stats[identity])
        self.assertEqual(
            (actor.effective_level, actor.max_ap, actor.max_mp),
            (50, resources["ap"], resources["mp"]),
        )
        self.assertEqual(
            dungeon_modulation.effective_health_max(character), actor.max_hp
        )


from postgres_case import PostgresCase
import test_dungeon_progression as dungeon_fixture


class DungeonAutomaticProfilePostgresTests(PostgresCase):
    install_context_policy = (
        dungeon_fixture.DungeonProgressionPostgresTests.install_context_policy
    )
    player = dungeon_fixture.DungeonProgressionPostgresTests.player
    party = dungeon_fixture.DungeonProgressionPostgresTests.party
    create = dungeon_fixture.DungeonProgressionPostgresTests.create

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        from wakfu_server.wire import proto_field
        from wakfu_server.spells import default_deck
        from wakfu_server.health import maximum
        from wakfu_server.progression import level_xp

        self.original_builds = {}
        for member in self.members:
            identity = member["character"]["id"]
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET level=200,hp=%s,max_hp=%s,hp_damage=17 WHERE id=%s",
                    (
                        maximum(member["character"]["breed"], 200) - 17,
                        maximum(member["character"]["breed"], 200),
                        identity,
                    ),
                )
                db.execute(
                    "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                    (level_xp(200), identity),
                )
            owned = self.store.character(member["account"], identity)
            blobs = dict(
                sheet=b"".join(
                    proto_field(tag, value)
                    for tag, value in (
                        (8, 1),
                        (18, b"Personal"),
                        (24, (1 << 64) - 1),
                        (56, 1),
                        (64, 0),
                    )
                ),
                equipment=b"",
                aptitudes=b"",
                deck=default_deck(owned),
            )
            self.store.save_build(
                member["account"], member["generation"], identity, 1, blobs
            )
            character = self.store.activate_build(
                member["account"], member["generation"], identity, 1, in_fight=False
            )
            self.original_builds[identity] = character["builds"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_difficulty_selections(instance_id,stasis_level,competitive,competitive_max_level) VALUES(%s,2,true,50) ON CONFLICT(instance_id) DO UPDATE SET competitive=true,competitive_max_level=50",
                (self.instance_id,),
            )
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=ANY(%s)",
                (
                    self.instance_id,
                    [member["character"]["id"] for member in self.members],
                ),
            )

    def test_all_participants_reopen_auto_profile_and_exit_restores_owned_selection_wounds(
        self,
    ):
        from wakfu_server import health_policy
        from wakfu_server.equipment_stats import effective_character

        reopened = self.reopen()
        for member in self.members:
            identity = member["character"]["id"]
            character = reopened.character(member["account"], identity)
            self.assertEqual(
                (character["level"], character["effective_level"]), (200, 50)
            )
            self.assertEqual(
                character["dungeon_modulation"]["owned_active_build_index"], 1
            )
            maximum = dungeon_modulation.effective_health_max(character)
            self.assertEqual(
                (character["max_hp"], character["hp"]), (maximum, maximum - 17)
            )
            with self.store.connection() as db:
                persisted = db.execute(
                    "SELECT active_index FROM character_build_selection WHERE character_id=%s",
                    (identity,),
                ).fetchone()
                self.assertEqual(persisted["active_index"], 1)
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS count FROM character_builds WHERE character_id=%s",
                        (identity,),
                    ).fetchone()["count"],
                    1,
                )
                health_policy.reconfigure(db, character, maximum)
                db.execute(
                    "UPDATE characters SET instance_id=0 WHERE id=%s", (identity,)
                )
                restored = self.store.character(member["account"], identity, db)
                restored_max = effective_character(restored)["max_hp"]
                health_policy.reconfigure(db, restored, restored_max)
            restored = reopened.character(member["account"], identity)
            self.assertNotIn("dungeon_modulation", restored)
            self.assertEqual(
                (restored["active_build_index"], restored["effective_level"]), (1, 200)
            )
            self.assertEqual(restored["builds"], self.original_builds[identity])
            self.assertEqual(
                (restored["hp_damage"], restored["hp"]), (17, restored["max_hp"] - 17)
            )

    def test_temporary_sheet_cannot_be_persisted_activated_or_deleted(self):
        member = self.members[0]
        identity = member["character"]["id"]
        character = self.store.character(member["account"], identity)
        auto_index = character["active_build_index"]
        auto = {
            key: bytes.fromhex(value)
            for key, value in character["builds"][auto_index].items()
        }
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.store.save_build(
                member["account"], member["generation"], identity, auto_index, auto
            )
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.store.activate_build(
                member["account"], member["generation"], identity, 1, in_fight=False
            )
        with self.assertRaisesRegex(ValueError, "modulation"):
            self.store.delete_build(
                member["account"], member["generation"], identity, 1, in_fight=False
            )
        # An ordinary owned sheet can still be edited without altering selection.
        owned = {
            key: bytes.fromhex(value) for key, value in character["builds"][1].items()
        }
        updated = self.store.save_build(
            member["account"], member["generation"], identity, 1, owned
        )
        self.assertEqual(updated["active_build_index"], auto_index)
        self.assertEqual(updated["dungeon_modulation"]["owned_active_build_index"], 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS count FROM character_builds WHERE character_id=%s",
                    (identity,),
                ).fetchone()["count"],
                1,
            )
