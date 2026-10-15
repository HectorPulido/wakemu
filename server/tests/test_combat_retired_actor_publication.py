"""Retired actors keep their client QK byte until native death cleanup."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import struct
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_combat_summon_retirement import SummonRetirementTests
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_transaction import SpellTransaction
from wakfu_server.combat_wire import decode_actor_state


class RetiredActorPublicationTests(unittest.TestCase):
    def test_native_oracle_lethal_movement_preserves_death_cleanup_handle(self):
        ai_root = str(Path(__file__).resolve().parents[1] / "ai-service")
        if ai_root not in sys.path:
            sys.path.insert(0, ai_root)
        from wakfu_ai.native.native_oracle import NativeOracle

        for reference in (3251, 1382):
            with self.subTest(reference=reference):
                fight, owner, _, summon = self.fixture()
                summon.native_summon_source["ref"] = reference
                fight.native_summon_registrations[summon.id]["authority"][
                    "breed_id"
                ] = reference
                runtime = RuntimeMessages(fight)
                private = deepcopy(runtime)
                private.fight.apply_effect_damage(owner.id, summon.id, summon.hp)
                private.action_id = 1
                oracle = object.__new__(NativeOracle)
                oracle.runtime = runtime
                oracle.flags = {}
                oracle.authorities = lambda state: {}
                callback = (
                    struct.pack(">iii", fight.id, private.action_id, -1)
                    + b"lethal-area"
                )
                oracle.preview = lambda *args, **kwargs: (
                    private,
                    [(12613, callback)],
                    None,
                )
                serialized = []
                with patch("wakfu_ai.native.native_oracle.check"), patch(
                    "wakfu_ai.native.native_oracle.complete_fingerprint",
                    return_value="stable",
                ):
                    packets = oracle.commit(
                        {"type": "move"},
                        stats_serializer=lambda actor, state: serialized.append(
                            actor.id
                        )
                        or b"owned",
                    )
                self.assertNotIn(summon.id, serialized)
                self.assertTrue(
                    any(
                        op == 12727
                        and struct.unpack_from(">q", body, 12)[0] == summon.id
                        for op, body in packets
                    )
                )
                self.assertEqual(runtime.fight.actors[summon.id].native_obstacle_id, -1)

    def test_final_ordinary_npc_retirement_is_hidden_from_later_cast_snapshots(self):
        from wakfu_server.combat_death import death_messages

        fight, owner, enemy, _ = self.fixture()
        fight.apply_effect_damage(owner.id, enemy.id, enemy.hp)
        runtime = RuntimeMessages(fight)
        deaths = death_messages(runtime, enemy.id)
        self.assertEqual([body[-1] for op, body in deaths if op == 12727], [0, 2])
        self.assertEqual(enemy.native_obstacle_id, -1)
        serialized = []
        tx = self.transaction(fight, lambda state: None)
        tx = replace(tx, action_id=runtime.action_id + 1)
        commit_spell_transaction(
            runtime,
            tx,
            stats_serializer=lambda actor, state: serialized.append(actor.id)
            or b"owned",
        )
        self.assertNotIn(enemy.id, serialized)
        self.assertIn(owner.id, serialized)

    def test_turn_start_lethal_area_keeps_callback_and_omits_retired_other_actor(self):
        fight, owner, _, summon = self.fixture()
        runtime = RuntimeMessages(fight)
        runtime.stats_serializer = lambda actor: b"owned"

        def start(state, **kwargs):
            state = deepcopy(state)
            state.apply_effect_damage(owner.id, summon.id, summon.hp)
            callback = (
                struct.pack(">iii", state.id, kwargs["action_id"], -1)
                + b"lethal-turn-area"
            )
            return state, [(12613, callback)]

        runtime.turn_start_provider = start
        packets = runtime.turn_started()
        self.assertTrue(
            any(
                op == 12613 and body[12:] == b"lethal-turn-area" for op, body in packets
            )
        )
        published = [
            decode_actor_state(op, body)["actor_id"]
            for op, body in packets
            if op == 12873
        ]
        self.assertNotIn(summon.id, published)
        self.assertIn(owner.id, published)

    def test_timed_expiration_lethal_effect_omits_retired_snapshot(self):
        fight, owner, _, summon = self.fixture()
        runtime = RuntimeMessages(fight)
        runtime.stats_serializer = lambda actor: b"owned"
        fight.owned_stat_effects[owner.id] = {"timer": {"remaining": 1}}

        def expire(state, **kwargs):
            state.apply_effect_damage(owner.id, summon.id, summon.hp)
            return [(12613, b"lethal-expiration")]

        with patch(
            "wakfu_server.combat_timed_expiration.expire_timed_effects",
            side_effect=expire,
        ):
            packets = runtime._expire_owned(
                actor_id=owner.id, round_number=1, phase="end"
            )
        self.assertIn((12613, b"lethal-expiration"), packets)
        self.assertNotIn(
            summon.id,
            [
                decode_actor_state(op, body)["actor_id"]
                for op, body in packets
                if op == 12873
            ],
        )
        self.assertEqual(runtime.fight.actors[summon.id].native_obstacle_id, -1)

    def fixture(self):
        fight, owner, enemy, summon = SummonRetirementTests().fight()
        from wakfu_server.combat_native_death_status import (
            initialize_fresh_bje_death_status,
        )

        initialize_fresh_bje_death_status(summon)
        return fight, owner, enemy, summon

    @staticmethod
    def transaction(fight, mutate):
        before = source_snapshot(fight)
        preview = deepcopy(fight)
        mutate(preview)
        return SpellTransaction(preview, {}, 0, (), (), (), before, 1)

    def test_cast_skips_retired_summon_snapshot_but_keeps_native_death(self):
        from wakfu_server.combat_death import newly_registered_death_messages

        fight, owner, _, summon = self.fixture()
        previous_sequence = fight.sequence
        tx = self.transaction(
            fight,
            lambda preview: preview.apply_effect_damage(owner.id, summon.id, summon.hp),
        )
        runtime = RuntimeMessages(fight)
        serialized = []

        def serialize(actor, state):
            serialized.append(actor.id)
            return b"visible-owned-stats"

        packets = commit_spell_transaction(runtime, tx, stats_serializer=serialize)
        self.assertNotIn(summon.id, serialized)
        self.assertNotIn(
            summon.id,
            [
                decode_actor_state(op, body)["actor_id"]
                for op, body in packets
                if op == 12873
            ],
        )
        self.assertEqual(runtime.fight.actors[summon.id].native_obstacle_id, -1)
        deaths = newly_registered_death_messages(
            runtime, after_sequence=previous_sequence
        )
        self.assertTrue(
            any(
                op == 12727
                and struct.unpack_from(">q", body, 12)[0] == summon.id
                and body[-1] == 2
                for op, body in deaths
            )
        )

    def test_cast_keeps_reversible_player_corpse_snapshot(self):
        fight, owner, enemy, _ = self.fixture()
        original_slot = owner.native_obstacle_id
        tx = self.transaction(
            fight,
            lambda preview: preview.apply_effect_damage(enemy.id, owner.id, owner.hp),
        )
        serialized = []
        runtime = RuntimeMessages(fight)
        commit_spell_transaction(
            runtime,
            tx,
            stats_serializer=lambda actor, state: serialized.append(actor.id)
            or b"owned",
        )
        self.assertIn(owner.id, serialized)
        self.assertEqual(
            runtime.fight.actors[owner.id].native_obstacle_id, original_slot
        )

    def test_cast_keeps_ordinary_corpse_original_qi_until_death_delivery(self):
        fight, owner, enemy, _ = self.fixture()
        original_slot = enemy.native_obstacle_id
        tx = self.transaction(
            fight,
            lambda preview: preview.apply_effect_damage(owner.id, enemy.id, enemy.hp),
        )
        serialized = []
        runtime = RuntimeMessages(fight)
        commit_spell_transaction(
            runtime,
            tx,
            stats_serializer=lambda actor, state: serialized.append(actor.id)
            or b"owned",
        )
        self.assertIn(enemy.id, serialized)
        self.assertEqual(
            runtime.fight.actors[enemy.id].native_obstacle_id, original_slot
        )

    def test_area_wrapper_drops_retired_mover_snapshot_keeps_callback(self):
        from wakfu_server.combat_movement_runtime import _with_areas
        from wakfu_server.combat_wire import actor_state

        fight, owner, _, summon = self.fixture()
        runtime = RuntimeMessages(fight)

        def operation(candidate, callback):
            candidate.fight.apply_effect_damage(owner.id, summon.id, summon.hp)
            callback(
                candidate.fight, candidate.fight.actors[summon.id], (1, 0, 0), (1, 1, 0)
            )
            return [
                (13624, b"native-movement"),
                candidate._flush(),
                (
                    12873,
                    actor_state(12873, fight.id, summon.id, b"retired-QK-minus-one"),
                ),
            ], {"path": [(1, 1, 0)]}

        packets, _ = _with_areas(
            runtime,
            lambda preview, **kwargs: (deepcopy(preview), [(12613, b"lethal-area")]),
            operation,
        )
        self.assertEqual([op for op, _ in packets], [13624, 13420, 12613, 13420])

    def test_ai_nonspell_delivery_skips_retired_summon_snapshot(self):
        from wakfu_server.combat_tactical_ai import NativeProvider, Preview

        fight, owner, _, summon = self.fixture()
        preview = deepcopy(fight)
        preview.apply_effect_damage(owner.id, summon.id, summon.hp)
        provider = SimpleNamespace(
            area_provider=None,
            preview=lambda *args, **kwargs: Preview(preview),
        )
        runtime = RuntimeMessages(fight)
        serialized = []
        with patch(
            "wakfu_server.combat_tactical_ai._source_key", return_value="same-source"
        ):
            packets = NativeProvider.commit(
                provider,
                runtime,
                {"type": "move"},
                lambda actor, state: serialized.append(actor.id) or b"owned",
            )
        self.assertNotIn(summon.id, serialized)
        self.assertNotIn(
            summon.id,
            [
                decode_actor_state(op, body)["actor_id"]
                for op, body in packets
                if op == 12873
            ],
        )


if __name__ == "__main__":
    unittest.main()
