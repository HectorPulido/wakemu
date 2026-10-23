"""Native result display requires a frozen joined owner and reward-list entry."""
from copy import deepcopy
import struct
import unittest

from wakfu_server.objectives.environmental_result_delivery import plan_result_delivery


class EnvironmentalResultDeliveryTests(unittest.TestCase):
    def joined(self, *, kind="completed", display_rank=1):
        delivery = dict(
            delivery_key=f"environmental:42:11:{kind}:3",
            kind=kind,
            instance_id=42,
            revision=3,
            account_id=7,
            character_id=11,
        )
        view = dict(
            instance_id=42,
            profile_key="original-result",
            version=2,
            native_scenario_id=-2311,
            score=3_050_975,
            native_publication=dict(challenge_id=-2311, secondary_id=17),
            native_result=dict(
                profile_key="original-result",
                version=2,
                instance_id=42,
                account_id=7,
                character_id=11,
                source_authority="installed primary reward list",
                mapping_authority="qualified profile-to-list entry",
                parameter_authority="qualified native result parameter",
                challenge_id=-2311,
                secondary_id=17,
                primary_reward_count=1,
                primary_reward_index=0,
                display_rank=display_rank,
                name="Héctor",
                result_parameter=6,
                terminal_state=kind,
                terminal_at_ms=5000,
            ),
        )
        return delivery, view

    def plan(self, delivery, view):
        return plan_result_delivery(delivery, view, account_id=7, character_id=11)

    def decode(self, plan):
        self.assertEqual(len(plan["packets"]), 1)
        opcode, payload = plan["packets"][0]
        self.assertEqual(opcode, 13263)
        challenge, secondary, name_length = struct.unpack_from(">iib", payload)
        offset = 9 + name_length
        name = payload[9:offset].decode("utf-8") if name_length else None
        parameter, raw_rank, index = struct.unpack_from(">ihi", payload, offset)
        self.assertEqual(len(payload), offset + 10)
        return challenge, secondary, name, parameter, raw_rank, index

    def test_joined_primary_index_is_distinct_from_score_and_does_not_mutate_inputs(
        self,
    ):
        for kind in ("completed", "expired"):
            with self.subTest(kind=kind):
                delivery, view = self.joined(kind=kind)
                # Earned display is independent of whether capacity delayed the claim.
                view["reward_claimed"] = False
                delivery["score"] = 900_000
                before = deepcopy((delivery, view))
                plan = self.plan(delivery, view)
                self.assertEqual((delivery, view), before)
                self.assertEqual(
                    {
                        k: plan[k]
                        for k in ("delivery_key", "instance_id", "revision", "kind")
                    },
                    dict(
                        delivery_key=delivery["delivery_key"],
                        instance_id=42,
                        revision=3,
                        kind="native_result",
                    ),
                )
                self.assertEqual(self.decode(plan), (-2311, 17, "Héctor", 6, 0, 0))
                view["score"] = 17
                delivery["score"] = 2**63 - 1
                self.assertEqual(self.plan(delivery, view), plan)

    def test_maximum_display_rank_and_unranked_values_keep_native_signed_wire_bounds(
        self,
    ):
        for displayed, raw in ((0, -1), (1, 0), (32767, 32766)):
            with self.subTest(display_rank=displayed):
                delivery, view = self.joined(display_rank=displayed)
                view["native_result"]["name"] = None
                self.assertEqual(
                    self.decode(self.plan(delivery, view)), (-2311, 17, None, 6, raw, 0)
                )

    def test_foreign_join_invalid_index_rank_and_missing_authority_are_rejected(self):
        mutations = (
            ("delivery", "instance_id", 43),
            ("delivery", "account_id", 8),
            ("delivery", "character_id", 12),
            ("delivery", "revision", True),
            ("native_result", "instance_id", 43),
            ("native_result", "account_id", 8),
            ("native_result", "character_id", 12),
            ("native_result", "profile_key", "foreign-profile"),
            ("native_result", "version", 3),
            ("native_result", "version", True),
            ("native_result", "challenge_id", -2312),
            ("native_publication", "secondary_id", 18),
            ("native_result", "primary_reward_count", 0),
            ("native_result", "primary_reward_index", 1),
            ("native_result", "primary_reward_index", True),
            ("native_result", "display_rank", 32768),
            ("native_result", "display_rank", True),
            ("native_result", "terminal_state", "expired"),
            ("native_result", "terminal_at_ms", None),
            ("native_result", "source_authority", None),
            ("native_result", "mapping_authority", "  "),
            ("native_result", "parameter_authority", ""),
        )
        for section, key, value in mutations:
            with self.subTest(section=section, key=key, value=value):
                delivery, view = self.joined()
                target = delivery if section == "delivery" else view[section]
                target[key] = value
                before = deepcopy((delivery, view))
                with self.assertRaises(ValueError):
                    self.plan(delivery, view)
                self.assertEqual((delivery, view), before)
        delivery, view = self.joined()
        del view["native_result"]["name"]
        with self.assertRaises(ValueError):
            self.plan(delivery, view)

    def test_missing_result_or_publication_and_nonterminal_progress_do_not_publish(
        self,
    ):
        for missing in ("native_result", "native_publication"):
            with self.subTest(missing=missing):
                delivery, view = self.joined()
                del view[missing]
                self.assertIsNone(self.plan(delivery, view))
                view[missing] = None
                self.assertIsNone(self.plan(delivery, view))
        for kind in ("progress", "snapshot", "claimed"):
            with self.subTest(kind=kind):
                delivery, view = self.joined()
                delivery["kind"] = kind
                self.assertIsNone(self.plan(delivery, view))


if __name__ == "__main__":
    unittest.main()
