"""Original Boat1115 landing, native egress and ordinary incoming denial."""
import copy
import json
import struct
import unittest
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server import native_boats, native_boat_arrivals
from wakfu_server.movement import Movement


def request(start, targets):
    point = dict(zip(("x", "y", "z"), start))
    steps = []
    for target in targets:
        steps.append(
            {
                "d" + axis: target[i] - point[axis]
                for i, axis in enumerate(("x", "y", "z"))
            }
        )
        point = dict(zip(("x", "y", "z"), target))
    return dict(
        start_position=dict(zip(("x", "y", "z"), start)),
        end_position=point,
        steps=steps,
    )


class NativeBoatArrivalOnlyAuthorityTests(PostgresCase):
    def test_original_link_landing_departures_incoming_replacement_and_rollback(self):
        with self.store.connection() as db:
            authority = native_boat_arrivals.load(db)
            contracts = native_boats.load(db)
        from wakfu_server.storage.native_catalog import _database, release

        with _database().connection() as source_db:
            row = source_db.execute(
                "SELECT raw FROM native_catalog_documents WHERE revision=%s "
                "AND path='combat-maps/843.json'",
                (release(),),
            ).fetchone()
            geometry = json.loads(bytes(row["raw"]))
        self.assertEqual(len(authority), 1)
        source = authority[0]["source"]
        self.assertEqual(source, (-1, 0, 49))
        expected = {(0, 0, 48), (-2, 0, 48), (-1, 1, 48), (-1, -1, 48)}
        self.assertEqual(authority[0]["targets"], expected)
        original_geometry = copy.deepcopy(geometry)
        endpoints = {r["id"]: r for r in contracts["endpoints"]}
        links = {}
        for row in contracts["routes"]:
            links.setdefault(frozenset((row["source"], row["destination"])), []).append(
                row
            )
        account = self.store.register("boat-exact-arrival", "local-password")["id"]
        actor = self.store.create_character(account, "Exact Landing")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=967,instance_id=0,x=9,y=12,z=2 WHERE id=%s",
                (actor["id"],),
            )
        actor = self.store.character(account, actor["id"])
        with patch.object(
            native_boats, "_indexes", return_value=(endpoints, links)
        ), patch.object(native_boat_arrivals, "_authority", return_value=authority):
            result = native_boats.resolve(
                actor,
                struct.pack(">qq", 35192, 35193),
                source_allowed=lambda a, o: native_boats.admit_source(
                    self.store, account, generation, a, o
                ),
                geometry=lambda _map: geometry,
            )
            self.assertEqual(result["native_link_id"], 1115)
            self.assertEqual(
                result["destination"], dict(map_id=843, instance_id=0, x=-1, y=0, z=49)
            )
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                with self.store.connection() as db:
                    self.store.transition_map_in_transaction(
                        db,
                        account,
                        generation,
                        actor["id"],
                        actor,
                        result["destination"],
                    )
                    raise RuntimeError("rollback")
            self.assertEqual(self.store.character(account, actor["id"])["map_id"], 967)
            landed = self.store.transition_map(
                account, generation, actor["id"], actor, result["destination"]
            )
            owned_position = {axis: landed[axis] for axis in ("x", "y", "z")}
            state = Movement(owned_position)
            for target in sorted(expected):
                move = request(source, [target])
                approved = state.validate(move)
                native_boat_arrivals.validate_movement(
                    landed, move, geometry=lambda _: geometry
                )
                self.assertIn(target, approved)
            # Same source is a legitimate approved replacement start while the
            # previous route animates; incoming traversal remains forbidden.
            state.commit(state.validate(request(source, [(0, 0, 48)])))
            replacement = request(source, [(-2, 0, 48)])
            native_boat_arrivals.validate_movement(
                landed, replacement, geometry=lambda _: geometry
            )
            state.validate(replacement)
            with self.assertRaisesRegex(
                ValueError, "not an ordinary movement destination"
            ):
                incoming = request((0, 0, 48), [source])
                state.validate(incoming)
                native_boat_arrivals.validate_movement(
                    landed, incoming, geometry=lambda _: geometry
                )
            with self.assertRaisesRegex(ValueError, "original native Boat departure"):
                native_boat_arrivals.validate_movement(
                    landed, request(source, [(1, 0, 48)]), geometry=lambda _: geometry
                )
            saved = self.store.move(
                account, generation, landed["id"], owned_position, dict(x=0, y=0, z=48)
            )
            self.assertEqual(
                (saved["map_id"], saved["x"], saved["y"], saved["z"]), (843, 0, 0, 48)
            )
            self.assertNotIn(source, {tuple(p) for p in geometry["cells"]})
            self.assertFalse(any(tuple(to) == source for _, to in geometry["edges"]))
            self.assertEqual(geometry, original_geometry)
        with self.store.connection() as db:
            original = db.execute(
                "SELECT value FROM settings WHERE name=%s",
                (native_boat_arrivals.SETTING,),
            ).fetchone()["value"]
            for field, bad in [
                ("surface_count", 2),
                ("source", [-1, 0, 48]),
                ("endpoint_sha256", "0" * 64),
            ]:
                changed = copy.deepcopy(original)
                changed["arrivals"][0][field] = bad
                with db.transaction():
                    db.execute(
                        "UPDATE settings SET value=%s::jsonb WHERE name=%s",
                        (json.dumps(changed), native_boat_arrivals.SETTING),
                    )
                    with self.assertRaises(ValueError):
                        native_boat_arrivals.load(db)
                    db.execute(
                        "UPDATE settings SET value=%s::jsonb WHERE name=%s",
                        (json.dumps(original), native_boat_arrivals.SETTING),
                    )


class NativeBoatArrivalUnchangedScopeTests(unittest.TestCase):
    def test_other_map_does_not_load_terrain_and_unknown_endpoint_does_not_gain_arrival(
        self,
    ):
        entry = dict(
            map_id=843,
            endpoint_id=35193,
            source=(-1, 0, 49),
            targets=frozenset({(0, 0, 48)}),
        )
        with patch.object(native_boat_arrivals, "_authority", return_value=(entry,)):
            native_boat_arrivals.validate_movement(
                dict(map_id=504, instance_id=0),
                request((4, 3, 9), [(4, 2, 9)]),
                geometry=lambda _: self.fail("Other map must not load terrain"),
            )
            self.assertIsNone(native_boat_arrivals.arrival(dict(id=14697), {}))
