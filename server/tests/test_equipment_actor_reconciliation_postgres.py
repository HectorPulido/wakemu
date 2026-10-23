"""Public selected-build reconciliation after durable actor changes."""
import re
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import builds, equipment, wire
from wakfu_server.combat_conditions import _NATIVE_BREED_NAMES
from wakfu_server.equipment_conditions import catalog as condition_catalog
from wakfu_server.equipment_stats import CATALOG, _flat, bonuses
from wakfu_server.inventory_items import grant


class EquipmentActorReconciliationPostgresTests(PostgresCase):
    @staticmethod
    def _native_breed_item():
        names = {name.upper(): breed for name, breed in _NATIVE_BREED_NAMES.items()}
        rows = []
        for reference, actions in condition_catalog().items():
            criterion = actions.get("EQUIP", "")
            match = re.fullmatch(r'IsBreed\(["\']([A-Za-z]+)["\']\)', criterion.strip())
            if match is None or int(reference) not in equipment.RULES:
                continue
            breed = names.get(match.group(1).upper())
            if breed is None:
                continue
            template = CATALOG.get(int(reference), {"effects": []})
            effects = template["effects"]
            flats = [_flat(effect) for effect in effects]
            if effects and (
                any(value is None for value in flats)
                or not any(value != (0, 0) for value in flats)
            ):
                continue
            if not effects:
                continue
            rule = equipment.RULES[int(reference)]
            rows.append(
                (int(reference), breed, rule["slots"][0], rule["minimum_level"])
            )
        return sorted(rows, key=lambda row: (row[3], row[0]))

    def test_real_class_change_disables_existing_item_but_keeps_saved_uid_and_strict_new_admission(
        self,
    ):
        from wakfu_server.character_levels import XP_BY_LEVEL

        # Import through the flat production namespace; the physical file is
        # nested under characters but its relative imports expect this alias.
        from wakfu_server.breed_resources import playable_breeds
        from wakfu_server.equipment_stats import effective_character

        candidates = self._native_breed_item()
        self.assertTrue(
            candidates, "expected an actual supported breed-gated equipment item"
        )
        reference, breed, slot, minimum_level = candidates[0]
        other_breeds = sorted(set(playable_breeds()) - {breed})
        self.assertTrue(other_breeds)
        changed_breed = other_breeds[0]

        account = self.store.register(
            "actor-equip-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        character = self.store.create_character(account, "Actor Equipment", breed=breed)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=245 WHERE id=%s", (character["id"],)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[245], character["id"]),
            )
        character = self.store.character(account, character["id"])
        self.assertEqual(character["xp"], XP_BY_LEVEL[245])
        initial_sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in ((8, 0), (18, b"Actor equipment"), (24, 245), (56, 0))
        )
        character = self.store.save_build(
            account,
            generation,
            character["id"],
            0,
            dict(
                sheet=initial_sheet,
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=b"",
            ),
        )
        self.assertGreaterEqual(character["effective_level"], minimum_level)
        container = next(
            row["uid"] for row in character["inventory_containers"] if row["kind"] == 0
        )
        item = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={reference},
        )
        sheet = initial_sheet
        equipment_blob = wire.proto_field(
            10, wire.proto_field(8, item["uid"]) + wire.proto_field(16, slot)
        )
        blobs = dict(sheet=sheet, equipment=equipment_blob, deck=b"", aptitudes=b"")
        saved = self.store.save_build(account, generation, character["id"], 0, blobs)
        active = bonuses(saved)
        self.assertIn(item["uid"], active["equipped_uids"])
        self.assertTrue(
            active["stats"], "the selected real item must contribute a qualified effect"
        )
        saved_builds = saved["builds"]

        # Model a durable class change, then hydrate only through Store.character.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET breed=%s WHERE id=%s",
                (changed_breed, character["id"]),
            )
        reopened = self.store.character(account, character["id"])
        self.assertEqual(
            reopened["equipment_criterion_context"]["breed_id"], changed_breed
        )
        self.assertEqual(reopened["builds"], saved_builds)
        effective = effective_character(reopened)
        self.assertEqual(effective["equipment_stats"], {})
        resolution = equipment.resolve_sheet(
            reopened, bytes.fromhex(reopened["builds"][0]["equipment"])
        )
        self.assertEqual(resolution["entries"], [])
        self.assertEqual(
            equipment.physical_sheet(
                reopened, bytes.fromhex(reopened["builds"][0]["equipment"])
            ),
            [dict(uid=item["uid"], slot=slot, _level_ineligible=False)],
        )

        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            self.store.save_build(account, generation, character["id"], 0, blobs)
        unchanged = self.store.character(account, character["id"])
        self.assertEqual(unchanged["builds"], saved_builds)
        self.assertTrue(
            any(row["uid"] == item["uid"] for row in unchanged["inventory_items"])
        )

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET breed=%s WHERE id=%s", (breed, character["id"])
            )
        restored = self.store.character(account, character["id"])
        self.assertEqual(
            equipment.resolve_sheet(
                restored, bytes.fromhex(restored["builds"][0]["equipment"])
            )["entries"],
            [dict(uid=item["uid"], slot=slot)],
        )
        self.assertIn(item["uid"], bonuses(restored)["equipped_uids"])
