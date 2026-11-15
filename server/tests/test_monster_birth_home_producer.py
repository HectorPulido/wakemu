"""World preserves explicit Rust-owned birth provenance and actor state.

Home selection, wandering and offspring destination fencing execute in the real
Rust cases in tests/idle_planner_contract.rs; no Python planner is retained.
"""

from psycopg import Error
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.monster_maturation import STAGES
from wakfu_server.planting_context import region


class BirthHomeProducerTests(PostgresCase):
    HOME = 62201

    def frozen_home(self, reference, identity, group_id):
        groups = PersistentGroups(self.store)
        member = owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            identity,
            map_id=546,
            x=-44,
            y=16,
            z=0,
        )
        key = groups.register(546, 0, group_id, [member])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_group_birth_homes "
                "(map_id,instance_id,group_id,region_id,source_kind,source_key,anchor) "
                "VALUES(546,0,%s,%s,'reproduction_birth','rust-frozen-birth',%s)",
                (group_id, self.HOME, Jsonb([-44, 16, 0])),
            )
        return groups, key, member

    def test_world_preserves_frozen_foreign_family_birth_home_during_native_movement(
        self,
    ):
        family = STAGES[41][0]["family_id"]
        self.assertNotIn(
            family,
            {row["family_id"] for row in region(546, self.HOME)["monster_families"]},
        )
        groups, key, member = self.frozen_home(41, -9201, 9201)
        moved = dict(member, y=17)
        self.assertTrue(groups.move_members(key, [member], [moved]))
        with self.store.connection() as db:
            home = db.execute(
                "SELECT * FROM monster_group_birth_homes WHERE group_id=9201"
            ).fetchone()
            current = db.execute(
                "SELECT members FROM combat_groups WHERE group_id=9201"
            ).fetchone()["members"]
        self.assertEqual(home["region_id"], self.HOME)
        self.assertEqual(home["source_key"], "rust-frozen-birth")
        self.assertEqual(current, [moved])
        self.assertEqual(
            {k: v for k, v in current[0].items() if k not in ("x", "y", "z")},
            {k: v for k, v in member.items() if k not in ("x", "y", "z")},
        )

    def test_world_cannot_rewrite_frozen_offspring_home_provenance(self):
        _, _, member = self.frozen_home(2, -1125900015900000, 9202)
        with self.assertRaisesRegex(Error, "immutable"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE monster_group_birth_homes SET region_id=62202 WHERE group_id=9202"
                )
        with self.store.connection() as db:
            home = db.execute(
                "SELECT region_id,anchor FROM monster_group_birth_homes WHERE group_id=9202"
            ).fetchone()
            current = db.execute(
                "SELECT members FROM combat_groups WHERE group_id=9202"
            ).fetchone()["members"]
        self.assertEqual(home["region_id"], self.HOME)
        self.assertEqual(home["anchor"], [-44, 16, 0])
        self.assertEqual(current, [member])
