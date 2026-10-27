"""Source-qualified helper placement and its real PostgreSQL freeze boundary."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from postgres_case import PostgresCase
from wakfu_server.combat_encounter_scene_helpers import (
    SCHEMA,
    SPIRIT_POLICY,
    canonical_digest,
)
from wakfu_server.combat_placement_cells import generate
from wakfu_server.combat_placement_policy import freeze, partition_scene_helper_seeds


def helper_arena(account_id=4, character_id=9):
    cells = {(x, y, 0) for x in range(8) for y in range(4)}
    edges = {
        (a, b) for a in cells for b in cells if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
    }
    raw = [(7, 3, 0), (6, 3, 0), (5, 3, 0)]
    destinations = [(7, 3, 0), (0, 1, 0), (1, 1, 0)]
    source = dict(
        schema=SCHEMA,
        policy=SPIRIT_POLICY,
        version=1,
        authority="explicit_source_backed_wakemu_reconstruction",
        map_id=1134,
        instance_id=0,
        account_id=account_id,
        principal_id=character_id,
        originals=[dict(id=-700, reference=5848, position=list(raw[0]))],
        helpers=[
            dict(
                actor_id=-701,
                reference=5849,
                level=96,
                team_role="player",
                controller_role="principal",
                initial_position=list(raw[1]),
            ),
            dict(
                actor_id=-702,
                reference=5850,
                level=96,
                team_role="player",
                controller_role="principal",
                initial_position=list(raw[2]),
            ),
        ],
    )
    from wakfu_server.combat_wire import arena
    from wakfu_server.combat_encounter_roles import EncounterRoles, ORDINARY_POLICY

    result = arena(
        1134,
        character_id,
        sorted(cells),
        {0: {(0, 0, 0), *destinations[1:]}, 1: {destinations[0]}},
    )
    result.update(
        validated_cells=cells,
        valid_edges=edges,
        native_encounter_roles=EncounterRoles(
            ORDINARY_POLICY,
            "ordinary-existing-constructor-role-policy",
            1134,
            (5848, 5849, 5850),
            0,
            1,
        ).record(),
        native_encounter_scene_helpers=dict(
            source=source, source_digest=canonical_digest(source)
        ),
        native_encounter_scene_helper_seed_order=[-700, -701, -702],
        native_encounter_scene_helper_seed_positions=[list(cell) for cell in raw],
        participant_positions=[
            [list(start), list(end)] for start, end in zip(raw, destinations)
        ],
    )
    return result, {0: [(0, 0, 0)], 1: raw}, destinations


class SceneHelperPlacementTests(unittest.TestCase):
    def test_relocated_helpers_keep_player_side_and_six_human_slots(self):
        arena, raw, destinations = helper_arena()
        seeds, count = partition_scene_helper_seeds(
            arena,
            {0: raw[0], 1: destinations},
            original_npc_seeds=raw[1],
            map_id=1134,
            instance_id=0,
            account_id=4,
            character_id=9,
        )
        self.assertEqual(count, 2)
        self.assertEqual(set(seeds[0]), {(0, 0, 0), *destinations[1:]})
        self.assertEqual(seeds[1], [destinations[0]])
        placement = generate(
            arena["validated_cells"],
            arena["valid_edges"],
            seeds,
            slots_per_team=6,
            team_capacities={0: 8, 1: 6},
        )
        self.assertEqual((len(placement[0]), len(placement[1])), (8, 6))
        self.assertTrue(set(destinations[1:]) <= placement[0])
        self.assertFalse(placement[0] & placement[1])

    def test_foreign_or_reordered_source_proofs_are_rejected(self):
        arena, raw, destinations = helper_arena()
        for mutate in (
            lambda a: a.update(
                native_encounter_scene_helper_seed_order=[-701, -700, -702]
            ),
            lambda a: a["native_encounter_scene_helper_seed_positions"][0].__setitem__(
                0, 2
            ),
            lambda a: a["native_encounter_scene_helper_seed_order"].__setitem__(
                0, -999
            ),
        ):
            changed = deepcopy(arena)
            mutate(changed)
            with self.assertRaises(ValueError):
                partition_scene_helper_seeds(
                    changed,
                    {0: raw[0], 1: destinations},
                    original_npc_seeds=raw[1],
                    map_id=1134,
                    instance_id=0,
                    account_id=4,
                    character_id=9,
                )
        with self.assertRaises(ValueError):
            partition_scene_helper_seeds(
                arena,
                {0: raw[0], 1: destinations},
                original_npc_seeds=raw[1],
                map_id=1134,
                instance_id=1,
                account_id=4,
                character_id=9,
            )

    def test_default_formations_and_capacity_validation_remain_intact(self):
        arena, raw, _destinations = helper_arena()
        first = generate(
            arena["validated_cells"],
            arena["valid_edges"],
            raw,
            slots_per_team=6,
            variation_seed=83,
        )
        same = generate(
            arena["validated_cells"],
            arena["valid_edges"],
            raw,
            slots_per_team=6,
            variation_seed=83,
            team_capacities=None,
        )
        self.assertEqual(first, same)
        for capacities in ({0: 8}, {0: True, 1: 6}, {0: 128, 1: 6}):
            with self.assertRaises(ValueError):
                generate(
                    arena["validated_cells"],
                    arena["valid_edges"],
                    raw,
                    team_capacities=capacities,
                )


class SceneHelperPlacementPostgresTests(PostgresCase):
    def test_actual_freeze_and_restore_keep_friendly_helpers_and_human_capacity(self):
        from wakfu_server.fight_store import create
        from wakfu_server.combat_qi_surfaces import NativeQISurfaces

        account = self.store.register("helper-layout", "local-password")["id"]
        character = self.store.create_character(account, "HelperLayout")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        selected, seeds, destinations = helper_arena(account, character["id"])
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
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{slots_per_team}','6') "
                "WHERE name='fight_placement_policy'"
            )
        identity = create(self.store, account, generation, character["id"])

        def call():
            return freeze(
                self.store,
                account_id=account,
                generation=generation,
                character_id=character["id"],
                fight_id=identity,
                map_id=1134,
                instance_id=0,
                selected_arena=selected,
                seeds=seeds,
            )

        with patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
            return_value=surfaces,
        ), patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
            return_value=dict(
                map_id=1134,
                source_sha256="a" * 64,
                output_sha256="b" * 64,
                manifest_sha256="c" * 64,
            ),
        ), patch(
            "wakfu_server.combat_border_policy.choose", return_value=None
        ):
            result = call()
            self.assertEqual(
                tuple(len(result["placement_cells"][team]) for team in (0, 1)), (8, 6)
            )
            self.assertTrue(set(destinations[1:]) <= result["placement_cells"][0])
            self.assertIn(destinations[0], result["placement_cells"][1])
            with self.store.connection() as db:
                record = db.execute(
                    "SELECT layout FROM fight_placement_layouts WHERE fight_id=%s",
                    (identity,),
                ).fetchone()["layout"]
                self.assertEqual(
                    record["native_encounter_scene_helper_seed_order"],
                    [-700, -701, -702],
                )
                self.assertEqual(
                    record["native_encounter_scene_helpers"],
                    selected["native_encounter_scene_helpers"],
                )
                db.execute(
                    "UPDATE settings SET value=jsonb_set(value,'{slots_per_team}','2') "
                    "WHERE name='fight_placement_policy'"
                )
            restored = call()
            self.assertEqual(restored["placement_cells"], result["placement_cells"])
            self.assertEqual(
                restored["native_encounter_scene_helper_seed_positions"],
                selected["native_encounter_scene_helper_seed_positions"],
            )


if __name__ == "__main__":
    unittest.main()
