"""Public saved-build coverage for native resource gear and max predicates."""
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import builds, health_store, wire
from wakfu_server.character_levels import XP_BY_LEVEL
from wakfu_server.equipment import RULES
from wakfu_server.equipment_conditions import catalog as condition_catalog
from wakfu_server.equipment_stats import CATALOG, bonuses, combat_resources
from wakfu_server.inventory_items import grant


class EquipmentResourceProjectionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "resource-sheet-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(
            self.account, "Resource Sheet", breed=8
        )
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=245 WHERE id=%s",
                (self.character["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[245], self.character["id"]),
            )
        self.character = self.store.character(self.account, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def _grant(self, reference, slot):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    @staticmethod
    def _sheet(character, entries):
        equipment = b"".join(
            wire.proto_field(10, wire.proto_field(8, uid) + wire.proto_field(16, slot))
            for slot, uid in sorted(entries.items())
        )
        return dict(
            sheet=b"".join(
                wire.proto_field(tag, value)
                for tag, value in ((8, 0), (18, b"Resource sheet"), (24, 245), (56, 0))
            ),
            equipment=equipment or builds.EMPTY_EQUIPMENT,
            deck=b"",
            aptitudes=b"",
        )

    def _save(self, entries):
        current = self.store.character(self.account, self.character["id"])
        return self.store.save_build(
            self.account,
            self.generation,
            current["id"],
            0,
            self._sheet(current, entries),
        )

    @staticmethod
    def _resources(character):
        return bonuses(character)["resource_projection"]

    def test_native_resource_reductions_and_additions_survive_save_reload_and_clear(
        self,
    ):
        # These original rows exercise eWO AP/MP reductions and eWN AP/MP/WP
        # additions through the same selected build.  The final resource state
        # must derive from native baselines, not summed displayed deltas.
        refs = {9434: 16, 20248: 7, 28289: 13, 26994: 12, 26997: 3}
        for inventory_slot, (reference, slot) in enumerate(refs.items()):
            self.assertIn(slot, RULES[reference]["slots"])
            self._grant(reference, inventory_slot)
            self.assertIsNotNone(CATALOG.get(reference))

        self.assertEqual(
            condition_catalog()["26994"]["EQUIP"], 'GetCharacMax("WP") >= 8'
        )
        self.assertEqual(
            condition_catalog()["26997"]["EQUIP"], 'GetCharacMax("MP") <= 5'
        )
        initial_character = self.store.character(self.account, self.character["id"])
        initial = self._resources(initial_character)["initial"]
        self.assertEqual(
            (initial[2]["maximum"], initial[3]["maximum"], initial[4]["maximum"]),
            (6, 4, 6),
        )

        uids = {}
        for reference in refs:
            item = next(
                row
                for row in self.store.character(self.account, self.character["id"])[
                    "inventory_items"
                ]
                if row["reference"] == reference
            )
            uids[reference] = item["uid"]
        character = self._save(
            {slot: uids[reference] for reference, slot in refs.items()}
        )
        projection = self._resources(character)
        final = projection["final"]
        # Slot 3 and slot 13 raise WP to the exact threshold before the
        # conditional slot-12 boots are admitted. eWO AP/MP rows are applied
        # and the other two eWN sources produce the remaining four operations.
        self.assertEqual((final[2]["current"], final[2]["maximum"]), (6, 6))
        self.assertEqual((final[3]["current"], final[3]["maximum"]), (5, 5))
        self.assertEqual((final[4]["current"], final[4]["maximum"]), (8, 8))
        resources = combat_resources(character)
        self.assertEqual((resources["ap"], resources["mp"], resources["wp"]), (6, 5, 8))
        self.assertEqual(set(projection["final"]), {2, 3, 4})

        # A fresh Store hydration re-evaluates the saved sheet from the same
        # authoritative native baselines and keeps each owned UID.
        reopened = self.store.character(self.account, self.character["id"])
        self.assertEqual(self._resources(reopened), projection)
        self.assertEqual(combat_resources(reopened), resources)
        self.assertEqual(
            {
                row["reference"]: row["uid"]
                for row in reopened["inventory_items"]
                if row["reference"] in refs
            },
            uids,
        )

        cleared = self._save({})
        restored = self._resources(cleared)["final"]
        self.assertEqual(
            {stat: (row["current"], row["maximum"]) for stat, row in restored.items()},
            {stat: (row["current"], row["maximum"]) for stat, row in initial.items()},
        )
        self.assertEqual(
            (
                combat_resources(cleared)["ap"],
                combat_resources(cleared)["mp"],
                combat_resources(cleared)["wp"],
            ),
            (6, 4, 6),
        )

    def test_ap_maximum_condition_admits_only_after_seven_real_support_items(self):
        # The native AP>=13 criterion belongs to item26296. Seven distinct
        # owned AP+1 passives reach13 before it is registered. The candidate
        # contributes HP, not AP, so the resulting native AP maximum stays13.
        support = {
            16074: 0,
            17357: 3,
            2021: 4,
            7573: 5,
            17322: 12,
            2024: 13,
            20957: 16,
        }
        candidate = 26296
        self.assertEqual(
            condition_catalog()[str(candidate)]["EQUIP"], 'GetCharacMax("AP") >= 13'
        )
        uids = {}
        for inventory_slot, (reference, slot) in enumerate(
            {**support, candidate: 10}.items()
        ):
            self.assertIn(slot, RULES[reference]["slots"])
            self._grant(reference, inventory_slot)
            item = next(
                row
                for row in self.store.character(self.account, self.character["id"])[
                    "inventory_items"
                ]
                if row["reference"] == reference
            )
            uids[reference] = item["uid"]

        before = self._resources(
            self.store.character(self.account, self.character["id"])
        )["initial"][2]
        self.assertEqual(before["maximum"], 6)
        character = self._save(
            {
                **{slot: uids[reference] for reference, slot in support.items()},
                10: uids[candidate],
            }
        )
        projected = self._resources(character)["final"][2]
        bonuses_for_build = bonuses(character)
        self.assertIn(
            uids[candidate],
            bonuses_for_build["equipped_uids"],
            msg=(
                "max-conditioned candidate was not retained; "
                f"resources={projected}, unsupported={bonuses_for_build['unsupported']}, "
                f"equipment={character['builds'][0]['equipment']}"
            ),
        )
        self.assertEqual(
            (projected["current"], projected["maximum"]),
            (13, 13),
            msg=f"steps={bonuses_for_build['resource_projection']['steps']} "
            f"equipped={bonuses_for_build['equipped_uids']} "
            f"uidmap={uids}",
        )
        self.assertEqual(combat_resources(character)["ap"], 13)
        reopened = self.store.character(self.account, self.character["id"])
        self.assertEqual(self._resources(reopened)["final"][2], projected)

        cleared = self._save({})
        baseline = self._resources(cleared)["final"][2]
        self.assertEqual((baseline["current"], baseline["maximum"]), (6, 6))
        self.assertEqual(combat_resources(cleared)["ap"], 6)


if __name__ == "__main__":
    unittest.main()
