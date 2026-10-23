"""Real owned builds and companion gear use ordered native eWR reductions."""
import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import builds, health_store, wire
from wakfu_server.character_levels import XP_BY_LEVEL
from wakfu_server.equipment import RULES
from wakfu_server.equipment_stats import CATALOG, bonuses
from wakfu_server.inventory_items import grant
from wakfu_server.items.equipment_characteristics import native_rows


class EquipmentOrderedReductionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "ordered-equipment-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(
            self.account, "Ordered Equipment", breed=8
        )
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=245 WHERE id=%s",
                (self.character["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[245], self.character["id"]),
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
    def _sheet(character, equipment):
        return dict(
            sheet=b"".join(
                wire.proto_field(tag, value)
                for tag, value in (
                    (8, 0),
                    (18, b"Ordered equipment"),
                    (24, 245),
                    (56, 0),
                )
            ),
            equipment=equipment,
            deck=b"",
            aptitudes=b"",
        )

    @staticmethod
    def _equipment(entries):
        return b"".join(
            wire.proto_field(10, wire.proto_field(8, uid) + wire.proto_field(16, slot))
            for slot, uid in sorted(entries.items())
            if uid is not None
        )

    @staticmethod
    def _player_snapshot(character, account):
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import build_player_snapshot

        actor = Actor(
            character["id"],
            0,
            (0, 0, 0),
            character["hp"],
            6,
            3,
            0,
            245,
            account,
            True,
            max_hp=character["max_hp"],
        )
        return build_player_snapshot(
            character, actor, wp_current=6, wp_maximum=6, running_effects=()
        )

    def test_player_mixed_order_reaches_snapshot_and_rebuilds_after_removal(self):
        from wakfu_server.equipment_stats import scalar_reduction

        for reference, runner, stat, amount in (
            (24009, "eWR", 27, 20),
            (2026, "eWQ", 27, 5),
        ):
            self.assertTrue(RULES[reference]["slots"])
            matching = [
                row
                for row in CATALOG[reference]["effects"]
                if row.get("runner") == runner and row.get("stat_id") == stat
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(
                (matching[0]["runner"], matching[0]["stat_id"]), (runner, stat)
            )
            if runner == "eWR":
                self.assertTrue(scalar_reduction(matching[0]))
            self.assertEqual(matching[0]["values"], [amount])

        reduction_slot = RULES[24009]["slots"][0]
        positive_slot = RULES[2026]["slots"][0]
        self.assertEqual((positive_slot, reduction_slot), (0, 15))
        reduction = self._grant(24009, 0)
        positive = self._grant(2026, 1)
        character = health_store.initialize(
            self.store, self.account, self.generation, self.character["id"]
        )
        native = native_rows()[27]
        initial = native["current"]

        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(
                character,
                self._equipment(
                    {reduction_slot: reduction["uid"], positive_slot: positive["uid"]}
                ),
            ),
        )
        # Slot 0 adds before slot 15 subtracts, matching the native slot walk.
        expected = min(native["maximum"], initial + 5)
        expected = max(native["minimum"], expected - 20)
        self.assertEqual(bonuses(character)["stats"][27], expected - initial)
        self.assertEqual(
            self._player_snapshot(character, self.account).stats[27], expected
        )
        self.assertEqual(
            self.store.character(self.account, character["id"])["builds"],
            character["builds"],
        )

        # Removing the negative weapon operation rebuilds from native baseline;
        # it does not preserve a stale sum from the previous saved sheet.
        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, self._equipment({positive_slot: positive["uid"]})),
        )
        expected_after_reduction_removal = min(native["maximum"], initial + 5)
        self.assertEqual(
            self._player_snapshot(character, self.account).stats[27],
            expected_after_reduction_removal,
        )
        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, builds.EMPTY_EQUIPMENT),
        )
        character = self.store.character(self.account, character["id"])
        self.assertEqual(
            self._player_snapshot(character, self.account).stats[27], initial
        )

    def test_native_dynamic_armor_items_project_reconnect_and_unequip_cleanly(self):
        from wakfu_server.equipment_stats import dynamic_scalar_bonus

        for reference in (29115, 29116):
            with self.subTest(item_ref=reference):
                effects = [
                    effect
                    for effect in CATALOG[reference]["effects"]
                    if dynamic_scalar_bonus(effect) is not None
                ]
                self.assertEqual(len(effects), 1)
                identity, amount = dynamic_scalar_bonus(effects[0])
                self.assertIn(identity, (120, 121))
                slot = RULES[reference]["slots"][0]
                item = self._grant(reference, reference % 12)
                character = health_store.initialize(
                    self.store, self.account, self.generation, self.character["id"]
                )
                before = bonuses(character)["stats"].get(identity, 0)
                character = self.store.save_build(
                    self.account,
                    self.generation,
                    character["id"],
                    0,
                    self._sheet(character, self._equipment({slot: item["uid"]})),
                )
                projected = bonuses(character)["stats"].get(identity, 0)
                self.assertEqual(projected - before, amount)

                reloaded = self.store.character(self.account, character["id"])
                self.assertEqual(bonuses(reloaded)["stats"].get(identity, 0), projected)
                self.assertIn(
                    item["uid"], [row["uid"] for row in reloaded["inventory_items"]]
                )

                cleared = self.store.save_build(
                    self.account,
                    self.generation,
                    character["id"],
                    0,
                    self._sheet(reloaded, builds.EMPTY_EQUIPMENT),
                )
                self.assertEqual(bonuses(cleared)["stats"].get(identity, 0), before)

    def test_native_dynamic_pet_armor_recalculates_at_pet_levels_zero_one_and_fifty(
        self,
    ):
        from wakfu_server.combat_parameters import parameter_value
        from wakfu_server.equipment_stats import dynamic_scalar_bonus

        tested = 0
        for reference in (14152, 24293):
            effects = [
                effect
                for effect in CATALOG.get(reference, {}).get("effects", [])
                if dynamic_scalar_bonus(effect) is not None
            ]
            if not effects:
                continue
            tested += 1
            self.assertIn(22, RULES[reference]["slots"])
            item = self._grant(reference, reference % 13)
            character = health_store.initialize(
                self.store, self.account, self.generation, self.character["id"]
            )
            character = self.store.save_build(
                self.account,
                self.generation,
                character["id"],
                0,
                self._sheet(character, self._equipment({22: item["uid"]})),
            )
            for level in (0, 1, 50):
                with self.subTest(reference=reference, pet_level=level):
                    self._set_pet_level(item["uid"], level)
                    reloaded = self.store.character(self.account, character["id"])
                    pet_item = next(
                        row
                        for row in reloaded["inventory_items"]
                        if row["uid"] == item["uid"]
                    )
                    self.assertEqual(
                        pet_item["pet"]["xp"] // pet_item["pet"]["xp_per_level"], level
                    )
                    projected = bonuses(reloaded)["stats"]
                    for effect in effects:
                        identity, _base_amount = dynamic_scalar_bonus(effect)
                        expected = parameter_value(effect["params"], 0, level)
                        self.assertEqual(projected.get(identity, 0), expected)
        self.assertGreaterEqual(
            tested, 1, "expected a native dynamic armor pet among 14152/24293"
        )

    def test_native_relic_aura_roots_survive_projection_and_snapshot_roles_without_recursion(
        self,
    ):
        from wakfu_server.combat.combat_equipment_snapshot_roles import snapshot_roles
        from wakfu_server.combat.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat.combat_copied_equipment_plan import (
            copied_equipment_plan,
        )

        expected_roots = ((24095, 240698), (24114, 240822), (24361, 252647))
        native = native_copied_equipment_catalog()
        for reference, effect_id in expected_roots:
            with self.subTest(item_reference=reference):
                self.assertIn(
                    effect_id,
                    [
                        root["reference"]
                        for root in copied_equipment_plan(reference, native)["roots"]
                    ],
                )
                slot = RULES[reference]["slots"][0]
                item = self._grant(reference, reference % 11)
                character = health_store.initialize(
                    self.store, self.account, self.generation, self.character["id"]
                )
                baseline_stats = self._player_snapshot(character, self.account).stats
                character = self.store.save_build(
                    self.account,
                    self.generation,
                    character["id"],
                    0,
                    self._sheet(character, self._equipment({slot: item["uid"]})),
                )
                projected = bonuses(character)
                retained = [
                    row
                    for row in projected["unsupported"]
                    if row.get("uid") == item["uid"]
                    and row.get("effect_id") == effect_id
                ]
                self.assertEqual(len(retained), 1)
                roles = snapshot_roles(character, projected["unsupported"])
                self.assertEqual(
                    roles[(item["uid"], reference, effect_id, 400)],
                    "native-relic-aura-no-static-characteristic",
                )
                reloaded = self.store.character(self.account, character["id"])
                self.assertEqual(bonuses(reloaded), projected)
                self._player_snapshot(reloaded, self.account)

                cleared = self.store.save_build(
                    self.account,
                    self.generation,
                    reloaded["id"],
                    0,
                    self._sheet(reloaded, builds.EMPTY_EQUIPMENT),
                )
                self.assertEqual(
                    self._player_snapshot(cleared, self.account).stats,
                    baseline_stats,
                )

    def test_native_pet_dynamic_armor_recalculates_at_actual_pet_levels(self):
        from wakfu_server.combat_parameters import parameter_value
        from wakfu_server.equipment_stats import dynamic_scalar_bonus

        references = (14152, 24293)
        tested = 0
        for reference in references:
            effects = [
                effect
                for effect in CATALOG.get(reference, {}).get("effects", [])
                if dynamic_scalar_bonus(effect) is not None
            ]
            if not effects:
                continue
            tested += 1
            self.assertIn(22, RULES[reference]["slots"])
            item = self._grant(reference, 9)
            character = health_store.initialize(
                self.store, self.account, self.generation, self.character["id"]
            )
            character = self.store.save_build(
                self.account,
                self.generation,
                character["id"],
                0,
                self._sheet(character, self._equipment({22: item["uid"]})),
            )
            for level in (0, 1, 50):
                with self.subTest(reference=reference, pet_level=level):
                    self._set_pet_level(item["uid"], level)
                    reloaded = self.store.character(self.account, character["id"])
                    pet_item = next(
                        row
                        for row in reloaded["inventory_items"]
                        if row["uid"] == item["uid"]
                    )
                    self.assertEqual(
                        pet_item["pet"]["xp"] // pet_item["pet"]["xp_per_level"], level
                    )
                    projected = bonuses(reloaded)["stats"]
                    for effect in effects:
                        identity, _ = dynamic_scalar_bonus(effect)
                        amount = parameter_value(effect["params"], 0, level)
                        self.assertEqual(projected.get(identity, 0), amount)
        self.assertGreaterEqual(
            tested, 1, "expected a native dynamic armor pet among the audited refs"
        )

    def test_getcharac_precheck_and_postprojection_accept_native_4224(self):
        from wakfu_server.equipment_conditions import catalog

        reference = 4224
        slot = RULES[reference]["slots"][0]
        self.assertEqual(
            catalog()[str(reference)]["EQUIP"], 'GetCharac("FEROCITY") > -10'
        )
        item = self._grant(reference, 0)
        character = health_store.initialize(
            self.store, self.account, self.generation, self.character["id"]
        )
        initial = native_rows()[9]["current"]
        self.assertEqual(initial, 3)
        self.assertGreater(initial, -10)

        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, self._equipment({slot: item["uid"]})),
        )
        self.assertEqual(bonuses(character)["stats"][9], -10)
        self.assertEqual(self._player_snapshot(character, self.account).stats[9], -7)

        # Reconnect projection retains the selected unit and its own eWR delta.
        character = self.store.character(self.account, character["id"])
        self.assertEqual(bonuses(character)["stats"][9], -10)
        self.assertEqual(self._player_snapshot(character, self.account).stats[9], -7)
        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, builds.EMPTY_EQUIPMENT),
        )
        self.assertEqual(
            self._player_snapshot(character, self.account).stats[9], initial
        )

    def test_native_pet_getcharac_reconciles_without_deleting_physical_unit(self):
        from wakfu_server.equipment_conditions import catalog

        reference = 32245
        slot = RULES[reference]["slots"][0]
        self.assertEqual(slot, 22)
        self.assertIn("GetCharac", catalog()[str(reference)]["EQUIP"])
        item = self._grant(reference, 5)
        character = health_store.initialize(
            self.store, self.account, self.generation, self.character["id"]
        )
        self._set_pet_level(item["uid"], 1)
        character = self.store.character(self.account, character["id"])
        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, self._equipment({slot: item["uid"]})),
        )
        self.assertEqual(bonuses(character)["stats"].get(9), -1)

        # The same physical unit stays in the saved sheet while its native
        # GetCharac predicate becomes false at level 25. Reconciliation must
        # undo the clipped operation that was actually applied.
        self._set_pet_level(item["uid"], 25)
        character = self.store.character(self.account, character["id"])
        self.assertIn(item["uid"], [row["uid"] for row in character["inventory_items"]])
        self.assertEqual(bonuses(character)["stats"].get(9, 0), 0)
        from wakfu_server.equipment import physical_sheet

        self.assertIn(
            item["uid"],
            [
                row["uid"]
                for row in physical_sheet(
                    character, bytes.fromhex(character["builds"][0]["equipment"])
                )
            ],
        )

        # A later valid pet level starts from the persisted physical sheet and
        # evaluates against a fresh native baseline; the earlier temporary
        # reconciliation does not leave a stale inverse in the character.
        self._set_pet_level(item["uid"], 1)
        character = self.store.character(self.account, character["id"])
        self.assertEqual(bonuses(character)["stats"].get(9), -1)

    def test_native_pet_reduction_uses_actual_xp_level_and_bounds(self):
        from wakfu_server.combat_parameters import parameter_value
        from wakfu_server.equipment_characteristics import apply_scalar
        from wakfu_server.equipment_conditions import catalog

        reference, stat_id = 32246, 11
        slot = RULES[reference]["slots"][0]
        self.assertEqual(slot, 22)
        self.assertNotIn("GetCharac", catalog()[str(reference)].get("EQUIP") or "")
        effect = next(
            effect
            for effect in CATALOG[reference]["effects"]
            if effect.get("runner") == "eWR" and effect.get("stat_id") == stat_id
        )
        item = self._grant(reference, 6)
        character = health_store.initialize(
            self.store, self.account, self.generation, self.character["id"]
        )
        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, self._equipment({slot: item["uid"]})),
        )
        native = native_rows()[stat_id]
        for level in (1, 25, 50):
            with self.subTest(pet_level=level):
                self._set_pet_level(item["uid"], level)
                character = self.store.character(self.account, character["id"])
                value = parameter_value(effect["params"], 0, level)
                expected = apply_scalar(native["current"], native, value, True)
                expected_delta = expected - native["current"]
                self.assertEqual(
                    bonuses(character)["stats"].get(stat_id), expected_delta
                )
                self.assertIn(
                    item["uid"], [row["uid"] for row in character["inventory_items"]]
                )

    def test_two_native_ferocity_reducers_reconcile_by_fifo_inverse_and_keep_units(
        self,
    ):
        from wakfu_server.equipment import physical_sheet
        from wakfu_server.equipment_conditions import catalog

        # Both native pieces require FEROCITY > -10. The slot-0 reducer takes
        # the combined projection below that threshold; removing its actual
        # clipped contribution makes the later slot-15 reducer valid again.
        for reference in (4224, 14656):
            self.assertEqual(
                catalog()[str(reference)]["EQUIP"], 'GetCharac("FEROCITY") > -10'
            )
            self.assertEqual(
                len(
                    [
                        effect
                        for effect in CATALOG[reference]["effects"]
                        if effect.get("runner") == "eWR" and effect.get("stat_id") == 9
                    ]
                ),
                1,
            )
        first_slot, second_slot = RULES[4224]["slots"][0], RULES[14656]["slots"][0]
        self.assertEqual((first_slot, second_slot), (0, 15))
        second = self._grant(14656, 7)
        first = self._grant(4224, 8)
        character = health_store.initialize(
            self.store, self.account, self.generation, self.character["id"]
        )
        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, self._equipment({second_slot: second["uid"]})),
        )
        self.assertEqual(bonuses(character)["stats"].get(9), -5)

        candidate_blob = self._equipment(
            {first_slot: first["uid"], second_slot: second["uid"]}
        )
        candidate = dict(
            character,
            builds={
                **character["builds"],
                0: {**character["builds"][0], "equipment": candidate_blob.hex()},
            },
        )
        from wakfu_server.equipment import physical_sheet

        candidate_entries = physical_sheet(candidate, candidate_blob)
        candidate_bonuses = bonuses(candidate, _selected_entries=candidate_entries)
        self.assertEqual(candidate_bonuses["unsupported"], [])

        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, candidate_blob),
        )
        self.assertEqual(bonuses(character)["stats"].get(9), -5)
        physical = physical_sheet(
            character, bytes.fromhex(character["builds"][0]["equipment"])
        )
        self.assertEqual(
            {row["uid"] for row in physical}, {first["uid"], second["uid"]}
        )
        self.assertEqual(
            {
                row["uid"]
                for row in character["inventory_items"]
                if row["uid"] in (first["uid"], second["uid"])
            },
            {first["uid"], second["uid"]},
        )
        self.assertEqual(
            bonuses(self.store.character(self.account, character["id"]))["stats"].get(
                9
            ),
            -5,
        )

    def test_getcharac_candidate_below_native_threshold_rejects_atomically(self):
        from wakfu_server.equipment_conditions import catalog
        from wakfu_server.element_selection import select as select_elements

        # The native gate requires FEROCITY in [40, 50]. Supported equipment
        # puts this character at 35; the candidate must not be admitted by
        # evaluating its own effects before checking the native predicate.
        support = ((22126, 17), (2021, 4))
        items = {reference: self._grant(reference, slot) for reference, slot in support}
        candidate = self._grant(26302, 13)
        select_elements(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qBB", candidate["uid"], 14, 0),
        )
        self.assertEqual(
            catalog()["26302"]["EQUIP"],
            'GetCharac("FEROCITY") >= 40 && GetCharac("FEROCITY") <= 50',
        )
        character = health_store.initialize(
            self.store, self.account, self.generation, self.character["id"]
        )
        support_entries = {slot: items[reference]["uid"] for reference, slot in support}
        character = self.store.save_build(
            self.account,
            self.generation,
            character["id"],
            0,
            self._sheet(character, self._equipment(support_entries)),
        )
        native = native_rows()[9]["current"]
        self.assertEqual(native, 3)
        self.assertEqual(bonuses(character)["stats"][9], 32)
        before = character["builds"][0]["equipment"]
        proposed = {**support_entries, 13: candidate["uid"]}
        with self.assertRaisesRegex(ValueError, "pre-application criteria"):
            self.store.save_build(
                self.account,
                self.generation,
                character["id"],
                0,
                self._sheet(character, self._equipment(proposed)),
            )
        saved = self.store.character(self.account, character["id"])
        self.assertEqual(saved["builds"][0]["equipment"], before)
        self.assertTrue(
            all(
                any(row["uid"] == item["uid"] for row in saved["inventory_items"])
                for item in (*items.values(), candidate)
            )
        )

    def test_companion_getcharac_precheck_uses_native_default_emblem_then_reconnects(
        self,
    ):
        from wakfu_server.companions import (
            add_to_party,
            combat_sources,
            descriptors,
            use,
        )
        from wakfu_server.companion_equipment import save, retrieve_all
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values
        from wakfu_server.combat_companions import default_equipment_bonuses
        from wakfu_server.equipment_characteristics import apply_scalar

        descriptor = next(
            row for row in descriptors().values() if row["item_ref"] == 17878
        )
        activation = self._grant(descriptor["item_ref"], 9)
        companion = use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], activation["uid"]),
            in_fight=False,
        )["companion"]
        level = 200
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[level], companion["id"]),
            )
        owner = self.store.character(self.account, self.character["id"])
        baseline = {
            identity: row["current"]
            for identity, row in native_npc_creation_values(
                companion["breed_ref"], level
            ).items()
        }
        defaults = default_equipment_bonuses(level)
        self.assertGreater(defaults.get(9, 0), 0)
        pre_item = baseline[9] + defaults.get(9, 0)
        ferocity = native_rows()[9]
        pre_item = min(ferocity["maximum"], max(ferocity["minimum"], pre_item))
        self.assertGreater(pre_item, -10)

        item = self._grant(4224, 10)
        add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
        )
        save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], [(RULES[4224]["slots"][0], item["uid"])]),
            in_fight=False,
        )
        with self.store.connection() as db:
            sources = combat_sources(
                db, self.account, self.character["id"], store=self.store
            )
        source = next(row for row in sources if row["id"] == companion["id"])
        self.assertEqual(
            source["equipment_entries"][0]["entry"]["item"]["uid"], item["uid"]
        )
        expected_after_candidate = apply_scalar(baseline[9], ferocity, 10, True)
        expected_bonus = -10 if expected_after_candidate > -10 else 0
        self.assertEqual(source["equipment_stat_bonuses"].get(9, 0), expected_bonus)

        # The stored custom unit remains physical even when its own post-state
        # fails; reconnect projection uses the same NPC baseline and inverse.
        with self.store.connection() as db:
            reloaded = next(
                row
                for row in combat_sources(
                    db, self.account, self.character["id"], store=self.store
                )
                if row["id"] == companion["id"]
            )
        self.assertEqual(reloaded["equipment_stat_bonuses"].get(9, 0), expected_bonus)
        retrieve_all(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
            in_fight=False,
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM companion_equipment WHERE companion_id=%s",
                    (companion["id"],),
                ).fetchone()["n"],
                0,
            )
            returned = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
                (item["uid"], self.character["id"]),
            ).fetchone()
        self.assertEqual(returned["quantity"], 1)
        with self.store.connection() as db:
            after_retrieve = next(
                row
                for row in combat_sources(
                    db, self.account, self.character["id"], store=self.store
                )
                if row["id"] == companion["id"]
            )
        self.assertEqual(tuple(after_retrieve["equipment_entries"]), ())
        self.assertEqual(after_retrieve["equipment_stat_bonuses"], defaults)

    def _set_pet_level(self, uid, level):
        with self.store.connection() as db:
            model = db.execute(
                "SELECT model.xp_per_level FROM inventory_pets pet "
                "JOIN native_pet_models model USING(model_id) WHERE pet.uid=%s",
                (uid,),
            ).fetchone()
            self.assertIsNotNone(model)
            db.execute(
                "UPDATE inventory_pets SET xp=%s WHERE uid=%s",
                (model["xp_per_level"] * level, uid),
            )

    def test_companion_uses_its_own_native_baseline_for_the_same_mixed_pair(self):
        from wakfu_server.companions import (
            add_to_party,
            combat_sources,
            descriptors,
            use,
        )
        from wakfu_server.companion_equipment import save, retrieve_all
        from wakfu_server.combat_companions import companion_actor, native_stats

        descriptor = next(
            row for row in descriptors().values() if row["item_ref"] == 17878
        )
        activation = self._grant(descriptor["item_ref"], 2)
        companion = use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], activation["uid"]),
            in_fight=False,
        )["companion"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[245], companion["id"]),
            )
        owner = self.store.character(self.account, self.character["id"])
        add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
        )

        with self.store.connection() as db:
            base_sources = combat_sources(
                db, self.account, self.character["id"], store=self.store
            )
        base_source = next(row for row in base_sources if row["id"] == companion["id"])
        baseline_bonus = base_source["equipment_stat_bonuses"].get(27, 0)

        reduction_slot = RULES[24009]["slots"][0]
        positive_slot = RULES[2026]["slots"][0]
        reduction = self._grant(24009, 3)
        positive = self._grant(2026, 4)
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values

        npc_values = native_npc_creation_values(companion["breed_ref"], 245)
        npc_baseline = npc_values[27]["current"]
        player_values = native_rows()
        self.assertTrue(
            any(
                identity in player_values
                and npc_values[identity]["current"] != row["current"]
                for identity, row in player_values.items()
            )
        )
        save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(
                companion["id"],
                [(reduction_slot, reduction["uid"]), (positive_slot, positive["uid"])],
            ),
            in_fight=False,
        )
        with self.store.connection() as db:
            sources = combat_sources(
                db, self.account, self.character["id"], store=self.store
            )
        source = next(row for row in sources if row["id"] == companion["id"])
        expected = min(native_rows()[27]["maximum"], npc_baseline + 5)
        expected = max(native_rows()[27]["minimum"], expected - 20)
        self.assertEqual(source["equipment_stat_bonuses"][27], expected - npc_baseline)
        projected = native_stats(
            companion["breed_ref"],
            245,
            equipment_entries=source["equipment_entries"],
            owner=owner,
        )
        actor = companion_actor(source, team=0)
        self.assertEqual(actor.effect_stats[27], expected)
        self.assertEqual(
            projected["initiative"],
            __import__("wakfu_server.monsters", fromlist=["statistics"]).statistics(
                companion["breed_ref"], 245
            )["INIT"]
            + source["equipment_stat_bonuses"].get(35, 0),
        )

        retrieve_all(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
            in_fight=False,
        )
        with self.store.connection() as db:
            restored_sources = combat_sources(
                db, self.account, self.character["id"], store=self.store
            )
        restored = next(row for row in restored_sources if row["id"] == companion["id"])
        self.assertEqual(restored["equipment_stat_bonuses"].get(27, 0), baseline_bonus)
        restored_actor = companion_actor(restored, team=0)
        self.assertEqual(restored_actor.effect_stats[27], npc_baseline + baseline_bonus)
        for item in (reduction, positive):
            row = self.store.character(self.account, self.character["id"])
            self.assertTrue(
                any(i["uid"] == item["uid"] for i in row["inventory_items"])
            )

    @staticmethod
    def _save_body(identity, entries):
        body = bytearray(struct.pack(">qh", identity, len(entries)))
        for slot, uid in entries:
            body.extend(struct.pack(">Bbq", 1, slot, uid))
        return bytes(body)


if __name__ == "__main__":
    unittest.main()
