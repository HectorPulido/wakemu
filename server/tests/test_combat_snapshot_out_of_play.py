"""Native OUT_OF_PLAY NPCs never reappear; reversible OFF_PLAY remains visible."""
import unittest
from types import SimpleNamespace

from test_combat_spectator_snapshot import shared_fixture, actor_payload
from wakfu_server.combat_state import Actor
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_spectator_snapshot import current_snapshot
from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap
from wakfu_server.combat_wire import decode_bootstrap
from wakfu_server.combat_shared import Session
from wakfu_server.fight_checkpoint_store import snapshot


class SnapshotOutOfPlayTests(unittest.TestCase):
    def fixture(self):
        fight, shared = shared_fixture()
        victim = Actor(-1125899922923521, 1, (2, 0, 0), 20, 4, 2, 9, 1)
        fight.actors[victim.id] = victim
        fight.walkable.add(victim.position)
        fight.placement[1].add(victim.position)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.ready(1)
        fight.apply_damage(5, victim.id, 20)
        self.assertEqual(fight.phase, "active")
        self.assertEqual(fight.actors[victim.id].hp, 0)
        shared.runtime.turn_deadline = None
        shared.runtime.awaiting_ack = None
        shared.ack = None
        return fight, shared, victim.id

    def test_owned_and_spectator_exclude_irreversible_npc_without_hiding_off_play(self):
        for status in ("OFF_PLAY", "OUT_OF_PLAY"):
            with self.subTest(status=status):
                fight, shared, identity = self.fixture()
                set_global_fighter_status(fight, identity, status)
                before = snapshot(fight)
                serialized = []

                def owned_payload(current, actor, session):
                    serialized.append(actor.id)
                    return actor_payload(current, actor)

                packets = owned_snapshot(
                    fight,
                    shared,
                    Session(1, 5, "reconnect", 1134, 0),
                    actor_payload=owned_payload,
                )
                roster = {
                    row["actor_id"]
                    for row in decode_bootstrap(packets[0][1])["participants"]
                }
                self.assertEqual(identity in roster, status == "OFF_PLAY")
                self.assertEqual(identity in serialized, status == "OFF_PLAY")
                spectator = current_snapshot(
                    fight, shared, actor_payload=actor_payload, deadline_ms=123456
                )
                observed = {
                    row["actor_id"]
                    for row in decode_spectator_bootstrap(spectator[0][1])[
                        "participants"
                    ]
                }
                self.assertEqual(observed, roster)
                self.assertEqual(snapshot(fight), before)

    def test_missing_native_fighter_status_rejects_instead_of_using_hp(self):
        fight, shared, identity = self.fixture()
        del fight.native_global_pv_collections["fighter_status"][str(identity)]
        with self.assertRaisesRegex(ValueError, "fighter status"):
            current_snapshot(
                fight, shared, actor_payload=actor_payload, deadline_ms=123456
            )
