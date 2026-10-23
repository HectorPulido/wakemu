"""Neo account healing reaches actual admission actors without rejected-join grants."""
import struct
from copy import deepcopy
from types import SimpleNamespace

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.account_quest_inventory import grant
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_store import create
from wakfu_server.neo_regeneration import (
    freeze_fight_configuration,
    project_entry_character,
)


class NeoAdmissionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1700000000
        self.owners = []
        for label, x in (("leader", 0), ("joining", 1)):
            account = self.store.register("neo-" + label, "local-password")["id"]
            character = self.store.create_character(account, "Neo " + label)
            generation = self.store.begin_session(account)
            self.store.select_character(account, generation, character["id"])
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=1134,instance_id=0,x=%s,y=0,z=0 WHERE id=%s",
                    (x, character["id"]),
                )
            self.owners.append((account, character["id"], generation))
        with self.store.connection() as db:
            account, identity, _ = self.owners[1]
            grant(db, account, 32702, 1)
            self.maximum = db.execute(
                "SELECT max_hp FROM characters WHERE id=%s", (identity,)
            ).fetchone()["max_hp"]
            db.execute(
                "UPDATE characters SET hp=1,hp_damage=max_hp-1,health_dead=false WHERE id=%s",
                (identity,),
            )
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb({"version": 1, "is_neo_server": True}),),
            )

    def shared_fixture(self):
        adapter = CombatSessionAdapter(self.store)
        first, second = self.owners
        left = adapter.session(
            first[0], first[2], self.store.character(first[0], first[1])
        )
        right = adapter.session(
            second[0], second[2], self.store.character(second[0], second[1])
        )
        identity = create(self.store, first[0], first[2], first[1])
        leader = adapter.player_actor(left, team=0)
        monster = Actor(-200, 1, (3, 0, 0), 12, 4, 2, 10, 1)
        fight = Fight(
            identity,
            (leader, monster),
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        shared = adapter.register(left, fight)
        actor = adapter.player_actor(right, team=0)
        return adapter, left, right, shared, actor

    def test_actual_shared_admission_aligns_native_hp_and_preserves_other_resources(
        self,
    ):
        from wakfu_server.combat_hp_raw import hp_raw_current

        adapter, left, right, shared, actor = self.shared_fixture()
        before = (
            actor.max_hp,
            actor.ap,
            actor.mp,
            actor.max_ap,
            actor.max_mp,
            actor.effect_stats[4],
            deepcopy(actor.effect_maxima),
        )
        self.assertEqual(1, actor.hp)
        joined = adapter.join(
            right,
            struct.pack(">qB", left.character_id, 0),
            actor,
            bootstrap_packets=lambda *_: [(12847, b"isolated-placement")],
        )
        admitted = joined.fight.actors[right.character_id]
        self.assertEqual(
            (self.maximum,) * 3,
            (admitted.hp, admitted.effect_stats[1], hp_raw_current(admitted)),
        )
        self.assertEqual(
            before,
            (
                admitted.max_hp,
                admitted.ap,
                admitted.mp,
                admitted.max_ap,
                admitted.max_mp,
                admitted.effect_stats[4],
                admitted.effect_maxima,
            ),
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT entry_hp,entry_max_hp,entry_hp_damage FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
                (shared.fight.id, right.character_id),
            ).fetchone()
            self.assertEqual(
                {
                    "entry_hp": self.maximum,
                    "entry_max_hp": self.maximum,
                    "entry_hp_damage": 0,
                },
                row,
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=32702",
                    (right.account_id,),
                ).fetchone()["quantity"],
            )

    def test_rejected_shared_serialization_rolls_back_real_heal_and_membership(self):
        adapter, left, right, shared, actor = self.shared_fixture()

        def reject(*_args):
            raise ValueError("injected native serialization after admission heal")

        with self.assertRaisesRegex(ValueError, "injected"):
            adapter.join(
                right,
                struct.pack(">qB", left.character_id, 0),
                actor,
                actor_payload=reject,
                bootstrap_packets=lambda *_: [(12847, b"unpublished")],
            )
        self.assertNotIn(right.character_id, shared.fight.actors)
        self.assertEqual(1, actor.hp)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT hp,hp_damage FROM characters WHERE id=%s", (right.character_id,)
            ).fetchone()
            self.assertEqual({"hp": 1, "hp_damage": self.maximum - 1}, row)
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
                    (shared.fight.id, right.character_id),
                ).fetchone()
            )

    def test_duel_callback_receives_post_heal_character_source(self):
        from wakfu_server.combat_shared import Session
        from wakfu_server.friendly_duels import invite_challenge, answer_challenge

        a, b = self.owners
        first = Session(a[0], a[1], a[2], 1134, 0)
        second = Session(b[0], b[1], b[2], 1134, 0)
        invite_challenge(
            self.store, first, second, struct.pack(">qiihBB", b[1], 1, 0, 0, 0, 1)
        )
        received = {}

        def prepare(db, identity, invitation, source, recipient):
            received.update(source=source, recipient=recipient)
            return {"fight_id": identity}, lambda: None

        result = answer_challenge(
            self.store, second, struct.pack(">qBB", a[1], 1, 0), prepare_duel=prepare
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(
            (self.maximum, self.maximum, 0, False),
            tuple(
                received["recipient"][k]
                for k in ("hp", "max_hp", "hp_damage", "health_dead")
            ),
        )
        self.assertEqual(
            (1, 0, 0), tuple(received["recipient"][k] for k in ("x", "y", "z"))
        )

    def test_frozen_configuration_preserves_other_overrides_and_live_projection(self):
        from wakfu_server.combat_system_conditions import fresh_system_configuration

        fight = SimpleNamespace(
            native_system_configuration=dict(
                fresh_system_configuration(),
                overrides={"server.group.isneo": False, "another.policy": True},
            )
        )
        with self.store.connection() as db:
            self.assertTrue(freeze_fight_configuration(db, fight))
            self.assertTrue(
                fight.native_system_configuration["overrides"]["another.policy"]
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='dungeon_server_mode'",
                (Jsonb({"version": 1, "is_neo_server": False}),),
            )
            self.assertTrue(freeze_fight_configuration(db, fight))
        original = dict(
            id=8,
            account_id=9,
            hp=1,
            max_hp=100,
            hp_damage=99,
            health_dead=False,
            map_id=1134,
            instance_id=987654321,
            x=7,
            y=8,
            z=-1,
            territory_bonus={"saved": 1},
        )
        canonical = dict(original, hp=100, hp_damage=0, map_id=1, instance_id=0, x=0)
        projected = project_entry_character(original, canonical)
        self.assertEqual(100, projected["hp"])
        self.assertEqual(
            (1134, 987654321, 7, 8, -1),
            tuple(projected[k] for k in ("map_id", "instance_id", "x", "y", "z")),
        )
        self.assertEqual({"saved": 1}, projected["territory_bonus"])
        self.assertEqual(1, original["hp"])
