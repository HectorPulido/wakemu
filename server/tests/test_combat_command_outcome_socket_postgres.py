"""Actual socket command and native Rift settlement on an isolated incident.

The encounter is deliberately reconstructed, not a paid-action gameplay proof.
Wave references, durable bindings, participant leases and settlement are real.
"""
import time
from types import SimpleNamespace
from unittest.mock import Mock

from postgres_case import PostgresCase
import test_combat_admin_recovery as incident
import test_astrub_dispatch as socket_fixture
from test_party_instance_publication_recovery import published
from wakfu_server.combat_instance_publication import (
    bind_party_encounter,
    require_current_publication,
)
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_state import Actor
from wakfu_server.combat_encounter_roles import assigned_roles
from wakfu_server.combat_command_recovery import take_cancelled
from wakfu_server.combat_health import persist_owned
from wakfu_server.command_permissions import set_admin
from wakfu_server.rift_policy import select_wave
from wakfu_server import rift_runtime
from wakfu_server.rift_dispatch_combat import finish_accepted_action


class CombatCommandOutcomeSocketPostgresTests(PostgresCase):
    dispatcher = socket_fixture.AstrubDispatcherTests.dispatcher

    def outcome(self, win):
        fixture = incident.CombatAdminRecoveryTests.fixture(self)
        shared = fixture["shared"]
        account, old_generation, identity = fixture["owners"][0]
        self.account = account
        set_admin(
            self.store,
            account,
            True,
            operator="fixture",
            reason="isolated explicit outcome QA",
        )
        with self.store.connection() as db:
            run = rift_runtime._run(db, shared.instance_id)
            references = select_wave(run["catalog"], run["policy"], run["seed"], 1)
            pairs = tuple(
                (-200 - index, reference) for index, reference in enumerate(references)
            )
            rift_runtime.bind_wave(db, run["instance_id"], 1, pairs)
        roles = assigned_roles(shared.fight)
        sources = {}
        for index, (actor_id, reference) in enumerate(pairs):
            if actor_id not in shared.fight.actors:
                shared.fight.actors[actor_id] = Actor(
                    actor_id, roles.npc_team, (5, 1, 0), 20, 4, 2, 10, 1
                )
            actor = shared.fight.actors[actor_id]
            sources[actor_id] = dict(
                id=actor_id,
                ref=reference,
                instance_id=shared.instance_id,
                level=actor.effective_level,
            )
            fixture["registry"].by_actor[actor_id] = shared.fight.id
        shared.fight.order = [
            actor_id for actor_id in shared.fight.order if actor_id >= 0
        ] + list(sources)
        shared.fight.rift_monsters = sources
        shared.fight.rift_wave_state.update(
            catalog=run["catalog"],
            policy=run["policy"],
            seed=run["seed"],
            wave_actor_ids=list(sources),
            wave_species_refs=list(references),
        )
        shared.fight.phase = "active"
        shared.fight.winner = None
        shared.join_context = dict(
            monsters=sources,
            fight_started_at=time.monotonic() - 1,
            rift_accepted_action=lambda current, candidate, runtime, packets: finish_accepted_action(
                candidate, runtime, packets, initialize_actor=None
            ),
        )
        publications = [published(owner) for owner in fixture["sessions"]]
        bind_party_encounter(
            shared.fight,
            publications=tuple(publications),
            npc_ids=tuple(sources),
            player_ids=tuple(sorted(fixture["ids"])),
        )
        for source, scope in publications:
            source.invalidate()
        with self.assertRaises(ValueError):
            require_current_publication(shared.fight)
        current_owners = []
        for peer_account, previous, peer_identity in fixture["owners"][:2]:
            generation = self.store.begin_session(peer_account, ttl=10000)
            self.store.select_character(peer_account, generation, peer_identity)
            current_owners.append((peer_account, generation, peer_identity))
        self.generation = current_owners[0][1]
        self.saved = self.store.character(account, identity)
        namespace, sent, actor = self.dispatcher(complete=True)
        adapter = CombatSessionAdapter(self.store)
        adapter.registry = fixture["registry"]
        writer = Mock()
        writer.flush_fight.return_value = True
        writer.flush_for_takeover.return_value = True
        writer.takeover_writer.side_effect = lambda *args, persist: persist()
        namespace.update(
            COMBAT_SESSIONS=adapter,
            CHECKPOINT_WRITER=writer,
            POSITIONS=fixture["positions"],
        )
        # Unfinished publication custody must not be mistaken for a native ACK.
        shared.pending_publication_recoveries = {
            account: SimpleNamespace(session=fixture["sessions"][0])
        }
        shared.publication_recovery_origins = {account: fixture["sessions"][0]}
        answer = namespace["execute_test_command"]("!winfight" if win else "!losefight")
        self.assertIn("message", answer)
        self.assertIsNone(namespace["fight"])
        self.assertIsNone(namespace["combat_session"])
        self.assertTrue(shared.settlement_ready)
        self.assertEqual(shared.fight.native_timeline_round, 7)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT outcome,result FROM rift_settlement_receipts WHERE fight_id=%s",
                (shared.fight.id,),
            ).fetchone()
            self.assertEqual(receipt["outcome"], "closed" if win else "lost")
            self.assertEqual(receipt["result"]["turn"], 7)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s AND (xp<>0 OR kamas<>0)",
                    (shared.fight.id,),
                ).fetchone()["n"],
                0,
            )
        # Every remaining owner must be able to use the normal committed return,
        # including the still-connected peer, without stale recovery stage gates.
        for peer_account, participant in tuple(shared.participants.items()):
            if peer_account == account:
                continue
            if peer_account == fixture["owners"][2][0]:
                with self.store.connection() as db:
                    saved = self.store.character(
                        peer_account, participant.character_id, db
                    )
                    persist_owned(
                        self.store,
                        peer_account,
                        participant.generation,
                        saved,
                        shared.fight,
                        db=db,
                    )
                fixture["registry"].mark_returned(shared.fight.id, participant)
            else:
                self.assertIn(peer_account, shared.returned)
                self.assertIs(take_cancelled(fixture["registry"], participant), shared)
        self.assertFalse(shared.pending_publication_recoveries)
        self.assertFalse(shared.publication_recovery_origins)
        self.assertFalse(fixture["registry"].command_cancellations)
        self.assertFalse(fixture["registry"].fights)
        self.assertFalse(fixture["registry"].by_character)
        self.assertFalse(fixture["registry"].by_actor)

    def test_forced_rift_victory_from_deferred_selected_world_uses_real_settlement(
        self,
    ):
        self.outcome(True)

    def test_forced_rift_defeat_from_deferred_selected_world_uses_real_settlement(self):
        self.outcome(False)
