"""Real native AP/MP consumable plans retain their original cap flags."""
import struct
import uuid

from postgres_case import PostgresCase
from wakfu_server.consumable_characteristics import bonuses as consumable_bonuses
from wakfu_server.equipment_stats import bonuses as equipment_bonuses
from wakfu_server.inventory_consumable_effects import use
from wakfu_server.inventory_items import grant


class ConsumableResourcePlanProjectionPostgresTests(PostgresCase):
    def test_native_ap_and_mp_foods_apply_from_real_flags_without_resource_caps(self):
        account = self.store.register(
            "consumable-resource-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        character = self.store.create_character(account, "Buff Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        initial_character = self.store.character(account, character["id"])
        container = next(
            row["uid"]
            for row in initial_character["inventory_containers"]
            if row["kind"] == 0
        )

        # These are the two actual native one-point resource plans. Inspect the
        # persisted plans as well as using them through opcode 12659 so this
        # verifies the original flag17 source of their uncapped behavior.
        for reference, stat in ((14755, 2), (14796, 3)):
            with self.subTest(reference=reference):
                with self.store.connection() as db:
                    from wakfu_server.consumable_catalog import load_plan

                    plan = load_plan(db, reference)
                self.assertIsNotNone(plan)
                leaves = [
                    effect
                    for state in plan["states"]
                    for effect in state.get("metadata", {})
                    .get("native_effects", {})
                    .values()
                    if effect.get("generic") == (31 if stat == 2 else 41)
                    and effect.get("runner") == "eWN"
                ]
                self.assertEqual(len(leaves), 1)
                self.assertIn(17, leaves[0]["native_metadata"]["native_effect_flags"])

                uid = grant(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    reference=reference,
                    quantity=1,
                    container=container,
                    slot=10 if stat == 2 else 11,
                    allowed_references={reference},
                )["uid"]
                before = self.store.character(account, character["id"])
                before_projection = equipment_bonuses(
                    before, include_consumable_buffs=True
                )["resource_projection"]["final"]
                result = use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qB", uid, 0),
                    expected_hp=before["hp"],
                    in_fight=False,
                )
                after_projection = equipment_bonuses(
                    result["character"], include_consumable_buffs=True
                )["resource_projection"]["final"]
                self.assertEqual(
                    (
                        after_projection[stat]["current"],
                        after_projection[stat]["maximum"],
                    ),
                    (
                        before_projection[stat]["current"] + 1,
                        before_projection[stat]["maximum"] + 1,
                    ),
                )
                projected = consumable_bonuses(
                    result["character"], include_operations=True
                )
                self.assertEqual(projected["unsupported"], [])
                self.assertEqual(projected["resource_kinds"][0]["cap"], None)
                character = result["character"]


if __name__ == "__main__":
    import unittest

    unittest.main()
