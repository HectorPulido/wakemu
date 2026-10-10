import copy
import json
import os
import random
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

from wakfu_server.combat_tackle_movement import native_tackle_loss, movement_tackle_cost
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_state import Actor, Fight


class Authority:
    def __call__(self, fight, actor):
        return NativeActorAuthority(
            targeting=dict(
                baF=True,
                baG=False,
                baK=False,
                dpu_id=getattr(actor, "master", actor.id),
            ),
            is_player=True,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=getattr(actor, "carried", False),
            breed_id=1,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
        )

    def properties(self, fight, actor):
        return getattr(actor, "pb", frozenset())


class NativeTackleMovementTests(unittest.TestCase):
    def test_original_jvm_108_case_arithmetic_export(self):
        rows = json.loads(
            (
                Path(__file__).parent / "fixtures/native-tackle-fef-20261009.json"
            ).read_text()
        )
        self.assertEqual(len(rows), 108)
        for row in rows:
            with self.subTest(row=row):
                self.assertEqual(
                    native_tackle_loss(
                        [row["lock"]], row["dodge"], row["level"], "BACK"
                    ),
                    (row["ap"], row["mp"]),
                )

    def fixture(self):
        mover = Actor(7, 0, (0, 0, 0), 100, 6, 6, 20, 60, 3, True)
        enemy = Actor(8, 1, (1, 0, 0), 100, 6, 6, 10, 60)
        cells = {(x, y, 0) for x in range(-2, 3) for y in range(-2, 3)}
        fight = Fight(
            2, [mover, enemy], cells, {0: {mover.position}, 1: {enemy.position}}
        )
        fight.ready(3)
        for actor in (mover, enemy):
            actor.effect_stats = {7: 100, 8: 100, 2: 6, 3: 6}
            actor.physical_radius = 0
            actor.direction = 5  # Enemy faces mover from x=1.
        fight.native_rail_movement_authority = Authority()
        return fight, mover, enemy

    def test_original_float32_level_scaling_and_facing_split(self):
        self.assertEqual(native_tackle_loss([100], 100, 60, "FRONT"), (1, 2))
        self.assertEqual(native_tackle_loss([100], 100, 60, "SIDE"), (1, 1))
        self.assertEqual(native_tackle_loss([100], 100, 60, "BACK"), (0, 1))
        self.assertEqual(native_tackle_loss([100], 100, 200, "FRONT"), (2, 2))
        self.assertEqual(native_tackle_loss([100], 1000, 60, "FRONT"), (0, 0))
        self.assertEqual(native_tackle_loss([1000], 0, 200, "FRONT"), (4, 4))
        self.assertEqual(native_tackle_loss([], 0, 60, "FRONT"), (0, 0))

    def test_real_fsm_charges_ap_and_extra_mp_on_departure_only(self):
        fight, actor, enemy = self.fixture()
        self.assertEqual(movement_tackle_cost(fight, actor, [(0, 1, 0)]), (1, 2))
        event = fight.move(3, actor.id, [(0, 1, 0)])
        self.assertEqual((actor.ap, actor.mp, actor.position), (5, 3, (0, 1, 0)))
        self.assertEqual(
            (event["tackle_ap"], event["tackle_mp"], event["cost"]), (1, 2, 3)
        )
        # Entering contact at the destination adds no departure penalty.
        actor.position = (-2, 0, 0)
        self.assertEqual(
            movement_tackle_cost(fight, actor, [(-1, 0, 0), (0, 0, 0)]), (0, 0)
        )

    def test_rejected_cost_preserves_resources_geometry_and_events(self):
        fight, actor, _ = self.fixture()
        actor.mp = 2
        before = copy.deepcopy(
            (
                {k: v for k, v in actor.__dict__.items() if k != "state_ledger"},
                fight.events,
                fight.sequence,
            )
        )
        with self.assertRaisesRegex(ValueError, "insufficient AP/MP"):
            fight.move(3, actor.id, [(0, 1, 0)])
        self.assertEqual(
            (
                {k: v for k, v in actor.__dict__.items() if k != "state_ledger"},
                fight.events,
                fight.sequence,
            ),
            before,
        )

    def test_client_codec_failure_rolls_back_both_tackle_resources(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client

        fight, actor, _ = self.fixture()
        runtime = RuntimeMessages(fight)
        before = copy.deepcopy(
            (
                actor.ap,
                actor.mp,
                actor.position,
                actor.effect_stats,
                fight.events,
                fight.sequence,
            )
        )

        def fail(preview):
            self.assertEqual((preview.ap, preview.mp), (5, 3))
            self.assertEqual((actor.ap, actor.mp), (6, 6))
            raise ValueError("owned movement codec failure")

        with self.assertRaisesRegex(ValueError, "owned movement codec failure"):
            apply_client(runtime, 3, struct.pack(">qiih", actor.id, 0, 1, 0), fail)
        self.assertEqual(
            (
                actor.ap,
                actor.mp,
                actor.position,
                actor.effect_stats,
                fight.events,
                fight.sequence,
            ),
            before,
        )
        self.assertEqual(runtime.action_id, 0)

    def test_raw_pa_mutations_notify_ap_listener_once(self):
        from tests.test_combat_resource_pa_notifications import (
            ResourcePANotificationTests,
        )
        from wakfu_server.combat_resource_pa_notifications import attach_ap_listener

        fight, actor, _ = self.fixture()
        _, raw = ResourcePANotificationTests().fixture()
        for key, value in raw.__dict__.items():
            if key not in ("id", "effect_stats"):
                setattr(actor, key, copy.deepcopy(value))
        actor.mp = actor.max_mp = 6
        for key in (
            "effect_maxima",
            "effect_base_maxima",
            "effect_resource_raw_currents",
        ):
            getattr(actor, key)[3] = 6
        attach_ap_listener(fight, actor, 99)
        fight.move(3, actor.id, [(0, 1, 0)])
        # The real eWq AP observer additionally removes one MP. The original
        # movement penalty itself is charged exactly once through each PA.
        self.assertEqual((actor.ap, actor.mp), (5, 2))
        self.assertEqual(actor.effect_resource_raw_currents, {2: 5, 3: 2})

    def test_properties_carry_and_master_affiliation_are_actual_filters(self):
        fight, actor, enemy = self.fixture()
        for pb in (frozenset({15}), frozenset({5}), frozenset({17})):
            enemy.pb = pb
            self.assertEqual(movement_tackle_cost(fight, actor, [(0, 1, 0)]), (0, 0))
        enemy.pb = frozenset()
        enemy.master = actor.id
        self.assertEqual(movement_tackle_cost(fight, actor, [(0, 1, 0)]), (0, 0))
        del enemy.master
        actor.pb = frozenset({69})
        self.assertEqual(movement_tackle_cost(fight, actor, [(0, 1, 0)]), (0, 0))
        actor.pb = frozenset()
        enemy.carried = True
        self.assertEqual(movement_tackle_cost(fight, actor, [(0, 1, 0)]), (0, 0))

    def test_native_inplay_filter_precedes_corpse_relationship_lookup(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )

        fight, actor, enemy = self.fixture()
        initialize_global_pv_collections(fight, tuple(fight.actors))
        set_global_fighter_status(fight, enemy.id, "OFF_PLAY")

        class RejectCorpse(Authority):
            def __call__(self, fight, candidate):
                if candidate.id == enemy.id:
                    raise AssertionError("Original fdU must exclude corpse first")
                return super().__call__(fight, candidate)

        fight.native_rail_movement_authority = RejectCorpse()
        self.assertEqual(movement_tackle_cost(fight, actor, [(0, 1, 0)]), (0, 0))

    @unittest.skipUnless(
        os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
    )
    def test_actual_level60_class_initialization_binds_complete_movement_consumer(self):
        from tests.test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        character, creature, fight = SpellTransactionTests().native_server_fixture(
            9, 60, native_qi=True, target_distance=1
        )
        initialized, _ = prepare_server_initialization(
            character,
            {-7: creature},
            fight,
            3,
            encode_deck([4820]),
            action_id=1,
            rng=random.Random(0),
            fight_start=True,
        )
        actor = initialized.actors[7]
        for candidate in initialized.actors.values():
            self.assertIn(7, candidate.effect_stats)
            self.assertIn(8, candidate.effect_stats)
        destination = (actor.position[0] - 1, actor.position[1], actor.position[2])
        self.assertIn(destination, initialized.walkable)
        loss_ap, loss_mp = movement_tackle_cost(initialized, actor, [destination])
        before = (actor.ap, actor.mp, actor.position)
        if loss_ap > actor.ap or 1 + loss_mp > actor.mp:
            with self.assertRaisesRegex(ValueError, "insufficient AP/MP"):
                initialized.move(3, actor.id, [destination])
            self.assertEqual((actor.ap, actor.mp, actor.position), before)
        else:
            initialized.move(3, actor.id, [destination])
            self.assertEqual(
                (actor.ap, actor.mp, actor.position),
                (before[0] - loss_ap, before[1] - 1 - loss_mp, destination),
            )


if __name__ == "__main__":
    unittest.main()
