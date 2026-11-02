"""Owned high-ID admission regression; PostgreSQL writes use isolated schemas only."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from test_combat_placement_policy import PlacementPolicyTests
from wakfu_server.combat_wire import arena, topology, decode_topology
from wakfu_server.fight_store import create
from wakfu_server.combat_placement_policy import freeze


class TopologyIdentityTests(PlacementPolicyTests):
    def setUp(self):
        super().setUp()
        # Native arena preparation includes team placement cells. This flat
        # fixture has no ordinary-party reservation or NPC footprint override.
        self.arena["placement_cells"] = self.seeds

    def use_high_character(self):
        with self.store.connection() as db:
            db.execute("ALTER TABLE characters ALTER COLUMN id RESTART WITH 32768")
        self.character = self.store.create_character(self.account, "Highidentity")
        self.assertEqual(self.character["id"], 32768)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.arena = arena(1134, self.character["id"], sorted(self.cells), self.seeds)
        self.arena.update(
            validated_cells=self.cells,
            valid_edges=self.edges,
            placement_cells=self.seeds,
        )

    def test_owned_high_character_serializes_and_reopens_without_actor_remap(self):
        self.use_high_character()
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        admitted = self.call(fight_id)
        decoded = decode_topology(topology(admitted))
        self.assertGreaterEqual(decoded["instance_id"], 1)
        self.assertLessEqual(decoded["instance_id"], 32767)
        self.assertEqual(self.call(fight_id, self.reopen()), admitted)
        with self.store.connection() as db:
            actor = db.execute(
                "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()
        self.assertEqual(actor["character_id"], 32768)

    def test_duel_high_fight_identity_serializes_in_common_admission(self):
        with self.store.connection() as db:
            db.execute("ALTER TABLE combat_fights ALTER COLUMN id RESTART WITH 32768")
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.assertEqual(fight_id, 32768)
        # The consented duel producer supplies fight_id, whereas PvE supplies
        # character.id; both enter this same authorized placement transaction.
        self.arena["instance_id"] = fight_id
        admitted = self.call(fight_id)
        self.assertLessEqual(decode_topology(topology(admitted))["instance_id"], 32767)

    def test_distinct_owners_allocate_without_alias_and_release_terminal_lease(self):
        other_account = self.store.register("other-layout-owner", "local-password")[
            "id"
        ]
        other = self.store.create_character(other_account, "Otherlayout")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        owners = [
            (self.account, self.generation, self.character["id"]),
            (other_account, other_generation, other["id"]),
        ]
        fights = [create(self.store, *owner) for owner in owners]
        gate = Barrier(2)

        def admit(index):
            gate.wait(timeout=10)
            account, generation, character = owners[index]
            return freeze(
                self.store,
                account_id=account,
                generation=generation,
                character_id=character,
                fight_id=fights[index],
                map_id=1134,
                instance_id=0,
                selected_arena=dict(self.arena, instance_id=17),
                seeds=self.seeds,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            admitted = list(pool.map(admit, (0, 1)))
        identities = [decode_topology(topology(a))["instance_id"] for a in admitted]
        self.assertEqual(len(set(identities)), 2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fights[0],)
            )
            scopes = db.execute(
                "SELECT instance_id FROM fight_placement_layouts"
            ).fetchall()
        self.assertEqual({r["instance_id"] for r in scopes}, {0})
        self.arena["instance_id"] = identities[0]
        third = create(self.store, *owners[0])
        self.assertEqual(self.call(third)["instance_id"], identities[0])

    def test_oversized_committed_layout_recovers_without_changing_terrain(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        admitted = self.call(fight_id)
        with self.store.connection() as db:
            db.execute(
                "UPDATE fight_placement_layouts SET layout=jsonb_set(layout, "
                "'{wire_instance_id}', '32768'::jsonb) WHERE fight_id=%s",
                (fight_id,),
            )
        recovered = self.call(fight_id, self.reopen())
        topology(recovered)
        self.assertEqual(recovered["validated_cells"], admitted["validated_cells"])
        self.assertEqual(recovered["placement_cells"], admitted["placement_cells"])


def load_tests(loader, tests, pattern):
    # Inheriting the terrain fixture must not rerun unrelated policy cases.
    return unittest.TestSuite(
        TopologyIdentityTests(name)
        for name in (
            "test_owned_high_character_serializes_and_reopens_without_actor_remap",
            "test_duel_high_fight_identity_serializes_in_common_admission",
            "test_distinct_owners_allocate_without_alias_and_release_terminal_lease",
            "test_oversized_committed_layout_recovers_without_changing_terrain",
        )
    )


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(load_tests(None, None, None))
    raise SystemExit(not result.wasSuccessful())
