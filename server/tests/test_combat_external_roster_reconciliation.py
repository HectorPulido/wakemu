"""Native external contexts need incremental joins and actor-replacement repair."""
import struct
import unittest
from types import SimpleNamespace

from test_combat_external_markers import sample_shared
from wakfu_server.combat.combat_external_markers import (
    ExternalFightMarkers,
    MarkerPublications,
)
from wakfu_server.combat_multiplayer_wire import added, decode_added, decode_external
from wakfu_server.combat_actor import actor_stats, actor_effects
from wakfu_server.combat_public_fighter_stats import public_player_fighter_stats


def frame(opcode, body):
    return struct.pack(">IH", len(body) + 6, opcode) + body


class ExternalRosterReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.markers = ExternalFightMarkers()
        self.shared = sample_shared()
        self.shared.fight.actors[17].controlled = True
        self.cursor = MarkerPublications()
        self.scope = (9, "lease", 42, 1134, 0)
        self.full_stats = {}
        self.update()
        self.write(self.markers.world_snapshots(1134, 0))

    def packet(self, actor, source_fight=None):
        char = dict(
            id=actor.id,
            account_id=9,
            level=1,
            breed=8,
            hp=41,
            max_hp=60,
            x=-12,
            y=-8,
            z=-1,
            map_id=1134,
        )
        full = actor_stats(char, self.shared.fight.id, team=actor.team, wp=6)
        self.full_stats[actor.id] = full
        public = public_player_fighter_stats(
            full, actor_id=actor.id, fight_id=self.shared.fight.id
        )
        return added(
            self.shared.fight.id,
            actor.id,
            actor_type=0,
            team=actor.team,
            stats=public,
            effects=actor_effects(),
        )

    def update(self):
        return self.markers.update(
            self.shared, now_ms=100000, now_monotonic=100.0, member_packet=self.packet
        )

    def write(self, packets):
        self.cursor.after_write(b"".join(frame(*p) for p in packets), self.scope)

    def reconcile(self):
        return self.markers.world_snapshots(
            1134,
            0,
            exclude_character_id=42,
            known_phases=self.cursor.snapshot(self.scope),
            known_rosters=self.cursor.roster_snapshot(self.scope),
            unbound_members=self.cursor.unbound_snapshot(self.scope),
        )

    def join(self, identity=31):
        self.shared.fight.actors[identity] = SimpleNamespace(
            id=identity, team=0, controlled=True
        )
        self.shared.participants[2] = SimpleNamespace(
            character_id=identity, generation="joined"
        )
        self.assertIsNone(self.update())

    def test_existing_outside_context_gets_newcomer_without_recreation_or_xp(self):
        self.join()
        packets = self.reconcile()
        self.assertEqual([p[0] for p in packets], [13091])
        member = decode_added(packets[0][1])
        self.assertEqual(
            (member["fight_id"], member["actor_id"], member["team"]), (53, 31, 0)
        )
        self.assertEqual(member["stats"], b"\x02" + self.full_stats[31][9:])
        self.assertEqual(member["effects"], actor_effects())
        self.assertIsNone(member["controller"])
        self.write(packets)
        self.assertEqual(self.reconcile(), ())

    def test_fresh_context_already_with_newcomer_does_not_receive_duplicate_add(self):
        self.join()
        self.cursor.reset(self.scope)
        packets = self.reconcile()
        self.assertEqual([p[0] for p in packets], [12608, 13753])
        self.assertIn((31, 0), decode_external(packets[1][1])["teams"])
        self.write(packets)
        self.assertEqual(self.reconcile(), ())

    def test_successful_world_player_replacement_forces_existing_starter_rebind(self):
        # The ctE record envelope is sufficient for tracking identity. Its
        # entity bytes remain opaque here; native cgN proof validates replacement.
        entity = b"opaque-current-world-entity"
        body = b"\x00\x01" + struct.pack(">BqH", 0, 17, len(entity)) + entity
        self.write(((12608, body),))
        self.assertEqual(
            self.cursor.unbound_snapshot(self.scope), {53: frozenset({17})}
        )
        packets = self.reconcile()
        self.assertEqual([p[0] for p in packets], [13091])
        self.assertEqual(decode_added(packets[0][1])["actor_id"], 17)
        self.write(packets)
        self.assertEqual(self.reconcile(), ())

    def test_missed_join_during_spectating_and_world_replacement_reconcile_together(
        self,
    ):
        self.join()
        entity = b"opaque-current-world-entity"
        self.write(
            ((12608, b"\x00\x01" + struct.pack(">BqH", 0, 17, len(entity)) + entity),)
        )
        self.shared.fight.phase = "active"
        self.update()
        packets = self.reconcile()
        self.assertEqual([p[0] for p in packets], [13091, 13091, 12233])
        self.assertEqual(
            [decode_added(p[1])["actor_id"] for p in packets[:2]], [17, 31]
        )
        self.write(packets)
        self.assertEqual(self.reconcile(), ())

    def test_failed_public_serializer_keeps_prior_marker_available_for_retry(self):
        old = self.markers.markers[53]
        self.shared.fight.actors[31] = SimpleNamespace(id=31, team=0, controlled=True)

        def fail(_actor, _fight):
            raise ValueError("native public actor source unavailable")

        with self.assertRaises(ValueError):
            self.markers.update(self.shared, member_packet=fail)
        self.assertIs(self.markers.markers[53], old)
        self.assertNotIn(31, dict(decode_external(old.body)["teams"]))
        self.update()
        self.assertEqual([p[0] for p in self.reconcile()], [13091])

    def test_actual_publisher_targets_only_known_missing_outside_recipient(self):
        import ast
        from pathlib import Path
        from threading import RLock

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        publisher = next(
            n
            for n in ast.walk(ast.parse(source.read_text()))
            if isinstance(n, ast.FunctionDef) and n.name == "publish_external_marker"
        )
        sent = []

        def peer(character, known):
            cursor = MarkerPublications()
            scope = (9, "lease", character, 1134, 0)
            if known:
                cursor.after_write(
                    b"".join(frame(*p) for p in self.markers.world_snapshots(1134, 0)),
                    scope,
                )
            return SimpleNamespace(
                write_lock=RLock(),
                marker_publications=cursor,
                native_instance_scope=lambda: scope,
                actor_id=character,
            )

        missing = peer(42, True)
        self.join()
        fresh = peer(43, True)
        owner = peer(31, True)
        observer = peer(88, True)
        private = peer(44, True)
        bad = peer(45, True)
        bad.trace_id = "bad-recipient-known-team"
        bad.marker_publications.rosters[53][17] = 1

        def deliver(target, packets):
            packets = tuple(packets)
            if packets:
                sent.append((target.actor_id, packets))
                target.marker_publications.after_write(
                    b"".join(frame(*p) for p in packets), target.native_instance_scope()
                )
            return True

        players = {
            p.actor_id: (
                "lease",
                p,
                dict(id=p.actor_id, map_id=1134, instance_id=8 if p is private else 0),
            )
            for p in (bad, missing, fresh, owner, observer, private)
        }
        self.shared.participants[2].generation = "lease"
        for actor in self.shared.fight.actors.values():
            actor.owner_id = 9
        records = []
        namespace = dict(
            COMBAT_TEST=True,
            EXTERNAL_FIGHT_MARKERS=self.markers,
            STORE=SimpleNamespace(
                character=lambda owner, identity: dict(id=identity, account_id=owner)
            ),
            SPECTATORS=SimpleNamespace(
                sessions=lambda fid: (
                    SimpleNamespace(character_id=88, generation="lease"),
                )
            ),
            WORLD=SimpleNamespace(lock=RLock(), players=players, _send_batch=deliver),
            record=lambda **kw: records.append(kw),
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=[publisher], type_ignores=[])
                ),
                str(source),
                "exec",
            ),
            namespace,
        )
        from unittest.mock import patch

        with patch(
            "wakfu_server.combat_actor.actual_actor_stats",
            side_effect=lambda source, actor, fid, **kw: self.full_stats[actor.id],
        ), patch("wakfu_server.breed_resources.live_wp", return_value=(6, 6)):
            namespace["publish_external_marker"](self.shared)
        self.assertEqual([actor for actor, packets in sent], [42])
        self.assertEqual([p[0] for p in sent[0][1]], [13091])
        self.assertEqual(records[0]["event"], "combat_external_marker_recipient_failed")
        self.assertEqual(records[0]["target_connection_id"], "bad-recipient-known-team")
        self.assertIn("team transition", records[0]["reason"])
        with patch(
            "wakfu_server.combat_actor.actual_actor_stats",
            side_effect=lambda source, actor, fid, **kw: self.full_stats[actor.id],
        ), patch("wakfu_server.breed_resources.live_wp", return_value=(6, 6)):
            namespace["publish_external_marker"](self.shared)
        self.assertEqual(len(sent), 1)
        # A phase transition must repair a newly changed roster before the
        # existing uniform12233 delivery in this SAME publisher call.
        actor = SimpleNamespace(id=32, team=0, controlled=True, owner_id=9)
        self.shared.fight.actors[32] = actor
        self.packet(actor)
        self.shared.participants[3] = SimpleNamespace(
            character_id=32, generation="lease"
        )
        self.shared.fight.phase = "active"

        def broadcast(map_id, instance_id, packets, *, exclude_sessions):
            count = 0
            for lease, target, character in players.values():
                if (character["map_id"], character["instance_id"]) == (
                    map_id,
                    instance_id,
                ) and (character["id"], lease) not in exclude_sessions:
                    deliver(target, packets)
                    count += 1
            return count

        namespace["WORLD"].emit_location_batch = broadcast
        with patch(
            "wakfu_server.combat_actor.actual_actor_stats",
            side_effect=lambda source, actor, fid, **kw: self.full_stats[actor.id],
        ), patch("wakfu_server.breed_resources.live_wp", return_value=(6, 6)):
            namespace["publish_external_marker"](self.shared)
        for identity, expected in ((42, [13091, 13091, 12233]), (43, [13091, 12233])):
            opcodes = [
                opcode
                for target, packets in sent
                if target == identity
                for opcode, body in packets
            ]
            self.assertEqual(opcodes, expected)
        self.assertEqual(
            [
                opcode
                for target, packets in sent
                if target == 45
                for opcode, body in packets
            ],
            [12233],
        )

    def test_default_update_does_not_reuse_old_member_packet_as_current_proof(self):
        self.join()
        self.markers.update(self.shared)
        self.assertEqual(self.markers.markers[53].member_packets, ())
        with self.assertRaisesRegex(ValueError, "public member packet is unavailable"):
            self.reconcile()
        self.update()
        self.assertEqual([p[0] for p in self.reconcile()], [13091])

    def test_world_actor_publication_conservatively_invalidates_known_member_identity(
        self,
    ):
        entity = b"opaque-current-world-entity"
        for flag in (0, 1):
            body = bytes((flag, 1)) + struct.pack(">BqH", 0, 17, len(entity)) + entity
            self.write(((12608, body),))
            self.assertEqual(
                [decode_added(p[1])["actor_id"] for p in self.reconcile()], [17]
            )
            self.write(self.reconcile())
            self.assertEqual(self.reconcile(), ())
