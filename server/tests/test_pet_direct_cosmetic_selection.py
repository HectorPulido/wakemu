"""Complete pet/direct-skin preset selection while preserving physical game state."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.characters.cosmetics import OwnedCosmetics, finisher_request
from wakfu_server.equipment_appearance import rows, change_packet
from wakfu_server.wire import proto_field


def request(record, actor, category, reference=None, *, add=True):
    payload = struct.pack(">iiBB", 1, category, int(add), int(reference is not None))
    if reference is not None:
        payload += proto_field(8, reference)
    return finisher_request(record, actor, 13765, payload)


class PetDirectCosmeticTests(unittest.TestCase):
    def character(self):
        return dict(
            id=7,
            account_id=9,
            level=20,
            breed=8,
            active_build_index=0,
            inventory_items=[
                dict(
                    uid=123,
                    character_id=7,
                    reference=2040,
                    quantity=1,
                    appearance_ref=2026,
                )
            ],
            hp=100,
            max_hp=200,
            builds={
                0: dict(
                    sheet=proto_field(24, (1 << 64) - 1).hex(),
                    equipment=proto_field(
                        10, proto_field(8, 123) + proto_field(16, 0)
                    ).hex(),
                )
            },
        )

    def owned(self, actor):
        return (
            OwnedCosmetics(
                9,
                (
                    (2, 28561, 0, 0),
                    (8, 32853, 0, 0),
                    (8, 32901, 0, 0),
                    (11, 32854, 0, 0),
                    (12, 32855, 0, 0),
                    (3, 9727, 0, 0),
                    (5, 20753, 0, 0),
                ),
            )
            .equip_finishers(actor, (20753,))
            .equip_costume(actor, 9727)
        )

    def test_direct_skins_override_mimibionte_and_empty_slots_without_changing_any_equipment(
        self,
    ):
        actor = self.character()
        before = deepcopy(actor)
        record = self.owned(actor)
        for category, reference in ((8, 32853), (11, 32854), (12, 32855)):
            record = request(record, actor, category, reference)
        visible = dict(actor, owned_cosmetics=record.to_record())
        self.assertEqual(
            rows(visible), ((0, 2040, 32853), (12, 0, 32855), (13, 0, 32854))
        )
        self.assertEqual(actor, before)
        self.assertEqual(record.selected_costume(7), 9727)
        self.assertEqual(record.selected_finishers(7), (20753,))
        replaced = request(record, actor, 8, 32901)
        self.assertEqual(
            rows(dict(actor, owned_cosmetics=replaced.to_record()))[0], (0, 2040, 32901)
        )
        cleared = request(replaced, actor, 8, None, add=False)
        self.assertEqual(
            rows(dict(actor, owned_cosmetics=cleared.to_record()))[0], (0, 2040, 2026)
        )
        inactive = record.activate_preset(actor, False)
        restored = record.activate_preset(actor, False).activate_preset(actor, True)
        self.assertEqual(
            rows(dict(actor, owned_cosmetics=inactive.to_record())), ((0, 2040, 2026),)
        )
        self.assertEqual(
            rows(dict(actor, owned_cosmetics=restored.to_record())), rows(visible)
        )
        packet = change_packet(
            visible, dict(actor, owned_cosmetics=inactive.to_record())
        )
        self.assertEqual(
            packet,
            (
                13060,
                struct.pack(">qB", 7, 3)
                + struct.pack(">Bii", 0, 2040, 2026)
                + struct.pack(">Bii", 12, 0, 0)
                + struct.pack(">Bii", 13, 0, 0),
            ),
        )

    def test_pet_skin_requires_physical_equipped_pet_and_never_changes_its_xp_health_or_identity(
        self,
    ):
        from wakfu_server.pet_inventory import actor_pet

        actor = self.character()
        record = request(self.owned(actor), actor, 2, 28561)
        visible = dict(actor, owned_cosmetics=record.to_record())
        state = dict(
            definition_id=0,
            color_item_ref=10,
            equipped_item_ref=20,
            sleep_item_ref=30,
            health=50,
            reskin_item_ref=0,
            xp=1234,
        )
        unit = dict(uid=5, reference=12237, pet=state)
        original = deepcopy(unit)
        with patch("wakfu_server.pet_inventory.equipped", return_value=None):
            self.assertEqual(actor_pet(visible), b"\0")
        with patch("wakfu_server.pet_inventory.equipped", return_value=unit):
            self.assertEqual(
                actor_pet(visible), b"\1" + struct.pack(">6i", 0, 0, 28561, 30, 50, 0)
            )
            cleared = request(record, actor, 2, 28561, add=False)
            self.assertEqual(
                actor_pet(dict(actor, owned_cosmetics=cleared.to_record())),
                b"\1" + struct.pack(">6i", 0, 10, 20, 30, 50, 0),
            )
        self.assertEqual(unit, original)

    def test_unowned_category_operands_and_malformed_requests_cannot_create_selections(
        self,
    ):
        actor = self.character()
        record = self.owned(actor)
        for category, reference in (
            (2, 32853),
            (8, 28561),
            (8, 999999),
            (16, 32853),
            (15, 32853),
        ):
            with self.assertRaises(ValueError):
                request(record, actor, category, reference)
        with self.assertRaises(ValueError):
            finisher_request(
                record,
                actor,
                13765,
                struct.pack(">iiBB", 1, 2, 1, 1)
                + proto_field(8, 28561)
                + proto_field(24, 123),
            )
        with self.assertRaises(ValueError):
            request(record, dict(actor, account_id=10), 2, 28561)

    def test_fresh_combat_cosmetic_lists_include_pet_and_direct_skins_without_changing_esu_layout(
        self,
    ):
        from wakfu_server.combat_cosmetic_conditions import fresh_player_cosmetic_state

        actor = self.character()
        record = request(request(self.owned(actor), actor, 2, 28561), actor, 8, 32853)
        fresh = fresh_player_cosmetic_state(
            dict(actor, owned_cosmetics=record.to_record())
        )
        self.assertEqual(set(fresh["selected_values"]), {3, 4, 5, 6, 7})
        self.assertEqual(fresh["active_cosmetics"][2], (28561,))
        self.assertEqual(fresh["active_cosmetics"][8], (32853,))
        inactive = fresh_player_cosmetic_state(
            dict(
                actor, owned_cosmetics=record.activate_preset(actor, False).to_record()
            )
        )
        self.assertNotIn(2, inactive["active_cosmetics"])
        self.assertNotIn(8, inactive["active_cosmetics"])


class PetDirectCosmeticPostgresTests(PostgresCase):
    def fixture(self):
        account = self.store.register("pet-direct-owner", "local-password")["id"]
        actor = self.store.create_character(account, "Pet Direct Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        # Compare subsequent writes against the hydrated persisted baseline;
        # create_character's return value intentionally omits synthesized
        # default-sheet data that Store.character publishes on reload.
        actor = self.reopen().character(account, actor["id"])
        return account, generation, actor

    def test_all_283_real_catalog_items_select_owned_native_categories_and_persist(
        self,
    ):
        from wakfu_server.characters.cosmetic_store import equip_finishers

        account, generation, actor = self.fixture()
        with self.store.connection() as db:
            plans = list(
                db.execute(
                    "SELECT * FROM native_cosmetic_learning_actions WHERE category IN (2,8,11,12) ORDER BY category,item_ref"
                )
            )
        self.assertEqual(len(plans), 283)
        record = OwnedCosmetics(
            account, tuple((row["category"], row["item_ref"], 0, 0) for row in plans)
        ).equip_finishers(actor, ())
        for plan in plans:
            record = request(record, actor, plan["category"], plan["item_ref"])
            self.assertEqual(
                record.selected_single(actor["id"], plan["category"]), plan["item_ref"]
            )
        from psycopg.types.json import Jsonb

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s)",
                (account, Jsonb(record.to_record())),
            )
            equip_finishers(db, actor, (), updated_record=record)
        restored = self.reopen().character(account, actor["id"])
        self.assertEqual(
            OwnedCosmetics.from_record(restored["owned_cosmetics"], account_id=account),
            record,
        )
        for key in ("hp", "max_hp", "level", "builds", "inventory_items"):
            self.assertEqual(restored[key], actor[key], key)

    def test_real_learning_then_selection_for_each_new_category_preserves_source_consumption_and_character_stats(
        self,
    ):
        from wakfu_server.inventory_items import grant
        from wakfu_server.cosmetic_learning import learn_item

        account, generation, actor = self.fixture()
        with self.store.connection() as db:
            plans = list(
                db.execute(
                    "SELECT DISTINCT ON(category) * FROM native_cosmetic_learning_actions WHERE category IN(2,8,11,12) ORDER BY category,item_ref"
                )
            )
        baseline_builds = actor["builds"]
        for slot, plan in enumerate(plans):
            item = grant(
                self.store,
                account,
                generation,
                actor["id"],
                reference=plan["item_ref"],
                quantity=2,
                container=actor["inventory_containers"][0]["uid"],
                slot=slot,
                allowed_references={plan["item_ref"]},
            )
            outcome = learn_item(
                self.store,
                account,
                generation,
                actor["id"],
                struct.pack(">iq", plan["action_id"], item["uid"]),
            )
            self.assertTrue(outcome["applied"])
            updated = self.store.equip_owned_finishers(
                account,
                actor["id"],
                13765,
                struct.pack(">iiBB", 1, plan["category"], 1, 1)
                + proto_field(8, plan["item_ref"]),
            )
            self.assertEqual(updated["builds"], baseline_builds)
            self.assertEqual(
                (updated["hp"], updated["max_hp"]), (actor["hp"], actor["max_hp"])
            )
            self.assertEqual(
                next(
                    row["quantity"]
                    for row in updated["inventory_items"]
                    if row["uid"] == item["uid"]
                ),
                1,
            )
            self.assertEqual(
                OwnedCosmetics.from_record(
                    updated["owned_cosmetics"], account_id=account
                ).selected_single(actor["id"], plan["category"]),
                plan["item_ref"],
            )
        # The same native slot selection must also accept real Transespejo
        # knowledge, rather than only bIt appearance-learning items.
        from wakfu_server.mimisymbic_learning import learn as learn_mirror

        target = grant(
            self.store,
            account,
            generation,
            actor["id"],
            reference=2040,
            quantity=1,
            container=actor["inventory_containers"][0]["uid"],
            slot=4,
            allowed_references={2040},
        )
        mirror = grant(
            self.store,
            account,
            generation,
            actor["id"],
            reference=31508,
            quantity=1,
            container=actor["inventory_containers"][0]["uid"],
            slot=5,
            allowed_references={31508},
        )
        learned = learn_mirror(
            self.store,
            account,
            generation,
            actor["id"],
            struct.pack(">iqq", 13882, mirror["uid"], target["uid"]),
        )
        self.assertTrue(learned["applied"])
        updated = self.store.equip_owned_finishers(
            account,
            actor["id"],
            13765,
            struct.pack(">iiBB", 1, 8, 1, 1) + proto_field(8, 2040),
        )
        self.assertEqual(
            OwnedCosmetics.from_record(
                updated["owned_cosmetics"], account_id=account
            ).selected_single(actor["id"], 8),
            2040,
        )
        preserved = next(
            row for row in updated["inventory_items"] if row["uid"] == target["uid"]
        )
        self.assertEqual((preserved["reference"], preserved["quantity"]), (2040, 1))
        self.assertEqual(updated["builds"], baseline_builds)
