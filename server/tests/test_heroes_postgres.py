"""PostgreSQL coverage for same-account native HEROES rosters."""
import unittest
import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.characters import heroes


class HeroesPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("heroes-owner", "heroes-password")["id"]
        self.main = self.store.create_character(self.account, "Hero Main")
        self.hero_a = self.store.create_character(self.account, "Hero Alpha")
        self.hero_b = self.store.create_character(self.account, "Hero Beta")
        self.hero_c = self.store.create_character(self.account, "Hero Gamma")
        self.foreign_account = self.store.register("heroes-foreign", "heroes-password")[
            "id"
        ]
        self.foreign = self.store.create_character(self.foreign_account, "Foreign Hero")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])

    def _roster(self, main_id=None):
        with self.store.connection() as db:
            return heroes.load_roster(
                db, self.store, self.account, main_id or self.main["id"]
            )

    def test_saved_company_restores_missing_real_party_without_replacing_existing_party(
        self,
    ):
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        with self.store.connection() as db:
            previous = db.execute(
                "SELECT party_id FROM player_party_members WHERE character_id=%s",
                (self.main["id"],),
            ).fetchone()["party_id"]
            db.execute("DELETE FROM player_parties WHERE id=%s", (previous,))
        restored = heroes.ensure_company_party(
            self.store, self.account, self.generation, self.main["id"]
        )
        self.assertEqual(
            [self.hero_a["id"]], [hero["id"] for hero in restored["heroes"]]
        )
        with self.store.connection() as db:
            current = db.execute(
                "SELECT party_id FROM player_party_members WHERE character_id=%s",
                (self.main["id"],),
            ).fetchone()["party_id"]
            self.assertNotEqual(previous, current)
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (self.foreign["id"], current),
            )
        heroes.ensure_company_party(
            self.store, self.account, self.generation, self.main["id"]
        )
        with self.store.connection() as db:
            self.assertEqual(
                current,
                db.execute(
                    "SELECT party_id FROM player_party_members WHERE character_id=%s",
                    (self.main["id"],),
                ).fetchone()["party_id"],
            )
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (current,),
                ).fetchone()["n"],
            )

    def test_empty_company_does_not_create_party_and_stale_restore_is_rejected(self):
        heroes.ensure_company_party(
            self.store, self.account, self.generation, self.main["id"]
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT party_id FROM player_party_members WHERE character_id=%s",
                    (self.main["id"],),
                ).fetchone()
            )
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            heroes.ensure_company_party(
                self.store, self.account, self.generation, self.main["id"]
            )

    def test_add_remove_persists_real_characters_without_losing_character_state(self):
        hero_id = self.hero_a["id"]
        before = self.store.character(self.account, hero_id)
        result = heroes.add(
            self.store, self.account, self.generation, self.main["id"], hero_id
        )
        self.assertTrue(result["applied"])
        self.assertEqual([hero_id], [c["id"] for c in result["heroes"]])
        self.assertEqual(
            (
                self.main["map_id"],
                self.main["instance_id"],
                self.main["x"],
                self.main["y"],
                self.main["z"],
            ),
            tuple(
                result["heroes"][0][k] for k in ("map_id", "instance_id", "x", "y", "z")
            ),
        )
        after = self.store.character(self.account, hero_id)
        for key in (
            "breed",
            "level",
            "xp",
            "hp",
            "max_hp",
            "appearance",
            "active_build_index",
        ):
            if key in before:
                self.assertEqual(before[key], after[key], key)
        from wakfu_server import builds, spells, wire

        self.assertEqual(before["builds"], {})
        expected_sheet = next(
            value
            for tag, value in wire.proto_fields(builds.build_set(before, b""))
            if tag == 18
        )
        self.assertEqual(
            after["builds"],
            {
                0: {
                    "sheet": expected_sheet.hex(),
                    "equipment": "",
                    "aptitudes": "",
                    "deck": spells.default_deck(
                        dict(before, effective_level=before["level"])
                    ).hex(),
                }
            },
        )
        reopened = self.reopen()
        with reopened.connection() as db:
            restored = heroes.load_roster(db, reopened, self.account, self.main["id"])
        self.assertEqual((hero_id,), tuple(c["id"] for c in restored["heroes"]))
        self.assertFalse(
            heroes.add(
                self.store, self.account, self.generation, self.main["id"], hero_id
            )["applied"]
        )
        removed = heroes.remove(
            self.store, self.account, self.generation, self.main["id"], hero_id
        )
        self.assertTrue(removed["applied"])
        self.assertEqual((), removed["heroes"])
        self.assertFalse(
            heroes.remove(
                self.store, self.account, self.generation, self.main["id"], hero_id
            )["applied"]
        )
        self.assertIsNotNone(self.store.character(self.account, hero_id))

    def test_two_native_slots_cap_and_ordinary_party_exclusivity(self):
        first = heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        second = heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_b["id"],
        )
        self.assertEqual((0, 1), second["slots"])
        with self.assertRaisesRegex(ValueError, "slots are full"):
            heroes.add(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                self.hero_c["id"],
            )
        self.assertEqual(
            (self.hero_a["id"], self.hero_b["id"]),
            tuple(c["id"] for c in self._roster()["heroes"]),
        )

    def test_account_ownership_self_deleted_and_stale_session_are_rejected(self):
        for identity in (self.main["id"], self.foreign["id"], -1):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                heroes.add(
                    self.store, self.account, self.generation, self.main["id"], identity
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,health_dead=true WHERE id=%s",
                (self.hero_b["id"],),
            )
        with self.assertRaisesRegex(ValueError, "[Dd]ead"):
            heroes.add(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                self.hero_b["id"],
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET deleted_at=CURRENT_TIMESTAMP WHERE id=%s",
                (self.hero_c["id"],),
            )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            heroes.add(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                self.hero_c["id"],
            )
        self.store.end_session(self.account, self.generation)
        with self.assertRaises(ValueError):
            heroes.add(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                self.hero_a["id"],
            )

    def test_main_character_switch_rebinds_roster_and_keeps_old_main_as_real_hero(self):
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        self.store.select_character(self.account, self.generation, self.hero_a["id"])
        switched = heroes.select_main(
            self.store, self.account, self.generation, self.hero_a["id"]
        )
        self.assertEqual(self.hero_a["id"], switched["leader"]["id"])
        self.assertEqual((self.main["id"],), tuple(c["id"] for c in switched["heroes"]))
        self.assertEqual((0,), switched["slots"])
        with self.store.connection() as db:
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (self.account,)
            ).fetchone()
        self.assertEqual(self.hero_a["id"], session["character_id"])

    def test_atomic_main_switch_swaps_active_hero_and_updates_session_and_positions(
        self,
    ):
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        main_before = self.store.character(self.account, self.main["id"])
        switched = heroes.switch_main(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        self.assertTrue(switched["applied"])
        self.assertEqual(self.hero_a["id"], switched["leader"]["id"])
        self.assertEqual((self.main["id"],), tuple(c["id"] for c in switched["heroes"]))
        self.assertEqual(
            (
                main_before["map_id"],
                main_before["instance_id"],
                main_before["x"],
                main_before["y"],
                main_before["z"],
            ),
            tuple(
                switched["leader"][k] for k in ("map_id", "instance_id", "x", "y", "z")
            ),
        )
        hero_now = self.store.character(self.account, self.hero_a["id"])
        self.assertEqual(
            tuple(
                switched["leader"][k] for k in ("map_id", "instance_id", "x", "y", "z")
            ),
            tuple(hero_now[k] for k in ("map_id", "instance_id", "x", "y", "z")),
        )
        with self.store.connection() as db:
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (self.account,)
            ).fetchone()
        self.assertEqual(self.hero_a["id"], session["character_id"])
        self.assertFalse(
            heroes.switch_main(
                self.store,
                self.account,
                self.generation,
                self.hero_a["id"],
                self.hero_a["id"],
            )["applied"]
        )

    def test_three_round_main_switch_keeps_canonical_two_hero_party_account_scoped(
        self,
    ):
        """Repeated native main changes keep the same real three-character roster."""
        from test_party_snapshot import PartySnapshotTests
        from wakfu_server import party_snapshot

        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_b["id"],
        )
        foreign_generation = self.store.begin_session(self.foreign_account)
        self.store.select_character(
            self.foreign_account, foreign_generation, self.foreign["id"]
        )
        foreign_hero = self.store.create_character(
            self.foreign_account, "Foreign Companion"
        )
        heroes.add(
            self.store,
            self.foreign_account,
            foreign_generation,
            self.foreign["id"],
            foreign_hero["id"],
        )

        expected = {self.main["id"], self.hero_a["id"], self.hero_b["id"]}
        current_main_id = self.main["id"]
        for target in (self.hero_a["id"], self.hero_b["id"], self.main["id"]):
            with self.subTest(target=target):
                switched = heroes.switch_main(
                    self.store, self.account, self.generation, current_main_id, target
                )
                self.assertTrue(switched["applied"])
                current_main_id = target
                with self.store.connection() as db:
                    main_row = self.store.character(self.account, target, db)
                    members = heroes.augment_party(db, self.store, [main_row])
                self.assertEqual(expected, {row["id"] for row in members})
                self.assertEqual(3, len(members))
                snapshot = {
                    "party_id": (1 << 56) | (target & ((1 << 56) - 1)),
                    "leader_id": target,
                    "members": members,
                }
                levels = {row["id"]: row["effective_level"] for row in members}
                opcode, body = party_snapshot.packet(snapshot, effective_levels=levels)
                self.assertEqual(1184, opcode)
                decoded = PartySnapshotTests._decode_roster(body)
                self.assertEqual(expected, {row["id"] for row in decoded})
                self.assertEqual(target, struct.unpack_from(">qBhqh", body)[3])
                self.assertEqual(target, members[0]["id"])
                self.assertEqual(2, sum(row["native_identity_flag"] for row in decoded))
                self.assertEqual({self.account}, {row["account_id"] for row in decoded})

        with self.store.connection() as db:
            foreign_roster = heroes.load_roster(
                db, self.store, self.foreign_account, self.foreign["id"]
            )
        self.assertEqual(
            (foreign_hero["id"],), tuple(row["id"] for row in foreign_roster["heroes"])
        )

    def test_main_switch_requires_active_owned_hero_and_stale_lease_rolls_back(self):
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        for invalid in (self.hero_b["id"], self.foreign["id"]):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "active owned hero"
            ):
                heroes.switch_main(
                    self.store, self.account, self.generation, self.main["id"], invalid
                )
        replacement = self.store.begin_session(self.account)
        self.store.select_character(self.account, replacement, self.main["id"])
        with self.assertRaises(ValueError):
            heroes.switch_main(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                self.hero_a["id"],
            )
        with self.store.connection() as db:
            roster = db.execute(
                "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
                (self.account,),
            ).fetchone()
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (self.account,)
            ).fetchone()
        self.assertEqual(self.main["id"], roster["leader_id"])
        self.assertEqual(self.main["id"], session["character_id"])

    def test_roster_mutations_reject_active_combat_and_active_rift(self):
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, self.main["id"], self.account),
            )
        with self.assertRaisesRegex(ValueError, "during combat"):
            heroes.add(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                self.hero_a["id"],
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
            )
            instance_id = db.execute(
                "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed,status) "
                "VALUES(1,%s,%s,%s,%s,'heroes-test','running') RETURNING instance_id",
                (self.main["id"], Jsonb([self.main["id"]]), Jsonb({}), Jsonb({})),
            ).fetchone()["instance_id"]
        with self.assertRaisesRegex(ValueError, "active rift"):
            heroes.add(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                self.hero_a["id"],
            )


if __name__ == "__main__":
    unittest.main()
