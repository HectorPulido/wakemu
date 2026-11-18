"""Real SQL/NativeSpatial proof for an already earned room key and its gate."""

from collections import defaultdict, deque
from copy import deepcopy
import json
from pathlib import Path
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics as mechanics
from wakfu_server.application import owned_story_dispatch as dispatch
from wakfu_server.achievements import storage

ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"


class OwnedStoryRegistryPostgresTests(PostgresCase):
    def test_earned_key_gate_collision_packets_position_reconnect_and_effect_rollback(
        self,
    ):
        from wakfu_server import dungeon_runtime_config
        from wakfu_server.position_buffer import Positions

        account = self.store.register("story-native-gate", "isolated-test-password")[
            "id"
        ]
        actor = self.store.create_character(account, "Story Native Gate")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        selected = json.loads((ROOT / "astrub-temple-887.json").read_text())
        walking = json.loads((ROOT / "astrub-temple-887.exploration.json").read_text())
        configuration = dict(
            topology=dict(
                asset_map_id=887,
                policy=controller.SCHEMA,
                owned_story_controller=selected,
                exploration_geometry=walking,
                rooms=[],
                doors=[],
            )
        )
        with self.store.connection() as db:
            party = db.execute(
                "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                (actor["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (actor["id"], party),
            )
            instance = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,"
                "entry_map_id,entry_object_id,entry_destination_id,start_map_id) VALUES(%s,1,%s,887,887,747,23621,4029,887) RETURNING instance_id",
                (party, actor["id"]),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) "
                "VALUES(%s,%s,%s,%s,1,'leader')",
                (instance, party, actor["id"], generation),
            )
            db.execute(
                "UPDATE characters SET map_id=887,instance_id=%s,x=-4,y=-7,z=0 WHERE id=%s",
                (instance, actor["id"]),
            )
            # Controlled initial fixture: room1's earlier victory has already
            # settled. The test exercises its real subsequent key/gate actions;
            # it does not claim to be a natural full temple combat playthrough.
            storage.record_event(
                db,
                actor["id"],
                controller._key(selected, instance, "room1-victory"),
                dict(
                    schema=controller.SCHEMA,
                    profile_sha256=controller._digest(selected),
                    owner=actor["id"],
                    instance_id=instance,
                    step="room1-victory",
                    evidence=dict(fixture="previously settled owned room victory"),
                    created_ms=int(self.store.now().timestamp() * 1000),
                ),
            )
        active = {(account, generation, actor["id"])}
        positions = Positions(
            self.store, lease_active=lambda a, g, c: (a, g, c) in active
        )
        source = self.store.character(account, actor["id"])
        positions.attach(account, generation, source)
        with patch.object(
            dungeon_runtime_config, "pinned_configuration", return_value=configuration
        ):
            with positions.account_barrier(account):
                positions.flush(account_id=account)
                key = dispatch.interact(
                    self.store,
                    account,
                    generation,
                    source,
                    struct.pack(">qHH", 23399, 0, 0),
                    loaded=True,
                    blocked=False,
                )
            self.assertTrue(key["applied"])
            with self.store.connection() as db:
                _, steps = controller._scope(db, self.store, key["character"])
            gate = {
                row["object_id"]: row
                for row in controller.presentation_state(selected, steps)
            }[23400]
            self.assertTrue(
                gate["blocks_movement"],
                "Having a key enables the action, not crossing a closed gate",
            )

            def request(path):
                return dict(
                    start_position=dict(zip(("x", "y", "z"), path[0])),
                    end_position=dict(zip(("x", "y", "z"), path[-1])),
                    steps=[
                        dict(zip(("dx", "dy", "dz"), [b[i] - a[i] for i in range(3)]))
                        for a, b in zip(path, path[1:])
                    ],
                )

            adjacency = defaultdict(list)
            for a, b in walking["edges"]:
                adjacency[tuple(a)].append(tuple(b))
            start, goal = (-4, -7, 0), (0, -12, 0)
            queue, previous = deque([start]), {start: None}
            while queue and goal not in previous:
                parent = queue.popleft()
                for point in adjacency[parent]:
                    if point not in previous:
                        previous[point] = parent
                        queue.append(point)
            path = [goal]
            while previous[path[-1]] is not None:
                path.append(previous[path[-1]])
            path.reverse()
            with self.store.connection() as db:
                controller.validate_movement(
                    db, self.store, source, request(path), configuration
                )
            moved = positions.move(
                account, generation, actor["id"], source, dict(x=0, y=-12, z=0)
            )
            positions.flush(account_id=account)
            closed_request = request([(0, -12, 0), (0, -13, 0), (0, -14, 0)])
            with self.store.connection() as db:
                with self.assertRaises(ValueError):
                    controller.validate_movement(
                        db, self.store, moved, closed_request, configuration
                    )
            self.assertEqual(self.store.character(account, actor["id"])["y"], -12)
            with positions.account_barrier(account):
                opened = dispatch.interact(
                    self.store,
                    account,
                    generation,
                    moved,
                    struct.pack(">qHH", 23400, 0, 0),
                    loaded=True,
                    blocked=False,
                )
            self.assertTrue(opened["applied"])
            with self.store.connection() as db:
                controller.validate_movement(
                    db, self.store, opened["character"], closed_request, configuration
                )
            crossed = positions.move(
                account, generation, actor["id"], moved, dict(x=0, y=-14, z=0)
            )
            positions.flush(account_id=account)
            with self.store.connection() as db:
                _, steps = controller._scope(db, self.store, crossed)
                packets = controller.element_packets(selected, steps)
                gate_payload = next(
                    body[10:]
                    for _, body in packets
                    if struct.unpack_from(">q", body)[0] == 23400
                )
                self.assertEqual(struct.unpack_from(">h", gate_payload, 7)[0], 0)
                self.assertEqual((gate_payload[12], gate_payload[13]), (0, 0))
                before = deepcopy(self.store.character(account, actor["id"], db))

                def failed_native_effect(inner_db, inner_store, current, effects):
                    mechanics.move(inner_db, current, [0, -15, 0])
                    raise ValueError("native effect failed after position update")

                with self.assertRaisesRegex(ValueError, "native effect failed"):
                    with db.transaction():
                        controller._settle(
                            db,
                            self.store,
                            deepcopy(before),
                            selected,
                            steps,
                            kind="room_victory",
                            reference=2,
                            evidence=dict(fixture="failure-path-only"),
                            apply_effects=failed_native_effect,
                        )
                after = self.store.character(account, actor["id"], db)
                self.assertEqual(tuple(after[k] for k in ("x", "y", "z")), (0, -14, 0))
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                        (
                            actor["id"],
                            controller._key(selected, instance, "room2-victory"),
                        ),
                    ).fetchone()
                )
        reopened = self.reopen()
        second = Positions(reopened, lease_active=lambda a, g, c: (a, g, c) in active)
        restored = second.attach(
            account, generation, reopened.character(account, actor["id"])
        )
        self.assertEqual(
            tuple(restored[k] for k in ("map_id", "instance_id", "x", "y", "z")),
            (887, instance, 0, -14, 0),
        )
