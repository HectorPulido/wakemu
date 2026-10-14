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

            packets, result = original_move(
                runtime,
                owner_id,
                body,
                serializer,
                runtime_stats_serializer=real_serializer,
                **kwargs
            )
            actor = runtime.fight.actors[9]
            deliveries.append((packets, actor.mp, actor.max_mp))
            return packets, result

        with patch.object(fixture_type, "fixture", fixture), patch.object(
            movement_case, "apply_client", move
        ):
            movement_case.EnutrofTwoOwnerBagMovementTests().test_ally_last_paid_mp_retires_one_bag_and_preserves_other_owner_areas()

        checked = 0
        for packets, server_mp, server_maximum in deliveries:
            has_reward = any(
                kind == 12613
                and struct.unpack_from(">i", body, 13)[0] == 41
                and _identity_fields(body[19:]).get(3) == 384633
                for kind, body in packets
            )
            if not has_reward:
                continue
            checked += 1
            current = maximum = None
            trace = []
            for kind, body in packets:
                if kind == 12873:
                    envelope = decode_actor_state(kind, body)
                    if envelope["actor_id"] != 9:
                        continue
                    # Native eHf3: XP8 + position20 + fight10 follow tag1.
                    blob, offset = envelope["state"], 39
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
                    trace.append((kind, current, maximum))
                elif kind == 12613 and struct.unpack_from(">i", body, 13)[0] == 41:
                    messages = {}
                    fields = _identity_fields(body[19:], messages=messages)
                    if fields.get(3) != 384633 or fields.get(7) != 9:
                        continue
                    additional = _identity_fields(
                        messages[8], integer_fields=(10, 31, 32)
                    )
                    self.assertIsNotNone(current, trace)
                    self.assertEqual(
                        (fields[4], additional[10], additional[31]), (1, 1, 1)
                    )
                    self.assertIn(body[12], (0, 1))
                    if body[12]:
                        # An executable delivery invokes eWN.c: PA.op, then
                        # PA.nG when decoded rCl is true. A retained delivery
                        # with execute=false only materializes its carrier;
                        # the authoritative PA snapshot already owns values.
                        maximum += fields[4]
                        current = min(maximum, current + additional[10])
                    trace.append((kind, bool(body[12]), current, maximum))
            self.assertEqual((current, maximum), (server_mp, server_maximum), trace)
        self.assertEqual(checked, 1)
