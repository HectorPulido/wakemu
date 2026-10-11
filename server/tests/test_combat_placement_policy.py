from postgres_case import PostgresCase
from wakfu_server.combat_placement_policy import freeze
from wakfu_server.fight_store import create
from wakfu_server.combat_wire import arena
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from wakfu_server.combat_qi_surfaces import NativeQISurfaces


class PlacementPolicyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("layout-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Layout")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.cells = {(x, y, 0) for x in range(8) for y in range(4)}
        self.edges = {
            (a, b)
            for a in self.cells
            for b in self.cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        }
        # This database-policy fixture uses synthetic flat terrain; provide an
        # explicit native-shaped catalog rather than consulting map1134 assets.
        surfaces = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=1134,
                source_sha256="a" * 64,
                chunks=[
                    dict(
                        x=0,
                        y=0,
                        width=8,
                        height=4,
                        columns=[[x, y, [[0, 0]]] for x in range(8) for y in range(4)],
                    )
                ],
            ),
            map_id=1134,
            source_sha256="a" * 64,
        )
        surface_patch = patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
            return_value=surfaces,
        )
        provenance_patch = patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
            return_value=dict(
                map_id=1134,
                source_sha256="a" * 64,
                output_sha256="b" * 64,
                manifest_sha256="c" * 64,
            ),
        )
        surface_patch.start()
        self.addCleanup(surface_patch.stop)
        provenance_patch.start()
        self.addCleanup(provenance_patch.stop)
        self.seeds = {0: {(0, 0, 0)}, 1: {(7, 3, 0)}}
        self.arena = arena(1134, self.character["id"], sorted(self.cells), self.seeds)
        self.arena.update(validated_cells=self.cells, valid_edges=self.edges)

    def call(self, fight_id, store=None):
        return freeze(
            store or self.store,
            account_id=self.account,
            generation=self.generation,
            character_id=self.character["id"],
            fight_id=fight_id,
            map_id=1134,
            instance_id=0,
            selected_arena=self.arena,
            seeds=self.seeds,
        )

    def test_policy_change_and_store_reopen_preserve_chosen_layout(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        first = self.call(fight_id)
        self.assertEqual([len(first["placement_cells"][t]) for t in (0, 1)], [12, 12])
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{slots_per_team}','2') WHERE name='fight_placement_policy'"
            )
        self.assertEqual(self.call(fight_id, self.reopen()), first)
        next_fight = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.assertEqual(
            [len(self.call(next_fight)["placement_cells"][t]) for t in (0, 1)], [2, 2]
        )

    def test_invalid_policy_does_not_persist_layout(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{slots_per_team}','0') WHERE name='fight_placement_policy'"
            )
        with self.assertRaisesRegex(ValueError, "capacity"):
            self.call(fight_id)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_placement_layouts"
                ).fetchone()["n"],
                0,
            )

    def test_reconnect_requires_current_lease_even_for_committed_layout(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.call(fight_id)
        next_generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, next_generation, self.character["id"])
        with self.assertRaises(ValueError):
            self.call(fight_id)

    def test_borrowed_transaction_rolls_back_layout_with_encounter_preparation(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        with self.assertRaisesRegex(ValueError, "serializer failed"):
            with self.store.connection() as db:
                freeze(
                    self.store,
                    account_id=self.account,
                    generation=self.generation,
                    character_id=self.character["id"],
                    fight_id=fight_id,
                    map_id=1134,
                    instance_id=0,
                    selected_arena=self.arena,
                    seeds=self.seeds,
                    db=db,
                )
                raise ValueError("serializer failed")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_placement_layouts"
                ).fetchone()["n"],
                0,
            )

    def test_simultaneous_preparation_commits_one_identical_layout(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: self.call(fight_id), range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_placement_layouts WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["n"],
                1,
            )

    def test_border_selection_is_frozen_across_policy_changes_and_reopen(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='fight_border_policy'",
                ('{"version":1,"pool":[48]}',),
            )
        first = self.call(fight_id)
        self.assertEqual(first["terrain_effect_id"], 48)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='fight_border_policy'",
                ('{"version":2,"pool":[46]}',),
            )
        self.assertEqual(self.call(fight_id, self.reopen()), first)
        next_fight = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.assertEqual(self.call(next_fight)["terrain_effect_id"], 46)

    def test_invalid_border_pool_cannot_commit_partial_layout(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='fight_border_policy'",
                ('{"version":1,"pool":[44]}',),
            )
        with self.assertRaises(ValueError):
            self.call(fight_id)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM fight_placement_layouts WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()
            )

    def test_preexisting_layout_without_border_receipt_preserves_original46(self):
        fight_id = create(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.call(fight_id)
        with self.store.connection() as db:
            db.execute(
                "UPDATE fight_placement_layouts SET layout=layout-'border' WHERE fight_id=%s",
                (fight_id,),
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='fight_border_policy'",
                ('{"version":2,"pool":[48]}',),
            )
        self.assertEqual(self.call(fight_id)["terrain_effect_id"], 46)
