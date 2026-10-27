"""Live multi-account emergency exits using real isolated PostgreSQL custody."""
import test_combat_admin_recovery as recovery_fixture
from wakfu_server.combat_command_recovery import bind_selected, cancel
from wakfu_server.combat_shared import Session
from unittest.mock import Mock
from wakfu_server import console_relocation


class CombatCommandRecoveryTests(recovery_fixture.CombatAdminRecoveryTests):
    # Reuse only fixture construction, not the HTTP/offline qualification.
    test_actual_five_member_offline_abort_preserves_health_then_reselect_create_and_new_fight = (
        None
    )

    def test_live_rift_cancel_relocate_and_later_selection_preserve_all_wounds(self):
        fixture = self.fixture()
        shared = fixture["shared"]
        owner = fixture["owners"][0]
        shared.fight.phase = "active"
        shared.fight.winner = None
        result = cancel(self.store, fixture["registry"], fixture["sessions"][0])
        self.assertIs(result["shared"], shared)
        self.assertEqual(set(result["exits"]), set(fixture["ids"]))
        self.assertFalse(fixture["registry"].fights)
        self.assertFalse(fixture["registry"].by_character)
        self.assertFalse(fixture["registry"].by_actor)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (shared.fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (shared.instance_id,),
                ).fetchone()["status"],
                "closed",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (shared.fight.id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s AND reason='abort'",
                    (shared.fight.id,),
                ).fetchone()["n"],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM fight_checkpoints WHERE fight_id=%s",
                    (shared.fight.id,),
                ).fetchone()["status"],
                "aborted",
            )
        source = self.store.character(owner[0], owner[2])
        moved = console_relocation.relocate(
            self.store,
            *owner,
            source,
            dict(map_id=527, instance_id=0, x=0, y=32, z=0),
            positions=fixture["positions"],
        )
        self.assertEqual((moved["map_id"], moved["instance_id"]), (527, 0))
        for account, generation, identity in fixture["owners"]:
            self.assertEqual(
                self.store.character(account, identity)["hp"],
                fixture["expected"][identity],
            )
        for identity in fixture["heroes"]:
            hero = self.store.character(owner[0], identity)
            self.assertEqual((hero["map_id"], hero["instance_id"]), (527, 0))
            self.assertEqual(hero["hp"], fixture["expected"][identity])
        with self.store.connection() as db:
            self.assertFalse(
                db.execute(
                    "SELECT 1 FROM rift_settlement_receipts WHERE fight_id=%s",
                    (shared.fight.id,),
                ).fetchone()
            )
        generation = self.store.begin_session(owner[0], ttl=10000)
        self.store.select_character(owner[0], generation, fixture["heroes"][0])
        created = self.store.create_character(owner[0], "Emergency New")
        self.assertGreater(created["id"], 0)

    def test_selected_new_generation_can_cancel_without_rebuilding_pending_native_presentation(
        self,
    ):
        fixture = self.fixture()
        shared = fixture["shared"]
        account, previous_generation, identity = fixture["owners"][0]
        generation = self.store.begin_session(account, ttl=10000)
        self.store.select_character(account, generation, identity)
        selected = Session(
            account, identity, generation, shared.map_id, shared.instance_id
        )
        writer = Mock()
        writer.flush_for_takeover.return_value = True
        writer.takeover_writer.side_effect = lambda *args, persist: persist()
        original = (shared.fight, shared.runtime, shared.ack)
        bind_selected(self.store, fixture["registry"], selected, writer)
        self.assertEqual((shared.fight, shared.runtime, shared.ack), original)
        self.assertNotIn(account, shared.connected)
        with self.store.connection() as db:
            generations = db.execute(
                "SELECT DISTINCT session_generation FROM combat_fight_participants WHERE fight_id=%s AND account_id=%s",
                (shared.fight.id, account),
            ).fetchall()
            self.assertEqual(
                [row["session_generation"] for row in generations], [generation]
            )
        peer_account, peer_previous, peer_identity = fixture["owners"][1]
        peer_generation = self.store.begin_session(peer_account, ttl=10000)
        self.store.select_character(peer_account, peer_generation, peer_identity)
        result = cancel(
            self.store, fixture["registry"], selected, checkpoint_writer=writer
        )
        self.assertEqual(shared.participants[peer_account].generation, peer_generation)
        self.assertEqual(set(result["exits"]), set(fixture["ids"]))
        self.assertFalse(fixture["registry"].fights)
        for member in (identity, *fixture["heroes"]):
            self.assertEqual(
                self.store.character(account, member)["hp"], fixture["expected"][member]
            )
