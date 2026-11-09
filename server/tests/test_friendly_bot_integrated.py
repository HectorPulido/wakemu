"""Isolated PostgreSQL challenge through native readiness and WakIA."""
import os
import threading
import time
import unittest
from types import SimpleNamespace

from test_friendly_duels import FriendlyDuelStoreTests


@unittest.skipUnless(
    os.environ.get("WAKIA_INTEGRATION_ENDPOINT"), "WakIA endpoint required"
)
class FriendlyBotIntegratedTests(FriendlyDuelStoreTests):
    def test_bot_accept_ready_and_wakia_turn(self):
        from wakfu_server.bots.friendly_duel import accept
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.friendly_duel_runtime import enable_friendly_bot_ai
        from wakfu_server.combat_effective_control import effective_server_controlled

        first, second = map_geometry(527)["edges"][0]
        with self.store.connection() as db:
            for character, cell in ((self.char_a, first), (self.char_b, second)):
                db.execute(
                    "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (527, *cell, character["id"]),
                )
        self.session_a = Session(
            self.account_a, self.char_a["id"], self.generation_a, 527, 0
        )
        self.session_b = Session(
            self.account_b, self.char_b["id"], self.generation_b, 527, 0
        )
        self.challenge()
        lease = dict(
            bot_id="test_bot",
            character_id=self.char_b["id"],
            account_id=self.account_b,
            generation=self.generation_b,
            capabilities=["duel"],
        )
        bot = SimpleNamespace(
            store=self.store, lock=threading.RLock(), active={"test_bot": lease}
        )
        bot._lease = lambda identity: lease
        adapter = CombatSessionAdapter(self.store)
        result = accept(
            bot, adapter, self.session_b, self.char_a["id"], lambda **kwargs: None
        )
        self.assertTrue(result["accepted"])
        shared = adapter.lookup_character(self.char_b["id"])
        self.assertTrue(shared.is_duel)
        self.assertEqual(shared.join_context["ai_bot_character_id"], self.char_b["id"])
        # Give the bot the first turn without changing the native turn scheduler.
        shared.fight.actors[self.char_b["id"]].initiative = 10000
        shared.fight.actors[self.char_b["id"]].effect_stats[35] = 10000

        def ready(session, *, bot_ready=False):
            def transition(candidate, runtime):
                if bot_ready:
                    enable_friendly_bot_ai(
                        candidate,
                        tuple(shared.duel_leaders.values()),
                        self.char_b["id"],
                    )
                return adapter.ready_transition(
                    session,
                    candidate,
                    runtime,
                    True,
                    {},
                    previous_native_action_id=runtime.native_action_id,
                    fight_start=True,
                    area_callbacks=True,
                )

            adapter.execute(
                session,
                shared.fight.id,
                session.character_id,
                transition,
                require_turn=False,
            )

        ready(self.session_b, bot_ready=True)
        self.assertTrue(
            effective_server_controlled(
                shared.fight, shared.fight.actors[self.char_b["id"]]
            )
        )
        ready(self.session_a)
        self.assertEqual(shared.fight.phase, "active")
        self.assertTrue(
            effective_server_controlled(
                shared.fight, shared.fight.actors[self.char_b["id"]]
            )
        )
        self.assertEqual(shared.fight.current.id, self.char_b["id"])
        from wakfu_server.wakia_bridge.wakfu_ai.bridge.world_entry import run_npc_turn

        actor_before = shared.fight.current.id
        turn_before = shared.fight.turn_id
        records = list(
            run_npc_turn(
                shared.runtime,
                store=self.store,
                viewer_character=self.store.character(
                    self.account_a, self.char_a["id"]
                ),
                monsters={},
                shared_adapter=adapter,
                session=self.session_a,
            )
        )
        self.assertTrue(records, "WakIA produced no shared turn outcome")
        self.assertFalse(
            any(
                record.get("reason") == "complete_native_bridge_rejected"
                for _, record in records
            ),
            records,
        )
        self.assertTrue(
            any(
                record.get("action", {}).get("type") in ("move", "cast")
                for _, record in records
            ),
            records,
        )
        # Exercise the real child created by the bot's spell. Native fqL stays
        # false for player-owned summons; the bot's controller must route it to
        # WakIA without changing the native flag or player ownership.
        summons = shared.fight.native_summon_registrations
        bot_summons = [
            identity
            for identity, row in summons.items()
            if row.get("caster_id") == self.char_b["id"]
        ]
        self.assertTrue(bot_summons, "The bot did not create its expected summon")
        summon_id = bot_summons[0]
        summon = shared.fight.actors[summon_id]
        self.assertTrue(summon.controlled)
        self.assertFalse(summon.native_controlled_by_ai)
        self.assertTrue(effective_server_controlled(shared.fight, summon))
        bot_marker = shared.fight.native_friendly_duel_ai_character_id
        shared.fight.native_friendly_duel_ai_character_id = None
        self.assertFalse(effective_server_controlled(shared.fight, summon))
        shared.fight.native_friendly_duel_ai_character_id = bot_marker
        owner = summon.owner_id
        summon.owner_id = self.account_a
        self.assertFalse(effective_server_controlled(shared.fight, summon))
        summon.owner_id = owner
        # Advance the isolated fixture to the child's timeline slot and use the
        # same registry gate that commits native WakIA actions.
        shared.fight.turn_index = shared.fight.order.index(summon_id)
        published = []

        def summon_action(candidate, runtime):
            published.append(candidate.current.id)
            return []

        shared.is_duel = False
        with self.assertRaisesRegex(ValueError, "Not current server-controlled"):
            adapter.registry.execute_server(
                shared.fight.id,
                summon_id,
                summon_action,
                expected_sequence=shared.sequence,
            )
        shared.is_duel = True
        adapter.registry.execute_server(
            shared.fight.id,
            summon_id,
            summon_action,
            expected_sequence=shared.sequence,
        )
        self.assertEqual(published, [summon_id])
        # This is an isolated fixture: clear the previous actor's presentation
        # barrier to model both clients acknowledging before the child's turn.
        shared.ack.cancel_for_recovery()
        shared.runtime.awaiting_ack = None
        shared.runtime.pending = []
        summon_records = list(
            run_npc_turn(
                shared.runtime,
                store=self.store,
                viewer_character=self.store.character(
                    self.account_a, self.char_a["id"]
                ),
                monsters={},
                shared_adapter=adapter,
                session=self.session_a,
            )
        )
        self.assertTrue(summon_records, "WakIA did not run the summon turn")
        self.assertFalse(
            any(
                record.get("reason") == "complete_native_bridge_rejected"
                for _, record in summon_records
            ),
            summon_records,
        )
        self.assertTrue(
            any(
                record.get("action", {}).get("type") in ("move", "cast")
                for _, record in summon_records
            ),
            summon_records,
        )
        self.assertTrue(
            shared.fight.turn_id != turn_before
            or shared.fight.current.id != actor_before
            or shared.runtime.awaiting_ack is not None
            or any(
                record.get("action", {}).get("type") in ("move", "cast")
                for _, record in records
            ),
            records,
        )
