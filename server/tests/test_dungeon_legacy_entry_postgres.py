"""Two-player entry respects native legacy templates and empty criteria."""
import struct
from unittest.mock import patch
from postgres_case import PostgresCase
from test_dungeon_progression import DungeonProgressionPostgresTests as Fixture
from wakfu_server import dungeon_instances, dungeon_transport, generic_transports
from wakfu_server.maps import dungeon_criteria


class LegacyDungeonEntryPostgresTests(PostgresCase):
    player = Fixture.player
    party = Fixture.party

    def test_empty_legacy_criterion_enters_with_both_party_members(self):
        self.store.clock = lambda: 2_000_000_000.0
        self.members, party_id = self.party(2)
        # A real native legacy destination; fixture registers its private run ID.
        source = next(
            s
            for s in generic_transports._CATALOG
            for d in s["destinations"]
            if d["map_id"] != s["map_id"]
            and d["map_id"] <= 32767
            and d["cyZ"] == -1
            and not d["criterion"].strip()
            and d["native_altitude_walkable"]
            and not d["cyX"]
            and not (d["cyW"] > 0 and d["item_reference"] > 0)
        )
        destination = next(
            d
            for d in source["destinations"]
            if d["map_id"] != source["map_id"]
            and d["map_id"] <= 32767
            and d["cyZ"] == -1
            and not d["criterion"].strip()
            and d["native_altitude_walkable"]
            and not d["cyX"]
            and not (d["cyW"] > 0 and d["item_reference"] > 0)
        )
        map_id = destination["map_id"]
        raw = dict(
            key="legacy-test",
            definition_id=1000000 + map_id,
            template_id=1000000 + map_id,
            entry_map_id=source["map_id"],
            entry_object_id=source["id"],
            destination_id=destination["destination_id"],
            start_map_id=map_id,
            criterion="",
            registration_policy="local_legacy_map_registry",
            native_definition_id=None,
            native_template_id=-1,
            native_localization_key=f"content.77.{map_id}",
        )
        routes = dungeon_instances._load_routes([raw])
        route = routes["legacy-test"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_context_policy_versions(route_key,policy_version,template_id,definition_id,max_level,min_level,difficulty_level,is_difficulty_available,can_increase_difficulty,is_competitive_cancelled,allowed_ids,provenance) VALUES(%s,1,%s,%s,0,0,2,false,false,false,'{}','synthetic entry test')",
                (route.key, route.template_id, route.definition_id),
            )
            db.execute(
                "INSERT INTO dungeon_context_active_policies VALUES(%s,1)", (route.key,)
            )
            for member in self.members:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        source["map_id"],
                        source["x"],
                        source["y"],
                        source["z"],
                        member["character"]["id"],
                    ),
                )
        leader = self.members[0]
        body = struct.pack(">qiBi", source["id"], destination["destination_id"], 0, 2)
        observed = []

        def criterion_allowed(actor, criterion):
            observed.append(actor)
            return dungeon_criteria.evaluate(self.store, criterion, character=actor)

        with patch.object(dungeon_instances, "_ROUTES", routes):
            entered = dungeon_transport.enter(
                self.store,
                leader["account"],
                leader["generation"],
                leader["character"]["id"],
                source["map_id"],
                body,
                source_allowed=lambda actor, native_source: True,
                criterion_allowed=criterion_allowed,
            )
        self.assertEqual(entered["party_id"], party_id)
        self.assertEqual(observed[0]["level"], leader["character"]["level"])
        self.assertIsInstance(observed[0]["inventory_items"], list)
        for member in self.members:
            saved = self.store.character(member["account"], member["character"]["id"])
            self.assertEqual(
                (saved["map_id"], saved["instance_id"]),
                (map_id, entered["instance_id"]),
            )
