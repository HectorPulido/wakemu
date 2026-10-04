import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_rewards import Policy, award, load
from wakfu_server.progression import level_xp


class RewardTests(unittest.TestCase):
    def setup_state(self, directory):
        store = Store(Path(directory) / "world.sqlite3", lambda: 1000)
        account = store.register("owner", "local-password")["id"]
        character = store.create_character(account, "Prueba")
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        fight = Fight(
            7,
            [
                Actor(character["id"], 0, (0, 0, 0), 60, 6, 3, 100, 1, account, True),
                Actor(-200, 1, (1, 0, 0), 12, 4, 2, 10, 1),
            ],
            [(0, 0, 0), (1, 0, 0)],
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(account)
        fight.apply_damage(character["id"], -200, 12)
        return store, account, character, generation, fight

    def test_configured_reward_once_and_reopen_native_level_progression(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            result = award(s, a, g, c["id"], f, Policy(xp=level_xp(3), kamas=17))
            self.assertEqual(
                (
                    result["character"]["level"],
                    result["character"]["xp"],
                    result["character"]["kamas"],
                ),
                (3, level_xp(3), 17),
            )
            again = award(s, a, g, c["id"], f, Policy(xp=99, kamas=99))
            self.assertFalse(again["awarded"])
            self.assertEqual((again["xp"], again["kamas"]), (level_xp(3), 17))
            reopened = Store(s.path, lambda: 1000)
            with reopened.connection() as db:
                self.assertEqual(
                    load(db, reopened.character(a, c["id"], db)),
                    dict(xp=level_xp(3), kamas=17),
                )
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM fight_rewards").fetchone()[0], 1
                )

    def test_default_zero_manual_level200_and_replaced_generation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            with s.connection() as db:
                db.execute("UPDATE characters SET level=200 WHERE id=?", (c["id"],))
            result = award(s, a, g, c["id"], f)
            self.assertEqual(
                (
                    result["character"]["level"],
                    result["character"]["xp"],
                    result["kamas"],
                ),
                (200, level_xp(200), 0),
            )
            newer = s.begin_session(a)
            s.select_character(a, newer, c["id"])
            with self.assertRaises(ValueError):
                award(s, a, g, c["id"], f, Policy(kamas=10))
            # A reused numeric fightID in another generation is independent.
            self.assertTrue(award(s, a, newer, c["id"], f, Policy(kamas=10))["awarded"])

    def test_ownership_defeat_and_overflow_fail_without_partial_award(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            f.winner = 1
            with self.assertRaises(ValueError):
                award(s, a, g, c["id"], f)
            f.winner = 0
            f.actors[c["id"]].owner_id = a + 1
            with self.assertRaises(ValueError):
                award(s, a, g, c["id"], f)
            f.actors[c["id"]].owner_id = a
            with s.connection() as db:
                db.execute("UPDATE characters SET level=2 WHERE id=?", (c["id"],))
            with self.assertRaises(ValueError):
                award(s, a, g, c["id"], f, Policy(xp=2**63 - 1, kamas=2**63 - 1))
            with s.connection() as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM fight_rewards").fetchone()[0], 0
                )
                self.assertEqual(
                    db.execute("SELECT xp,kamas FROM character_progression").fetchone()[
                        "kamas"
                    ],
                    0,
                )
            for amount in (-1, True, 2**63):
                with self.assertRaises(ValueError):
                    Policy(xp=amount)

    def test_earned_xp_between_levels_survives_reload_and_native_wire(self):
        import struct
        from wakfu_server import wire
        from wakfu_server.combat_actor import actor_stats
        from wakfu_server.progression import character_xp

        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            gained = level_xp(2) + 1
            self.assertLess(gained, level_xp(3))
            award(s, a, g, c["id"], f, Policy(xp=gained, kamas=23))
            reopened = Store(s.path, lambda: 1000)
            actual = reopened.character(a, c["id"])
            self.assertEqual((actual["level"], character_xp(actual)), (2, gained))
            self.assertEqual(
                struct.unpack_from(">q", actor_stats(actual, 7, wp=6), 1)[0], gained
            )
            fixture = (
                bytes([5]) + bytes(261) + struct.pack(">q", 4094076145) + b"afterXP"
            )
            encoded = wire.initial_progression(fixture, actual)
            self.assertEqual(struct.unpack_from(">q", encoded, 262)[0], gained)
            self.assertTrue(encoded.endswith(b"afterXP"))
            self.assertEqual(
                wire.adapt(13021, bytes(8), a, actual), struct.pack(">q", 23)
            )
            self.assertEqual(
                wire.adapt(
                    13873,
                    struct.pack(">IIq", 1, 6, 999),
                    a,
                    kamas=reopened.account_kamas(a),
                ),
                struct.pack(">IIq", 1, 6, 23),
            )
            second = reopened.create_character(a, "Second")
            self.assertEqual(
                second["kamas"], 23
            )  # Shared account wallet, independent XP.
            self.assertEqual(second["xp"], level_xp(1))
            with self.assertRaises(ValueError):
                character_xp(dict(actual, xp=level_xp(3)))

    def test_persisted_receipt_drives_native_report_and_survives_later_rewards(self):
        from wakfu_server.combat_rewards import report_metadata
        from wakfu_server.combat_results import fight_report
        from wakfu_server.wire import proto_fields

        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            first = award(s, a, g, c["id"], f, Policy(xp=level_xp(2) + 1, kamas=13))
            metadata = {
                c["id"]: dict(
                    kind="player",
                    account_id=a,
                    name=c["name"],
                    breed=c["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }
            own = report_metadata(metadata, c["id"], first)
            report = fight_report(
                f, own, duration_ms=1000, fight_instance_id=8, initiator_id=c["id"]
            )
            player = dict(
                proto_fields(dict(proto_fields(dict(proto_fields(report))[42]))[18])
            )
            self.assertEqual(player[72], 13)
            self.assertEqual(
                dict(proto_fields(player[66])),
                {8: level_xp(2) + 1, 16: level_xp(2) + 1, 40: 1, 48: 2},
            )
            f.id = 8
            award(s, a, g, c["id"], f, Policy(xp=1, kamas=1))
            f.id = 7
            duplicate = award(s, a, g, c["id"], f, Policy(xp=999, kamas=999))
            self.assertEqual(duplicate["xp_info"], first["xp_info"])
            self.assertEqual(duplicate["kamas"], 13)
            self.assertNotIn("xp_info", metadata[c["id"]])
