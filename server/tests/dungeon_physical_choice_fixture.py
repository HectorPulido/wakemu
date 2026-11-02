"""Isolated actual-PG setup for the private139 movement transaction tests.

This establishes a settled prefix as fixture data. It does not claim a played
combat, qualify bomb prerequisites, install public policies or touch live actors.
Run only from PostgresCase with the complete immutable image/native catalog.
"""
import copy
import json
from pathlib import Path

from psycopg.types.json import Jsonb
from test_dungeon_instances import DungeonInstanceTests


class PhysicalChoiceFixture:
    player = DungeonInstanceTests.player
    party = DungeonInstanceTests.party

    def build_choice_fixture(self, count=2):
        from wakfu_server import (
            combat_group_store,
            combat_terrain,
            dungeon_runtime_config,
        )
        from wakfu_server import dungeon_progression, dungeon_runtime
        from wakfu_server.position_buffer import Positions

        self.store.clock = lambda: 2_000_000_000.0
        self.input_fixture = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "dungeon139"
                / "physical-choice.json"
            ).read_text()
        )
        old = self.input_fixture["source_configuration"]
        # A new version belongs only to this disposable schema. It avoids
        # replacing any migration-seeded139 version and is never published.
        self.config = dungeon_runtime_config.prepare_configuration(
            old["compiled_plan"],
            old["topology"],
            old["route"],
            version=9000139,
            provenance=old["provenance"],
            level_policy=old["level_policy"],
        )
        self.geometry = combat_terrain.map_geometry(301)
        self.groups = combat_group_store.PersistentGroups(self.store)
        self.members, self.party_id = self.party(count)
        route = self.config["route"]
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, self.config)
            party = db.execute(
                "SELECT leader_id,revision FROM player_parties WHERE id=%s",
                (self.party_id,),
            ).fetchone()
            self.instance_id = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
                "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
                "start_map_id,context_route_key,context_policy_version) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING instance_id",
                (
                    self.party_id,
                    party["revision"],
                    party["leader_id"],
                    route["template_id"],
                    route["definition_id"],
                    route["entry_map_id"],
                    route["entry_object_id"],
                    route["destination_id"],
                    route["start_map_id"],
                    route["key"],
                    self.config["version"],
                ),
            ).fetchone()["instance_id"]
            for index, member in enumerate(self.members):
                witness = self.input_fixture["physical_selection_witnesses"][index % 2]
                xyz = witness["source_neighbor"]
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                    "session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        self.instance_id,
                        self.party_id,
                        member["character"]["id"],
                        member["generation"],
                        party["revision"],
                        "leader"
                        if member["character"]["id"] == party["leader_id"]
                        else "member",
                    ),
                )
                db.execute(
                    "UPDATE characters SET map_id=301,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (self.instance_id, *xyz, member["character"]["id"]),
                )
            plan = dungeon_runtime_config.plan_from_configuration(self.config)
            dungeon_progression.initialize_run(
                db, self.instance_id, self.party_id, plan
            )
            # Actual first-group registration is performed by production code;
            # no suffix receipt may exist until a physical choice is committed.
            self.prefix_receipt = dungeon_runtime.ensure_current_room(
                db, self.groups, self.instance_id, self.geometry
            )
            if self.prefix_receipt is None:
                raise AssertionError(
                    "Shared first room must be available before selection"
                )
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            result = dict(victory=True, completed=False, current_room=2)
            db.execute(
                "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,"
                "player_team,status,result_revision,result) VALUES(%s,%s,1,0,'victory',2,%s)",
                (fight, self.instance_id, Jsonb(result)),
            )
            db.execute(
                "UPDATE dungeon_room_runs SET current_room=2,revision=2 WHERE instance_id=%s",
                (self.instance_id,),
            )
            self.prefix_encounter = fight
        live = {
            (m["account"], m["generation"], m["character"]["id"]) for m in self.members
        }
        self.live_leases = live
        self.positions = Positions(self.store, lease_active=lambda *key: key in live)
        for member in self.members:
            member["character"] = self.store.character(
                member["account"], member["character"]["id"]
            )
            self.positions.attach(
                member["account"], member["generation"], member["character"]
            )
        self.before_choice = self.choice_snapshot()
        return self

    def choice_snapshot(self):
        with self.store.connection() as db:
            return {
                "run": db.execute(
                    "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone(),
                "receipts": db.execute(
                    "SELECT * FROM dungeon_room_spawn_receipts WHERE instance_id=%s ORDER BY room_order",
                    (self.instance_id,),
                ).fetchall(),
                "encounters": db.execute(
                    "SELECT * FROM dungeon_room_encounters WHERE instance_id=%s ORDER BY fight_id",
                    (self.instance_id,),
                ).fetchall(),
                "characters": db.execute(
                    "SELECT id,map_id,instance_id,x,y,z,direction FROM characters WHERE id=ANY(%s) ORDER BY id",
                    ([m["character"]["id"] for m in self.members],),
                ).fetchall(),
                "buffer": copy.deepcopy(self.positions.entries),
            }

    def move_choice(
        self, member_index=0, path_key=None, *, store=None, generation=None
    ):
        from wakfu_server import dungeon_runtime
        from wakfu_server.dungeon_physical_choice import commit_movement

        member = self.members[member_index]
        if path_key is None:
            path_key = "west" if member_index % 2 == 0 else "east"
        witness = next(
            r
            for r in self.input_fixture["physical_selection_witnesses"]
            if r["path_key"] == path_key
        )
        with self.store.connection() as db:
            _, configuration = dungeon_runtime.configuration_for_instance(
                db, self.instance_id
            )
            progress = db.execute(
                "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
        return commit_movement(
            store or self.store,
            self.positions,
            self.groups,
            member["account"],
            generation or member["generation"],
            member["character"],
            copy.deepcopy(witness["movement"]),
            copy.deepcopy(witness["movement"]["start_position"]),
            geometry=lambda: self.geometry,
            preview_configuration=configuration,
            unlocked_room=progress["current_room"],
        )
