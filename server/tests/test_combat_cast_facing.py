import unittest
import struct
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_cast_facing import (
    finish_mirrored_cast_facing,
    mirror_cast_facing,
    native_cast_facing,
    cast_direction,
)


class CastFacingTest(unittest.TestCase):
    def test_original_desplume_script_turns_caster_before_mode6(self):
        source = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        preview = deepcopy(source)
        self.assertTrue(
            mirror_cast_facing(
                preview,
                {"spell_id": 7318, "target": (-1, 0, 0)},
                fight=SimpleNamespace(actors={7: preview}),
            )
        )
        self.assertEqual(preview.direction, 5)
        self.assertEqual(source.direction, 0)
        self.assertEqual(native_cast_facing()["7318"]["script_id"], 1002410)

    def test_same_xy_preserves_direction(self):
        actor = SimpleNamespace(position=(0, 0, 0), direction=3)
        self.assertFalse(
            mirror_cast_facing(actor, {"spell_id": 7318, "target": (0, 0, 9)})
        )
        self.assertEqual(actor.direction, 3)

    def test_explicit_no_turn_preserves_direction(self):
        actor = SimpleNamespace(position=(0, 0, 0), direction=7)
        records = {
            "1": {
                "status": "verified",
                "turnCasterTowardTargetCell": False,
                "useDiags": True,
            }
        }
        self.assertFalse(
            mirror_cast_facing(
                actor, {"spell_id": 1, "target": (2, 0, 0)}, contracts=records
            )
        )
        self.assertEqual(actor.direction, 7)

    def test_original_cardinal_and_diagonal_vector_matrix(self):
        path = (
            Path(__file__).parents[2]
            / "server/tests/fixtures/native_combat_oracles/cast-facing.tsv"
        )
        for line in path.read_text().splitlines():
            dx, dy, cardinal, diagonal = map(int, line.split())
            for enabled, expected in ((False, cardinal), (True, diagonal)):
                expected = None if dx == dy == 0 else expected
                self.assertEqual(cast_direction(dx, dy, diagonals=enabled), expected)

    def test_diagonal_1040_facing_is_transient_and_finishes_cardinal(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=3)
        fight = SimpleNamespace(actors={7: actor})
        plan = {"spell_id": 1, "target": (1, -1, 0)}
        contracts = {
            "1": {
                "status": "verified",
                "template": 1040,
                "turnCasterTowardTargetCell": True,
                "useDiags": True,
                "casterAnimOnTarget": False,
            }
        }

        self.assertTrue(
            mirror_cast_facing(actor, plan, fight=fight, contracts=contracts)
        )
        self.assertEqual(actor.direction, 0)  # used while spell effects are evaluated
        self.assertTrue(
            finish_mirrored_cast_facing(
                actor,
                plan,
                fight=fight,
                contracts=contracts,
            )
        )
        self.assertEqual(actor.direction, 7)  # native 1040 delayed useDiags=false

    def test_delayed_cardinal_reset_is_independent_of_initial_turn_flag(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        fight = SimpleNamespace(actors={7: actor})
        contracts = {
            "1": {
                "status": "verified",
                "template": 1040,
                "turnCasterTowardTargetCell": False,
                "useDiags": True,
                "casterAnimOnTarget": False,
            }
        }
        self.assertTrue(
            finish_mirrored_cast_facing(
                actor,
                {"spell_id": 1, "target": (1, -1, 0)},
                fight=fight,
                contracts=contracts,
            )
        )
        self.assertEqual(actor.direction, 7)

    def test_diagonal_finish_does_not_turn_caster_when_script_animates_target(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        contracts = {
            "1": {
                "status": "verified",
                "template": 1040,
                "turnCasterTowardTargetCell": True,
                "useDiags": True,
                "casterAnimOnTarget": True,
            }
        }
        self.assertFalse(
            finish_mirrored_cast_facing(
                actor,
                {"spell_id": 1, "target": (1, -1, 0)},
                fight=SimpleNamespace(actors={7: actor}),
                contracts=contracts,
            )
        )
        self.assertEqual(actor.direction, 0)

    def test_unverified_script_keeps_prior_orientation(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        self.assertFalse(
            finish_mirrored_cast_facing(
                actor,
                {"spell_id": 1, "target": (1, -1, 0)},
                fight=SimpleNamespace(actors={7: actor}),
                contracts={"1": {"status": "pending", "useDiags": True}},
            )
        )
        self.assertEqual(actor.direction, 0)

    def test_spell_transaction_keeps_diagonal_for_dispatch_then_serializes_cardinal(
        self,
    ):
        cells = {(0, 0, 0), (1, -1, 0), (3, 0, 0)}
        caster = Actor(7, 0, (0, 0, 0), 60, 6, 3, 9, 3, 7, True)
        caster.direction = 3
        enemy = Actor(-2, 1, (3, 0, 0), 12, 6, 3, 1, 1)
        fight = Fight(
            2,
            [caster, enemy],
            cells,
            {0: {caster.position}, 1: {enemy.position}},
            set(),
        )
        fight.ready(7)
        runtime = RuntimeMessages(fight)
        plan = {
            "actor_id": 7,
            "spell_id": 4808,
            "spell_uid": 4808,
            "evaluation_level": 1,
            "target": (1, -1, 0),
            "target_id": -2,
            "costs": {"ap": 0, "mp": 0, "wp": 0, "extra_resource_deltas": {}},
            "effect_ids": [],
            "native_usage": {"interval": 0, "per_turn": 0, "targets": []},
        }
        contracts = {
            "4808": {
                "status": "verified",
                "template": 1040,
                "turnCasterTowardTargetCell": True,
                "useDiags": True,
                "casterAnimOnTarget": False,
            }
        }
        dispatch_directions = []

        def factory(preview, _plan):
            dispatch_directions.append(preview.actors[7].direction)
            return (
                EffectDispatcher(
                    {},
                    {},
                    resolve=lambda *_: (),
                    condition_context=lambda *_: None,
                    probability_accepts=lambda *_: True,
                    group_cells=lambda *_: (),
                    actor_position=lambda uid: preview.actors[uid].position,
                ),
                [],
            )

        with patch(
            "wakfu_server.combat_spell_transaction.prepare_spell_cast",
            return_value=plan,
        ), patch(
            "wakfu_server.combat_ai_cast_history.record_authorized_cast",
            return_value=None,
        ), patch(
            "wakfu_server.combat_cast_facing.native_cast_facing",
            return_value={"4808": contracts["4808"]},
        ):
            transaction = prepare_spell_transaction(
                b"",
                {"id": 7},
                fight,
                7,
                b"",
                wp_current=0,
                action_id=1,
                line_of_sight=lambda *_: True,
                runtime_factory=factory,
            )

        self.assertEqual(dispatch_directions, [0])
        self.assertEqual(
            [op for op, _ in transaction.packets[:4]], [13494, 13420, 12588, 12678]
        )
        self.assertEqual(transaction.packets[0][1][-1], 0)
        self.assertEqual(transaction.fight.actors[7].direction, 7)
        delivery = commit_spell_transaction(
            runtime,
            transaction,
            stats_serializer=lambda actor, _fight: struct.pack(">i", actor.direction),
        )
        actor_refreshes = [payload for opcode, payload in delivery if opcode == 12873]
        self.assertEqual(len(actor_refreshes), 2)
        self.assertTrue(actor_refreshes[0].endswith(struct.pack(">i", 7)))

    def test_signed_int_delta_overflow_before_float_conversion(self):
        actor = SimpleNamespace(id=7, position=(-2147483648, 0, 0), direction=7)
        records = {
            "1": {
                "status": "verified",
                "turnCasterTowardTargetCell": True,
                "useDiags": True,
            }
        }
        mirror_cast_facing(
            actor,
            {"spell_id": 1, "target": (2147483647, 1, 0)},
            contracts=records,
            fight=SimpleNamespace(actors={7: actor}),
        )
        self.assertEqual(actor.direction, 4)  # int delta(-1,+1), not (+4294967295,+1).

    def test_failed_dispatch_factory_does_not_commit_mirrored_direction_or_costs(self):
        caster = SimpleNamespace(
            id=7, position=(0, 0, 0), direction=3, ap=6, mp=3, effect_stats=None
        )
        fight = SimpleNamespace(id=77, actors={7: caster}, events=[])
        plan = {
            "actor_id": 7,
            "spell_id": 7318,
            "target": (-2, 0, 0),
            "costs": {"ap": 2, "mp": 0, "wp": 0, "extra_resource_deltas": {}},
        }

        def failing(preview, request):
            self.assertEqual(preview.actors[7].direction, 5)
            self.assertEqual(preview.actors[7].ap, 4)
            raise ValueError("later dispatcher failure")

        with patch(
            "wakfu_server.combat_spell_transaction.source_snapshot", return_value={}
        ), patch(
            "wakfu_server.combat_spell_transaction.prepare_spell_cast",
            return_value=plan,
        ), patch(
            "wakfu_server.combat_ai_cast_history.record_authorized_cast",
            return_value=None,
        ):
            with self.assertRaisesRegex(ValueError, "later dispatcher failure"):
                prepare_spell_transaction(
                    b"",
                    {},
                    fight,
                    3,
                    b"",
                    wp_current=6,
                    action_id=1,
                    line_of_sight=lambda *a: True,
                    runtime_factory=failing,
                )
        self.assertEqual((caster.direction, caster.ap, caster.mp), (3, 6, 3))
