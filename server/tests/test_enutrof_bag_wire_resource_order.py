"""Real PA snapshots and evaluated MP reward must reconcile in delivery order."""
import os
import struct
import unittest
from unittest.mock import patch

import test_enutrof_remaining_companion_actions as fixture_module
import test_enutrof_two_owner_bag_movement as movement_case
from wakfu_server.combat_actor import actual_actor_stats
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_wire import decode_actor_state


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EnutrofBagWireResourceOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        movement_case.EnutrofTwoOwnerBagMovementTests.setUpClass()

    def test_actual_post_callback_pa_and_mp_reward_do_not_double_apply_on_wire(self):
        characters = {}
        deliveries = []
        fixture_type = fixture_module.EnutrofRemainingCompanionActionsTests
        original_fixture = fixture_type.fixture
        original_move = movement_case.apply_client

        def fixture(helper):
            result = original_fixture(helper)
            characters.update(result[1])
            return result

        def move(runtime, owner_id, body, serializer, **kwargs):
            def real_serializer(actor, current):
                return actual_actor_stats(
                    characters[actor.id],
                    actor,
                    current.id,
                    fight=current,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                )

            before = runtime.fight.actors[9]
            initial_mp = (before.mp, before.max_mp)
            packets, result = original_move(
                runtime,
                owner_id,
                body,
                serializer,
                runtime_stats_serializer=real_serializer,
                **kwargs
            )
            actor = runtime.fight.actors[9]
            deliveries.append((packets, actor.mp, actor.max_mp, initial_mp))
            return packets, result

        with patch.object(fixture_type, "fixture", fixture), patch.object(
            movement_case, "apply_client", move
        ):
            movement_case.EnutrofTwoOwnerBagMovementTests().test_ally_last_paid_mp_retires_one_bag_and_preserves_other_owner_areas()

        from wakfu_server.combat_retained_runtime import native_retained_metadata

        reward_metadata = native_retained_metadata()["effects"]["384633"]
        self.assertEqual(reward_metadata["effect_class"], 41)
        self.assertIs(reward_metadata["subscription"], False)
        self.assertEqual(reward_metadata["parameters"], [1.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        checked = 0
        for packets, server_mp, server_maximum, initial_mp in deliveries:
            has_reward = any(
                kind == 12613
                and struct.unpack_from(">i", body, 13)[0] == 41
                and _identity_fields(body[19:]).get(3) == 384633
                for kind, body in packets
            )
            if not has_reward:
                continue
            checked += 1

            def project(ordered):
                current, maximum = initial_mp
                trace = []
                reward_positions, snapshot_positions = [], []
                for index, (kind, body) in enumerate(ordered):
                    if kind == 12873:
                        envelope = decode_actor_state(kind, body)
                        if envelope["actor_id"] != 9:
                            continue
                        blob = envelope["state"]
                        # Movement owns position and normally publishes native
                        # ALL_CHARACTERISTICS40; changed metadata keeps full3.
                        self.assertIn(blob[0], (3, 40))
                        offset = 1 if blob[0] == 40 else 39
                        count = struct.unpack_from(">H", blob, offset)[0]
                        rows = {
                            row[0]: row[1:]
                            for row in (
                                struct.unpack_from(">Biiii", blob, offset + 2 + i * 17)
                                for i in range(count)
                            )
                        }
                        current, _, maximum, percentage = rows[3]
                        self.assertEqual(percentage, 0)
                        snapshot_positions.append(index)
                        trace.append((kind, current, maximum))
                    elif kind == 12613 and struct.unpack_from(">i", body, 13)[0] == 41:
                        messages = {}
                        fields = _identity_fields(body[19:], messages=messages)
                        if fields.get(3) != 384633 or fields.get(7) != 9:
                            continue
                        additional = _identity_fields(
                            messages[8], integer_fields=(10, 31, 32)
                        )
                        self.assertEqual(
                            (fields[4], additional[10], additional[31]), (1, 1, 1)
                        )
                        self.assertIn(body[12], (0, 1))
                        # Original aVo.cYg(false) applies unsubscribed eWN too.
                        # The execute bit alone does not make this delta inert.
                        maximum += fields[4]
                        current = min(maximum, current + additional[10])
                        reward_positions.append(index)
                        trace.append((kind, bool(body[12]), current, maximum))
                return (current, maximum), trace, reward_positions, snapshot_positions

            projected, trace, rewards, snapshots = project(packets)
            self.assertEqual(len(rewards), 1, trace)
            self.assertEqual(len(snapshots), 1, trace)
            self.assertLess(rewards[0], snapshots[0], trace)
            self.assertEqual(projected, (server_mp, server_maximum), trace)

            # Preserve all other packet order; reproduce the old final-PA-first
            # bug using this actual native reward/snapshot tape, not fake values.
            old_order = list(packets)
            final_snapshot = old_order.pop(snapshots[0])
            old_order.insert(rewards[0], final_snapshot)
            old_projected, old_trace, _, _ = project(old_order)
            self.assertNotEqual(old_projected, (server_mp, server_maximum), old_trace)
        self.assertEqual(checked, 1)
