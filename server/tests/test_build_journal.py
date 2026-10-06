"""Build-dependent gameplay remains durable in PostgreSQL."""
import unittest

from postgres_case import PostgresCase
from wakfu_server.wire import proto_field


class BuildPersistenceIntegrationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("builder", "local-builder-password")["id"]
        self.char = self.store.create_character(self.account, "Builder", breed=8)
        self.generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, self.generation, self.char["id"])

    def fixed_build(self, index=1, level=49):
        from wakfu_server import builds

        sheet = b"".join(
            proto_field(t, v)
            for t, v in [
                (8, index),
                (18, b"Fixed selected"),
                (24, level),
                (56, 1),
                (64, 0),
            ]
        )
        return self.store.save_build(
            self.account,
            self.generation,
            self.char["id"],
            index,
            dict(
                sheet=sheet,
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=proto_field(24, level),
            ),
        )

    def test_reward_level_preserves_selected_fixed_sheet_and_reconnect_state(self):
        from wakfu_server.combat_rewards import Policy, award
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.progression import level_xp

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=49,hp=20 WHERE id=%s", (self.char["id"],)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(49), self.char["id"]),
            )
        self.fixed_build()
        before = self.store.activate_build(
            self.account, self.generation, self.char["id"], 1, in_fight=False
        )
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        pc = Actor(self.char["id"], 0, (0, 0, 0), 20, 6, 4, 0, 49, self.account, True)
        npc = Actor(-1, 1, (1, 0, 0), 1, 4, 3, 0, 49)
        fight = Fight(
            fight_id,
            [pc, npc],
            [(0, 0, 0), (1, 0, 0)],
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(self.account)
        fight.apply_damage(pc.id, npc.id, 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.char["id"], self.account),
            )
        result = award(
            self.store,
            self.account,
            self.generation,
            pc.id,
            fight,
            Policy(xp=level_xp(50) - level_xp(49)),
        )
        after = result["character"]
        self.assertEqual(
            (after["level"], after["effective_level"], after["active_build_index"]),
            (50, 49, 1),
        )
        for key in ("hp", "max_hp", "builds"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["xp"], level_xp(50))
        restored = self.reopen().character(self.account, pc.id)
        for key in (
            "level",
            "effective_level",
            "active_build_index",
            "xp",
            "hp",
            "max_hp",
            "builds",
        ):
            self.assertEqual(restored[key], after[key])

    def test_build_activation_never_heals_and_preserves_death(self):
        from wakfu_server import builds

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=6,hp=110,max_hp=110,hp_damage=0,health_dead=false WHERE id=%s",
                (self.char["id"],),
            )
        self.fixed_build(index=0, level=6)
        plain_sheet = b"".join(
            proto_field(t, v)
            for t, v in [(8, 1), (18, b"Plain"), (24, (1 << 64) - 1), (56, 1), (64, 0)]
        )
        self.store.save_build(
            self.account,
            self.generation,
            self.char["id"],
            1,
            dict(
                sheet=plain_sheet,
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=b"",
            ),
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=100,hp_damage=10,health_dead=false WHERE id=%s",
                (self.char["id"],),
            )
        plain = self.store.activate_build(
            self.account, self.generation, self.char["id"], 1, in_fight=False
        )
        self.assertEqual((plain["max_hp"], plain["hp"]), (110, 100))
        self.store.activate_build(
            self.account, self.generation, self.char["id"], 0, in_fight=False
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=110,health_dead=true WHERE id=%s",
                (self.char["id"],),
            )
        self.store.activate_build(
            self.account, self.generation, self.char["id"], 1, in_fight=False
        )
        restored = self.reopen().character(self.account, self.char["id"])
        self.assertEqual((restored["hp"], restored["max_hp"]), (0, 110))
