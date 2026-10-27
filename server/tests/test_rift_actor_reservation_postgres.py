"""RF-W01: real allocator/checkpoint through the public Registry boundary.

Wave construction is isolated here; native births and GUI progression beyond
32 successors belong to the separate full-flow matrix. No kill command, ID
generator substitute, live player mutation or fake completed wave is used.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase


class RiftActorReservationTests(PostgresCase):
    def test_world_pending_refill_checkpoint_rejection_retry_and_no_per_action_allocation(
        self,
    ):
        from wakfu_server import rift_runtime, rift_dispatch_combat
        from wakfu_server.combat_shared import Registry, Session, Transition
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot
        from wakfu_server.rift_encounter_roles import roles_for_catalog
        from wakfu_server.combat_encounter_roles import bind_roles
        from wakfu_server.rift_policy import select_wave
        from wakfu_server.rift_dispatch_lifecycle import actor_reservation_shortfall
        from wakfu_server.npc_actor_identity import lua_exact_identity

        self.store.clock = lambda: 1000
        account = self.store.register("reservation", "test-password")["id"]
        character = self.store.create_character(account, "Reservation Owner")["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character)
        with self.store.connection() as db:
            run = rift_runtime.enter(
                db,
                3,
                character,
                [character],
                seed="reserve-flow",
                authorize=lambda *_: True,
            )
            refs = select_wave(run["catalog"], run["policy"], run["seed"], 1)
            roles = roles_for_catalog(
                run["catalog"], run["policy"], monster_references=refs
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,%s)",
                (fight_id, character, account, roles.player_team),
            )
            rift_runtime.start(db, run["instance_id"], character, fight_id)
            old_ids = tuple(-200 - index for index in range(len(refs)))
            rift_runtime.bind_wave(db, run["instance_id"], 1, zip(old_ids, refs))
        pc = Actor(
            character, roles.player_team, (0, 0, 0), 60, 6, 3, 100, 1, account, True
        )
        enemies = [
            Actor(uid, roles.npc_team, (index + 2, 0, 0), 20, 6, 3, 1, 1)
            for index, uid in enumerate(old_ids)
        ]
        fight = Fight(
            fight_id,
            [pc, *enemies],
            {(x, 0, 0) for x in range(12)},
            roles.placement_cells([pc.position], [actor.position for actor in enemies]),
        )
        bind_roles(fight, roles, player_ids=(character,), npc_ids=old_ids)
        fight.rift_wave_state = dict(
            instance_id=run["instance_id"],
            wave=1,
            turn_budget=40,
            catalog=run["catalog"],
            policy=run["policy"],
            seed=run["seed"],
            wave_actor_ids=list(old_ids),
            actor_id_pool=[],
        )
        fight.ready(account)
        # Real FSM damage stages the pending boundary. It is a fixture premise,
        # not evidence of paid client kills or a completed >32-wave traversal.
        for enemy in enemies:
            fight.apply_damage(character, enemy.id, enemy.hp)
        self.assertIsNotNone(fight.rift_wave_state.get("pending_wave"))
        self.assertEqual(actor_reservation_shortfall(fight), len(refs))
        checkpoints = Checkpoints(self.store)
        baseline_revision = checkpoints.save(account, generation, fight)
        session = Session(
            account, character, generation, run["catalog"]["map_id"], run["instance_id"]
        )
        registry = Registry(
            lambda current: bool(
                self.store.current_character_session(
                    current.account_id, current.generation, current.character_id
                )
            )
        )
        shared = registry.register(
            fight, session, runtime=RuntimeMessages(fight), join_context={}
        )
        shared.checkpoint_revision = baseline_revision

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        node = next(
            node
            for node in ast.walk(ast.parse(source.read_text()))
            if isinstance(node, ast.FunctionDef)
            and node.name == "checkpoint_accepted_rift"
        )
        reject = [True]
        attempts = []

        class CheckpointBoundary:
            def save(_, *args, **kwargs):
                if reject[0]:
                    raise ValueError("checkpoint publication rejected")
                return checkpoints.save(*args, **kwargs)

        namespace = dict(
            STORE=self.store,
            CHECKPOINTS=CheckpointBoundary(),
            COMBAT_SESSIONS=SimpleNamespace(),
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        shared.join_context["rift_accepted_action"] = namespace[
            "checkpoint_accepted_rift"
        ]

        def observed_wave(candidate, runtime, packets, **kwargs):
            pool = tuple(candidate.rift_wave_state["actor_id_pool"])
            self.assertGreaterEqual(len(pool), len(refs))
            attempts.append(pool)
            return Transition(candidate, runtime, packets)

        before = snapshot(shared.fight)
        sequence = shared.sequence
        with patch.object(
            rift_dispatch_combat, "finish_accepted_action", observed_wave
        ):
            with self.assertRaisesRegex(ValueError, "checkpoint publication rejected"):
                registry.execute(fight_id, session, character, lambda *_: ())
            self.assertEqual(snapshot(shared.fight), before)
            self.assertEqual(shared.sequence, sequence)
            self.assertEqual(shared.checkpoint_revision, baseline_revision)
            self.assertEqual(
                checkpoints.read(account, fight_id)["revision"], baseline_revision
            )
            reject[0] = False
            registry.execute(fight_id, session, character, lambda *_: ())
            adopted = tuple(shared.fight.rift_wave_state["actor_id_pool"])
            self.assertEqual(len(adopted), 128)
            self.assertTrue(all(lua_exact_identity(uid) and uid < 0 for uid in adopted))
            self.assertFalse(set(adopted) & set(attempts[0]))
            self.assertFalse(set(adopted) & set(shared.fight.actors))
            self.assertEqual(actor_reservation_shortfall(shared.fight), 0)
            durable = checkpoints.read(account, fight_id)["snapshot"]
            self.assertEqual(durable["rift_wave_state"]["actor_id_pool"], list(adopted))
            with self.store.connection() as db:
                allocated = db.execute(
                    "SELECT last_value FROM lua_exact_npc_actor_ids"
                ).fetchone()["last_value"]
            registry.execute(fight_id, session, character, lambda *_: ())
            with self.store.connection() as db:
                after = db.execute(
                    "SELECT last_value FROM lua_exact_npc_actor_ids"
                ).fetchone()["last_value"]
            self.assertEqual(after, allocated)
        self.assertEqual(tuple(shared.fight.rift_wave_state["actor_id_pool"]), adopted)
        self.assertEqual(shared.fight.rift_wave_state["policy"]["turn_budget"], 40)
        self.assertEqual(
            select_wave(run["catalog"], run["policy"], run["seed"], 2),
            select_wave(
                shared.fight.rift_wave_state["catalog"],
                shared.fight.rift_wave_state["policy"],
                shared.fight.rift_wave_state["seed"],
                2,
            ),
        )
        self.assertEqual(len(registry.drain(fight_id, session)), 2)
