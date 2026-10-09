"""Temporary solo dungeon ownership disappears only after an owned return."""
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
import test_dungeon_auto_exit as auto_fixture
from wakfu_server import dungeon_instances, player_parties
from wakfu_server.maps import dungeon_exit
from wakfu_server.maps.dungeon_hydration import prepare_transition
from wakfu_server.maps.dungeon_progression import initialize_run


class SoloDungeonCleanupTests(PostgresCase):
    fixture = auto_fixture.AutomaticDungeonExitPostgresTests
    install_context_policy = fixture.install_context_policy
    player = fixture.player
    make_fight = fixture.make_fight
    bind = fixture.bind
    finish = fixture.finish
    topology = fixture.topology
    final_victory = fixture.final_victory
    complete = fixture.complete

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members = [self.player()]
        actor = self.members[0]
        result = dungeon_instances.create_or_reuse(
            self.store,
            actor["account"],
            actor["generation"],
            actor["character"]["id"],
            "jalato_normal",
            authorize_entry=lambda character, route: True,
        )
        self.party_id = result["party_id"]
        self.instance_id = result["instance_id"]
        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        rooms = tuple(
            SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1086,instance_id=%s,x=4,y=-12,z=0 WHERE id=%s",
                (self.instance_id, actor["character"]["id"]),
            )
            initialize_run(
                db,
                self.instance_id,
                self.party_id,
                SimpleNamespace(
                    roster_ready=True, document_sha256="e" * 64, rooms=rooms
                ),
            )

    def assert_cleaned(self):
        actor = self.members[0]
        self.assertIsNone(
            player_parties.snapshot(
                self.store,
                actor["account"],
                actor["generation"],
                actor["character"]["id"],
            )
        )
        with self.store.connection() as db:
            party = db.execute(
                "SELECT leader_id,dungeon_solo FROM player_parties WHERE id=%s",
                (self.party_id,),
            ).fetchone()
            self.assertEqual(party, {"leader_id": None, "dungeon_solo": True})
            self.assertEqual(
                db.execute(
                    "SELECT party_id FROM dungeon_instances WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone()["party_id"],
                self.party_id,
            )
        events = dungeon_instances.pending_transitions(
            self.store, actor["account"], actor["generation"], actor["character"]["id"]
        )
        self.assertEqual(events[-1]["transition_kind"], "exit")
        plan = prepare_transition(
            self.store,
            actor["account"],
            actor["generation"],
            actor["character"]["id"],
            events[-1],
        )
        removal = [packet for packet in plan.packets if packet[0] == 1049]
        self.assertEqual(len(removal), 1)
        from wakfu_server.party_wire import removed

        self.assertEqual(removal[0], removed(self.party_id, [actor["character"]["id"]]))

    def test_individual_escape_cleans_temporary_party_and_retains_delivery(self):
        actor = self.members[0]
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, {"topology": self.topology}),
        ):
            result = dungeon_exit.leave_automatic(
                self.store,
                actor["account"],
                actor["generation"],
                actor["character"]["id"],
                in_fight=lambda identity: False,
            )
        self.assertEqual(result["party_change"]["removed"], [actor["character"]["id"]])
        self.assert_cleaned()

    def test_final_victory_cleans_temporary_party_and_replay_is_safe(self):
        fight, _ = self.final_victory()
        result = self.complete(fight)
        self.assertEqual(result["party_change"]["party_id"], self.party_id)
        self.assert_cleaned()
        self.assertTrue(self.complete(fight)["replay"])

    def test_preexisting_singleton_is_not_cleaned(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE player_parties SET dungeon_solo=false WHERE id=%s",
                (self.party_id,),
            )
        fight, _ = self.final_victory()
        self.assertIsNone(self.complete(fight)["party_change"])
        actor = self.members[0]
        self.assertIsNotNone(
            player_parties.snapshot(
                self.store,
                actor["account"],
                actor["generation"],
                actor["character"]["id"],
            )
        )
        event = dungeon_instances.pending_transitions(
            self.store, actor["account"], actor["generation"], actor["character"]["id"]
        )[-1]
        plan = prepare_transition(
            self.store,
            actor["account"],
            actor["generation"],
            actor["character"]["id"],
            event,
        )
        self.assertFalse(any(packet[0] == 1049 for packet in plan.packets))

    def test_social_expansion_permanently_clears_temporary_origin(self):
        actor, guest = self.members[0], self.player()
        invitation = player_parties.invite(
            self.store,
            actor["account"],
            actor["generation"],
            actor["character"]["id"],
            guest["character"]["id"],
        )
        player_parties.answer(
            self.store,
            guest["account"],
            guest["generation"],
            guest["character"]["id"],
            invitation,
            True,
        )
        with self.store.connection() as db:
            party = db.execute(
                "SELECT dungeon_solo FROM player_parties WHERE id=%s", (self.party_id,)
            ).fetchone()
            self.assertFalse(party["dungeon_solo"])
            self.assertIsNone(player_parties.cleanup_dungeon_solo(db, self.party_id))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (self.party_id,),
                ).fetchone()["n"],
                2,
            )
        fight, _ = self.final_victory()
        self.assertIsNone(self.complete(fight)["party_change"])
        event = dungeon_instances.pending_transitions(
            self.store, actor["account"], actor["generation"], actor["character"]["id"]
        )[-1]
        plan = prepare_transition(
            self.store,
            actor["account"],
            actor["generation"],
            actor["character"]["id"],
            event,
        )
        self.assertFalse(any(packet[0] == 1049 for packet in plan.packets))
