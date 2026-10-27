"""Real quest/session/PG settlement over a bounded native KO component.

This does not qualify the authored three-turn Aguabrial encounter. Native NPC
birth and source pins are component fixtures; quest admission, session fencing,
ordinary death, settlement, event deduplication and outbox writes are real.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.achievements import storage
from wakfu_server.combat_aguabrial_scene import (
    authorize_aguabrial_scene,
    bind_aguabrial_start,
    earned_story_continuation,
)
from wakfu_server.combat_aguabrial_story import settle_aguabrial_story


class AguabrialStoryPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("aguabrial-owner", "local-password")["id"]
        self.identity = self.store.create_character(self.account, "Aguabrial Owner")[
            "id"
        ]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.identity)
        self.members = [
            dict(
                account_id=self.account,
                character_id=self.identity,
                session_generation=self.generation,
            )
        ]
        with self.store.connection() as db:
            self.before = dict(
                storage.load_locked(db, self.identity),
                variables={},
                objectives=[7834],
                running=[3797],
                completed=[],
                tracking=[],
                recent=[],
                completion_dates={},
            )
            storage.store(db, self.identity, self.before)
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) "
                "VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (self.fight_id, self.identity, self.account, self.generation),
            )

    def native_component(self):
        from test_combat_kill import NativeKillTests
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_controller_registry import (
            initialize_controller_registry,
            register_native_controller,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )

        player = Actor(
            self.identity,
            0,
            (0, 0, 0),
            100,
            6,
            3,
            10,
            20,
            owner_id=self.account,
            controlled=True,
        )
        boss = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 8, 20)
        fight = Fight(
            self.fight_id,
            [player, boss],
            {player.position, boss.position},
            {0: {player.position}, 1: {boss.position}},
        )
        for actor in fight.actors.values():
            actor.physical_radius = 0
            actor.native_fight_property_counts = {}
        fight.native_qi_snapshot = dict(x=0, y=0, width=2, height=1, cell_masks=[0, 0])
        initialize_global_pv_collections(fight, (player.id, boss.id))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(fight, physical_radii={player.id: 0, boss.id: 0}),
        )
        initialize_controller_registry(fight)
        for actor in fight.actors.values():
            register_native_controller(
                fight, actor.id, team=actor.team, controller_id=actor.id
            )
        _, stats, _, _, _, _, _ = NativeKillTests().fixture(1)
        for name in (
            "effect_stats",
            "effect_minima",
            "effect_maxima",
            "effect_base_minima",
            "effect_base_maxima",
            "effect_percentages",
            "effect_frozen",
        ):
            setattr(player, name, deepcopy(getattr(stats, name)))
        player.hp = 80
        # Only source publication is a fixture. Admission still authenticates
        # the real selected owner and reads the real durable quest authority.
        with self.store.connection() as db, patch(
            "wakfu_server.native_catalog.release", return_value="a" * 64
        ), patch(
            "wakfu_server.combat_encounter_source_revision.source_revision_matches",
            return_value=True,
        ):
            admitted = authorize_aguabrial_scene(
                self.store,
                db,
                fight,
                account_id=self.account,
                generation=self.generation,
                character_id=self.identity,
                monster_references=(1723,),
            )
        self.assertIsNotNone(admitted)
        fight.ready(self.account)
        fight.native_npc_initialization_receipts = {
            boss.id: dict(
                ref=1723,
                descriptor_level=boss.effective_level,
                raw_triples=[],
                resolved_states=[dict(state_id=1128), dict(state_id=1137)],
                applications=[],
                initialized=True,
            ),
        }
        self.assertTrue(bind_aguabrial_start(fight))
        return fight, player, boss

    def actual_ko(self):
        from wakfu_server.combat_kill import NativeKillHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_death_events import deliver_owned_death
        from wakfu_server.combat_event_replay import NativeEventSource

        fight, player, boss = self.native_component()
        authority = SimpleNamespace(property_counts=lambda p, a: {})
        handler = NativeKillHandler(
            fight,
            [],
            action_id=5,
            allocate_uid=lambda: 1001,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            rng=lambda: 0,
            authority=authority,
        )
        effect = dict(
            effect_class=28,
            parameter_count=1,
            parameters=[1, 0],
            target_masks=[[] for _ in range(7)],
        )
        invocation = EffectInvocation(240347, 215, boss.id, player.id, player.position)
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        lethal = next(
            row
            for row in reversed(fight.events)
            if row["kind"] == "kill_hp_minimum_update"
        )
        source = NativeEventSource(
            lethal["uid"],
            240347,
            lethal["hp_before"],
            boss.id,
            player.id,
            player.position,
            (1013,),
            6,
            player.id,
            None,
            False,
            False,
            False,
            True,
        )

        # No retained subscriptions in this bounded component. The real death
        # boundary validates OFF_PLAY and produces its own delivery receipt.
        def empty_replay(current, *, authority):
            current.validate()
            return ()

        deliver_owned_death(
            fight, player.id, source=source, replay=empty_replay, authority=authority
        )
        self.assertEqual((fight.phase, fight.winner, player.hp), ("finished", 1, 0))
        self.assertIsNotNone(earned_story_continuation(fight))
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight.id,)
            )
        return fight

    def counts(self, db):
        return tuple(
            db.execute(
                f"SELECT count(*) AS n FROM {table} WHERE character_id=%s",
                (self.identity,),
            ).fetchone()["n"]
            for table in (
                "character_achievement_events",
                "character_achievement_notifications",
                "character_achievement_reward_outbox",
            )
        )

    def test_real_admission_settlement_outbox_and_duplicate_preserve_loss(self):
        fight = self.actual_ko()
        with self.store.connection() as db:
            packets = settle_aguabrial_story(self.store, db, fight, self.members)
            after = storage.load_locked(db, self.identity)
            self.assertEqual(after, dict(self.before, objectives=[7834, 7835]))
            self.assertEqual([op for op, _ in packets[self.account]], [13832])
            self.assertEqual(self.counts(db), (1, 1, 0))
        with self.store.connection() as db:
            self.assertEqual(
                settle_aguabrial_story(self.store, db, fight, self.members), {}
            )
            self.assertEqual(self.counts(db), (1, 1, 0))
            pending = storage.pending_notifications(db, self.identity)
            self.assertEqual(len(pending), 1)
            self.assertEqual([p["opcode"] for p in pending[0]["packets"]], [13832])
        self.assertEqual((fight.phase, fight.winner), ("finished", 1))
        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertEqual(storage.load_locked(db, self.identity), after)

    def test_transaction_rollback_removes_objective_event_and_outbox_then_retry(self):
        fight = self.actual_ko()
        with self.assertRaisesRegex(RuntimeError, "rollback story"):
            with self.store.connection() as db:
                self.assertTrue(
                    settle_aguabrial_story(self.store, db, fight, self.members)
                )
                raise RuntimeError("rollback story")
        with self.store.connection() as db:
            self.assertEqual(storage.load_locked(db, self.identity), self.before)
            self.assertEqual(self.counts(db), (0, 0, 0))
            self.assertTrue(settle_aguabrial_story(self.store, db, fight, self.members))
            self.assertEqual(self.counts(db), (1, 1, 0))
        self.assertEqual(fight.winner, 1)
