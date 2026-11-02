"""Advisory retirement projection preserves corpse and retained-source history."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.bridge import jondo_snapshot
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)
from wakfu_server.combat_ordinary_qi_retirement import SOURCE as QI_RETIREMENT
from wakfu_server.combat_snapshot_actor_visibility import hidden_snapshot_actor_ids


class JondoRetiredProjectionTests(unittest.TestCase):
    def fixture(self):
        def actor(identity, team, position, hp=20):
            return SimpleNamespace(
                id=identity,
                team=team,
                position=position,
                hp=hp,
                max_hp=20,
                ap=6,
                max_ap=6,
                mp=1 if identity == 1 else 3,
                max_mp=3,
                effect_stats={4: 0, 97: 0},
                effect_maxima={4: 0, 92: 0},
                physical_radius=0,
                effective_level=10,
                direction=0,
                controlled=False,
                native_los_height=identity + 2,
                native_obstacle_id=identity,
                turn_count=1,
                state_ledger=SimpleNamespace(entries=[]),
            )

        current = actor(1, 1, (0, 0, 0))
        actors = [
            current,
            actor(2, 0, (3, 0, 2)),
            actor(3, 1, (0, 2, 0)),
            actor(4, 0, (2, 2, 0), hp=0),
            actor(5, 0, (4, 0, 0)),
        ]
        fight = SimpleNamespace(
            id=7,
            current=current,
            actors={a.id: a for a in actors},
            turn_id=1,
            sequence=1,
            native_table_turn=1,
            native_qi_visibility_ignored_slots=[],
            walkable={a.position for a in actors} | {(1, 0, 1), (7, 7, 3)},
            edges={(current.position, (1, 0, 1))},
        )
        # Named property/source seams isolate advisory projection; native
        # lifecycle receipts and their actual validators are not replaced.
        oracle = SimpleNamespace(
            runtime=SimpleNamespace(fight=fight, action_id=1),
            identity="source",
            monsters={},
            factory=lambda *args: (
                SimpleNamespace(native_rail_movement_authority=object()),
                SimpleNamespace(
                    actor_authority=SimpleNamespace(
                        properties=lambda f, a: frozenset({5})
                        if a.id == 5
                        else frozenset(),
                    )
                ),
            ),
            descriptor=lambda *args: dict(map_id=546, ref=1),
            owned_spells=lambda f: {},
        )
        oracle.state_identity = lambda runtime: oracle.identity
        retired = deepcopy(fight.actors[4])
        retired.id = 6
        retired.position = (6, 2, 0)
        retired.native_obstacle_id = -1
        unknown = deepcopy(fight.actors[4])
        unknown.id = 7
        unknown.position = (7, 2, 0)
        unknown.native_obstacle_id = 7
        fight.actors.update({6: retired, 7: unknown})
        fight.walkable.update((retired.position, unknown.position))
        initialize_global_pv_collections(fight, tuple(fight.actors))
        set_global_fighter_status(fight, 4, "OFF_PLAY")
        set_global_fighter_status(fight, 6, "OUT_OF_PLAY")
        fight.events = [
            dict(kind="damage", source_id=1, target_id=6, hp=0, sequence=1),
            dict(kind="death", actor_id=6, sequence=2),
        ]
        receipt = dict(source=QI_RETIREMENT, actor_id=6, qi_slot=6)
        retired.native_ordinary_qi_retirement = receipt
        fight.native_ordinary_qi_retirements = {"6": receipt}
        fight.native_owned_group_effects = {
            99: dict(
                uid=99,
                invocation=dict(caster_id=6),
                payload="retired-source-clock-preserved",
            ),
        }
        return oracle

    def build(self, oracle):
        descriptor, observed = oracle.descriptor, []

        def read(fight, actor):
            observed.append(actor.id)
            return descriptor(fight, actor)

        oracle.descriptor = read
        with patch.object(
            jondo_snapshot,
            "source",
            return_value=dict(nativeIdentity="source", catalogRevision="a" * 64),
        ), patch.object(
            jondo_snapshot,
            "effective_affiliation",
            side_effect=lambda f, a: a.team,
        ), patch(
            "wakfu_server.combat_los.authoritative_visible",
            return_value=True,
        ), patch(
            "wakfu_server.combat_tackle_movement.movement_tackle_cost",
            return_value=(0, 0),
        ):
            result = jondo_snapshot.build_snapshot(oracle)
        return result, observed

    def test_retired_receipt_excluded_but_offplay_and_unknown_hp0_remain(self):
        oracle = self.fixture()
        fight = oracle.runtime.fight
        before, count = deepcopy(vars(fight)), len(fight.actors)
        self.assertEqual(hidden_snapshot_actor_ids(fight), {6})
        result, observed = self.build(oracle)
        identities = {a["id"] for a in result["board"]["actors"]}
        self.assertNotIn(6, identities)
        self.assertNotIn(6, observed)
        self.assertIn(4, identities)
        self.assertIn(7, identities)
        self.assertEqual(len(fight.actors), count)
        self.assertEqual(vars(fight), before)
        self.assertEqual(
            fight.native_owned_group_effects[99]["invocation"]["caster_id"],
            6,
        )

    def test_controlled_summon_and_its_state_target_stay_observable(self):
        oracle = self.fixture()
        fight = oracle.runtime.fight
        actor = fight.actors[3]
        actor.controlled = True
        actor.state_ledger.entries = [
            SimpleNamespace(reference=101, level=2, duration=3, caster_id=1),
        ]
        fight.native_summon_registrations = {
            3: dict(caster_id=1, controller_id=1),
        }
        before = deepcopy(vars(fight))
        result, _ = self.build(oracle)
        row = next(a for a in result["board"]["actors"] if a["id"] == 3)
        self.assertTrue(row["registeredSummon"])
        self.assertTrue(row["isPlayer"])
        self.assertEqual(row["summonerId"], 1)
        self.assertEqual(
            row["states"],
            [dict(reference=101, level=2, duration=3, casterId=1)],
        )
        self.assertEqual(vars(fight), before)

    def test_unverified_outofplay_still_rejects_without_mutation(self):
        oracle = self.fixture()
        fight = oracle.runtime.fight
        fight.native_ordinary_qi_retirements = {}
        del fight.actors[6].native_ordinary_qi_retirement
        before = deepcopy(vars(fight))
        with self.assertRaisesRegex(
            ValueError,
            "Unverified native snapshot fighter retirement",
        ):
            self.build(oracle)
        self.assertEqual(vars(fight), before)


if __name__ == "__main__":
    unittest.main()
