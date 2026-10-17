import tempfile
from psycopg.pq import TransactionStatus
from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_rewards import Policy, award, load
from wakfu_server.progression import level_xp


def setup_reward_state(store):
    store.clock = lambda: 1000
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
    fight.phase = "finished"
    fight.winner = 0
    with store.connection() as db:
        for fight_id in (7, 8):
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(%s,'finished')",
                (fight_id,),
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, character["id"], account),
            )
    return store, account, character, generation, fight


class RewardTests(PostgresCase):
    def test_native_xp_crosses_old_cap_reaches245_and_replays_once(self):
        from wakfu_server.health_store import initialize

        s, account, character, generation, fight = setup_reward_state(self.store)
        with s.connection() as db:
            db.execute(
                "UPDATE characters SET level=200 WHERE id=%s", (character["id"],)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(200), character["id"]),
            )
        initialize(s, account, generation, character["id"])
        first = award(
            s,
            account,
            generation,
            character["id"],
            fight,
            Policy(xp=level_xp(201) - level_xp(200)),
        )
        self.assertEqual(first["character"]["level"], 201)
        self.assertEqual(
            (first["xp_info"]["start_level"], first["xp_info"]["end_level"]), (200, 201)
        )
        fight.id = 8  # The fixture has two distinct finished durable fights.
        second = award(
            s,
            account,
            generation,
            character["id"],
            fight,
            Policy(xp=level_xp(245) - level_xp(201)),
        )
        self.assertEqual(
            (second["character"]["level"], second["character"]["xp"]),
            (245, level_xp(245)),
        )
        replay = award(s, account, generation, character["id"], fight, Policy(xp=123))
        self.assertFalse(replay["awarded"])
        restored = self.reopen().character(account, character["id"])
        self.assertEqual((restored["level"], restored["xp"]), (245, level_xp(245)))

    def test_level_reward_updates_maximum_without_healing_wounds_and_replay(self):
        from wakfu_server.health import maximum

        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            with s.connection() as db:
                damage = c["max_hp"] - 20
                db.execute(
                    "UPDATE characters SET hp=20,hp_damage=%s,health_dead=false WHERE id=%s",
                    (damage, c["id"]),
                )
            result = award(s, a, g, c["id"], f, Policy(xp=level_xp(3), kamas=17))
            new_maximum = maximum(c["breed"], 3)
            expected = (max(1, new_maximum - damage), new_maximum)
            self.assertEqual(
                (result["character"]["hp"], result["character"]["max_hp"]), expected
            )
            self.assertEqual(result["character"]["hp_damage"], damage)
            restored = self.reopen().character(a, c["id"])
            self.assertEqual((restored["hp"], restored["max_hp"]), expected)
            self.assertEqual(restored["hp_damage"], damage)
            duplicate = award(s, a, g, c["id"], f, Policy(xp=999))
            self.assertFalse(duplicate["awarded"])
            self.assertEqual(
                (duplicate["character"]["hp"], duplicate["character"]["max_hp"]),
                expected,
            )
            self.assertEqual(duplicate["character"]["hp_damage"], damage)

    def test_level_health_failure_rolls_back_reward_and_wallet(self):
        from unittest.mock import patch
        from wakfu_server.health_store import initialize

        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            before = s.character(a, c["id"])

            def fail_after_health(*args, **kwargs):
                updated = initialize(*args, **kwargs)
                self.assertGreater(updated["max_hp"], before["max_hp"])
                self.assertEqual(
                    kwargs["db"].info.transaction_status, TransactionStatus.INTRANS
                )
                raise ValueError("Injected failure after health writes")

            with patch(
                "wakfu_server.health_store.initialize", side_effect=fail_after_health
            ):
                with self.assertRaises(ValueError):
                    award(s, a, g, c["id"], f, Policy(xp=level_xp(3), kamas=17))
            after = s.character(a, c["id"])
            for key in ("level", "xp", "hp", "max_hp", "kamas", "builds"):
                self.assertEqual(after[key], before[key])
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )

    def test_group_settlement_rolls_back_with_reward_on_report_failure_then_commits(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.combat_lifecycle import prepare_finish
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.monsters import owned_instance

        store, account, character, generation, fight = self.setup_state("unused")
        groups = PersistentGroups(store, clock=lambda: 1000)
        key = groups.register(
            1134,
            0,
            501,
            [owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)],
        )
        lease, _ = groups.claim(key, generation, fight.id)
        runtime = RuntimeMessages(fight)
        metadata = {
            character["id"]: dict(
                kind="player",
                account_id=account,
                name=character["name"],
                breed=character["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        args = (
            store,
            account,
            generation,
            character,
            runtime,
            metadata,
        )
        kwargs = dict(
            duration_ms=1000,
            fight_instance_id=8,
            policy=Policy(xp=level_xp(2), kamas=5),
            groups=groups,
            group_lease=lease,
        )

        with self.assertRaisesRegex(ValueError, "provided together"):
            prepare_finish(*args, **dict(kwargs, group_lease=None))
        with store.database.pool.connection() as idle_db:
            with self.assertRaisesRegex(ValueError, "active transaction"):
                groups.finish(lease, defeated=True, db=idle_db)
        self.assertEqual(groups.snapshot()[0]["status"], "fighting")

        with patch(
            "wakfu_server.combat_lifecycle.combat_results.finish_messages",
            side_effect=ValueError("Injected report failure"),
        ):
            with self.assertRaisesRegex(ValueError, "Injected report failure"):
                prepare_finish(*args, **kwargs)
        self.assertEqual(groups.snapshot()[0]["status"], "fighting")
        with store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS count FROM fight_rewards").fetchone()[
                    "count"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "finished",
            )

        result = prepare_finish(*args, **kwargs)
        self.assertTrue(result["reward"]["awarded"])
        self.assertEqual(groups.snapshot()[0]["status"], "defeated")
        with store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS count FROM fight_rewards").fetchone()[
                    "count"
                ],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "finished",
            )

    def setup_state(self, directory):
        return setup_reward_state(self.store)

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
            reopened = self.reopen()
            with reopened.connection() as db:
                self.assertEqual(
                    load(db, reopened.character(a, c["id"], db)),
                    dict(xp=level_xp(3), kamas=17),
                )
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    1,
                )

    def test_default_zero_manual_level200_and_replaced_generation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.setup_state(directory)
            with s.connection() as db:
                db.execute("UPDATE characters SET level=200 WHERE id=%s", (c["id"],))
                db.execute(
                    "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                    (level_xp(200), c["id"]),
                )
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
            # Durable fight identity deduplicates a replay across session generations.
            self.assertFalse(
                award(s, a, newer, c["id"], f, Policy(kamas=10))["awarded"]
            )

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
                db.execute("UPDATE characters SET level=2 WHERE id=%s", (c["id"],))
            with self.assertRaises(ValueError):
                award(s, a, g, c["id"], f, Policy(xp=2**63 - 1, kamas=2**63 - 1))
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT kamas FROM account_wallets WHERE account_id=%s", (a,)
                    ).fetchone()["kamas"],
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
            reopened = self.reopen()
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
