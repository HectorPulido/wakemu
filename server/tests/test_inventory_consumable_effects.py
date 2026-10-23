"""Transactional use of persisted native buff foods through opcode12659."""
import struct

from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.inventory_items import grant
from wakfu_server.consumable_buffs import snapshot
from wakfu_server import health_store
from wakfu_server.inventory_consumable_effects import use
from wakfu_server.consumable_buff_wire import delta as consumable_delta
from wakfu_server.consumable_world_lifecycle import synchronize
from wakfu_server.consumable_buffs import apply_states, retire_states
from wakfu_server.consumable_characteristics import reconcile_health
from wakfu_server.health_policy import apply_damage
from wakfu_server.wire import owned_public_characteristics


class InventoryConsumableEffectPostgresTests(PostgresCase):
    def actor(self, username):
        account = self.store.register(username, "local-password")["id"]
        character = self.store.create_character(account, f"Owner {username}")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, character, generation

    def grant_item(self, account, character, generation, reference, quantity=1):
        character = self.store.character(account, character["id"])
        container = next(
            row["uid"] for row in character["inventory_containers"] if row["kind"] == 0
        )
        occupied = {
            row["slot"]
            for row in character["inventory_items"]
            if row["container"] == container
        }
        slot = next(index for index in range(5) if index not in occupied)
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=quantity,
            container=container,
            slot=slot,
            allowed_references={reference},
        )

    def test_state_food_consumes_one_unit_and_persists_exact_native_state(self):
        account, character, generation = self.actor("buff-food")
        source = self.grant_item(account, character, generation, 3663, quantity=2)

        result = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=character["hp"],
            in_fight=False,
        )

        self.assertTrue(result["native_consumable"])
        with self.store.connection() as db:
            anchor = db.execute(
                "SELECT online_anchor_ms FROM character_consumable_buffs WHERE character_id=%s",
                (character["id"],),
            ).fetchone()["online_anchor_ms"]
        states = snapshot(
            self.store, character["id"], generation=generation, now_ms=anchor
        )
        self.assertEqual(len(states), 1)
        self.assertEqual(
            (
                states[0]["source_item_ref"],
                states[0]["source_item_uid"],
                states[0]["state_id"],
                states[0]["level"],
                states[0]["clock"],
                states[0]["duration_ms"],
                states[0]["remaining_ms"],
                states[0]["effect_ids"],
            ),
            (
                3663,
                source["uid"],
                1210,
                10,
                "online",
                900_000,
                900_000,
                [64544, 64545, 64546],
            ),
        )
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(
            [(item["uid"], item["quantity"]) for item in reopened["inventory_items"]],
            [(source["uid"], 1)],
        )

    def test_event_counter_food_keeps_its_own_marker_and_adds_on_second_use(self):
        account, character, generation = self.actor("buff-event-counter")
        source = self.grant_item(account, character, generation, 5010, quantity=2)

        first = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=character["hp"],
            in_fight=False,
        )
        self.assertTrue(first["native_consumable"])
        first_packets = consumable_delta(
            first["previous_character"],
            first["character"],
            allocate_action=lambda: 700,
        )
        self.assertEqual([opcode for opcode, _ in first_packets], [12613, 13420])
        self.assertIn(b"\x98\xf8\xff\xff\xff\xff\xff\xff\xff\x01", first_packets[0][1])
        initial = snapshot(self.store, character["id"])
        self.assertEqual(
            [(state["state_id"], state["clock"], state["level"]) for state in initial],
            [(4436, "event", 5)],
        )

        second = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=character["hp"],
            in_fight=False,
        )
        self.assertTrue(second["native_consumable"])
        second_packets = consumable_delta(
            second["previous_character"],
            second["character"],
            allocate_action=lambda: 701,
        )
        self.assertEqual(
            [opcode for opcode, _ in second_packets], [13560, 12613, 13420]
        )
        accumulated = snapshot(self.store, character["id"])
        self.assertEqual(
            [
                (state["uid"], state["state_id"], state["clock"], state["level"])
                for state in accumulated
            ],
            [(initial[0]["uid"], 4436, "event", 10)],
        )
        reopened = self.reopen().character(account, character["id"])
        self.assertNotIn(
            source["uid"], {item["uid"] for item in reopened["inventory_items"]}
        )

    def test_active_hero_consumable_keeps_main_session_and_hero_owner_separate(self):
        account, main, generation = self.actor("buff-active-hero")
        hero = self.store.create_character(account, "Consumable Hero")
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        source = self.grant_item(account, hero, generation, 3663)
        main_before = self.store.character(account, main["id"])
        hero_before = self.store.character(account, hero["id"])

        result = use(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=main["hp"],
            in_fight=False,
        )

        self.assertEqual(result["character"]["id"], hero["id"])
        self.assertEqual(
            (result["character"]["map_id"], result["character"]["instance_id"]),
            (hero_before["map_id"], hero_before["instance_id"]),
        )
        self.assertEqual(
            (
                self.store.character(account, main["id"])["map_id"],
                self.store.character(account, main["id"])["instance_id"],
            ),
            (main_before["map_id"], main_before["instance_id"]),
        )
        with self.store.connection() as db:
            selected = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (account,)
            ).fetchone()["character_id"]
        self.assertEqual(selected, main["id"])
        self.assertEqual(snapshot(self.store, hero["id"])[0]["state_id"], 1210)
        self.assertEqual(snapshot(self.store, main["id"]), ())

    def test_world_lifecycle_logout_pause_and_new_generation_resume(self):
        account, character, generation = self.actor("buff-lifecycle-resume")
        source = self.grant_item(account, character, generation, 3663)
        applied = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=character["hp"],
            in_fight=False,
        )
        live = dict(applied["character"], position_x=7, position_y=9)

        paused = synchronize(self.store, account, generation, live, mode="pause")
        self.assertEqual((paused["position_x"], paused["position_y"]), (7, 9))
        with self.store.connection() as db:
            row = db.execute(
                "SELECT online_generation FROM character_consumable_buffs WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
        self.assertIsNone(row["online_generation"])

        replacement_generation = self.store.begin_session(account)
        self.store.select_character(account, replacement_generation, character["id"])
        resumed = synchronize(
            self.store, account, replacement_generation, paused, mode="resume"
        )
        self.assertEqual(
            (resumed["map_id"], resumed["instance_id"]),
            (paused["map_id"], paused["instance_id"]),
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT online_generation,remaining_ms FROM character_consumable_buffs WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
        self.assertEqual(row["online_generation"], replacement_generation)
        self.assertGreater(row["remaining_ms"], 0)

    def test_world_lifecycle_checkpoints_only_active_company_heroes(self):
        self.store.clock = lambda: 1_000
        account, main, generation = self.actor("buff-company-clock")
        hero = self.store.create_character(account, "Buff Company Hero")
        inactive = self.store.create_character(account, "Buff Inactive Hero")
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        source = self.grant_item(account, hero, generation, 3663)
        used = use(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=main["hp"],
            in_fight=False,
        )
        self.assertEqual(used["character"]["id"], hero["id"])
        main_live = self.store.character(account, main["id"])
        with self.store.connection() as db:
            descriptor = db.execute(
                "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=20034"
            ).fetchone()["state"]
            apply_states(
                self.store,
                db,
                inactive["id"],
                [descriptor],
                source_item_ref=20034,
                source_item_uid=20034,
                generation=generation,
            )

        self.store.clock = lambda: 1_002
        paused = synchronize(self.store, account, generation, main_live, mode="pause")
        self.assertEqual(paused["id"], main["id"])
        replacement = self.store.begin_session(account)
        self.store.select_character(account, replacement, main["id"])
        self.store.clock = lambda: 1_100
        resumed = synchronize(self.store, account, replacement, paused, mode="resume")
        self.store.clock = lambda: 1_101
        ticked = synchronize(self.store, account, replacement, resumed, mode="tick")
        self.assertEqual(
            (ticked["map_id"], ticked["instance_id"]),
            (resumed["map_id"], resumed["instance_id"]),
        )
        with self.store.connection() as db:
            active = db.execute(
                "SELECT online_generation,remaining_ms FROM character_consumable_buffs WHERE character_id=%s",
                (hero["id"],),
            ).fetchone()
            untouched = db.execute(
                "SELECT online_generation,remaining_ms FROM character_consumable_buffs WHERE character_id=%s",
                (inactive["id"],),
            ).fetchone()
        self.assertEqual(
            (active["online_generation"], active["remaining_ms"]),
            (replacement, 897_000),
        )
        self.assertEqual(
            (untouched["online_generation"], untouched["remaining_ms"]),
            (generation, 1_800_000),
        )

        stale = synchronize(self.store, account, generation, ticked, mode="pause")
        self.assertEqual(stale, ticked)
        with self.store.connection() as db:
            active = db.execute(
                "SELECT online_generation,remaining_ms FROM character_consumable_buffs WHERE character_id=%s",
                (hero["id"],),
            ).fetchone()
        self.assertEqual(active["online_generation"], replacement)

    def test_rejected_native_state_plan_and_combat_use_do_not_consume(self):
        account, character, generation = self.actor("buff-rejected")
        # 9811 is now qualified as a native event-clock state; 9247 is the
        # explicit empty-effect item retained as an unsupported control.
        unsupported = self.grant_item(account, character, generation, 9247)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", unsupported["uid"], 0),
                expected_hp=character["hp"],
                in_fight=False,
            )
        usable = self.grant_item(account, character, generation, 3663)
        with self.assertRaises(ValueError):
            use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", usable["uid"], 0),
                expected_hp=character["hp"],
                in_fight=True,
            )
        reopened = self.reopen().character(account, character["id"])
        quantities = {
            item["uid"]: item["quantity"] for item in reopened["inventory_items"]
        }
        self.assertEqual(quantities, {unsupported["uid"]: 1, usable["uid"]: 1})
        self.assertEqual(snapshot(self.store, character["id"]), ())

    def test_native_real_level_use_criterion_rejects_without_consuming(self):
        account, character, generation = self.actor("buff-level-gate")
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=35 WHERE id=%s", (character["id"],))
        character = self.store.character(account, character["id"])
        source = self.grant_item(account, character, generation, 9811)

        with self.assertRaisesRegex(ValueError, "condiciones"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", source["uid"], 0),
                expected_hp=character["hp"],
                in_fight=False,
            )

        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(
            [(row["uid"], row["quantity"]) for row in reopened["inventory_items"]],
            [(source["uid"], 1)],
        )
        self.assertEqual(snapshot(self.store, character["id"]), ())

    def test_native_crossboost_and_sharp2330_exclusions_reject_without_debit(self):
        account, character, generation = self.actor("buff-crossboost")
        xp = self.grant_item(account, character, generation, 27576, quantity=2)
        first = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", xp["uid"], 0),
            expected_hp=character["hp"],
            in_fight=False,
        )
        self.assertEqual(first["character"]["consumable_states"][0]["state_id"], 6254)
        with self.assertRaisesRegex(ValueError, "condiciones"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", xp["uid"], 0),
                expected_hp=character["hp"],
                in_fight=False,
            )
        self.assertEqual(
            {
                row["uid"]: row["quantity"]
                for row in self.store.character(account, character["id"])[
                    "inventory_items"
                ]
            }[xp["uid"]],
            1,
        )

        other_account, other, other_generation = self.actor("buff-sharp")
        sharp = self.grant_item(other_account, other, other_generation, 17728)
        active = use(
            self.store,
            other_account,
            other_generation,
            other["id"],
            struct.pack(">qB", sharp["uid"], 0),
            expected_hp=other["hp"],
            in_fight=False,
        )
        self.assertIn(
            2330, {row["state_id"] for row in active["character"]["consumable_states"]}
        )
        mea = self.grant_item(other_account, other, other_generation, 13551)
        with self.assertRaisesRegex(ValueError, "condiciones"):
            use(
                self.store,
                other_account,
                other_generation,
                other["id"],
                struct.pack(">qB", mea["uid"], 0),
                expected_hp=other["hp"],
                in_fight=False,
            )
        self.assertIn(
            mea["uid"],
            {
                row["uid"]
                for row in self.store.character(other_account, other["id"])[
                    "inventory_items"
                ]
            },
        )

    def test_native_battleground_and_non_neo_gates_preserve_food(self):
        from wakfu_server.native_world_context import battleground_worlds
        from unittest.mock import patch

        account, character, generation = self.actor("buff-battle-gate")
        with self.store.connection() as db:
            apply_damage(db, character, 10, False)
        wounded = self.store.character(account, character["id"])
        healing = self.grant_item(account, wounded, generation, 19313)
        battlefield = next(iter(battleground_worlds()))
        with self.assertRaisesRegex(ValueError, "condiciones"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", healing["uid"], 0),
                expected_hp=wounded["hp"],
                in_fight=False,
                native_map_id=battlefield,
            )
        self.assertEqual(
            self.store.character(account, character["id"])["hp"], wounded["hp"]
        )
        self.assertEqual(snapshot(self.store, character["id"]), ())

        neo = self.grant_item(account, wounded, generation, 32834)
        with patch(
            "wakfu_server.combat_system_conditions.boolean_system_configuration",
            return_value=False,
        ):
            with self.assertRaisesRegex(ValueError, "condiciones"):
                use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qB", neo["uid"], 0),
                    expected_hp=wounded["hp"],
                    in_fight=False,
                )
        self.assertIn(
            neo["uid"],
            {
                row["uid"]
                for row in self.store.character(account, character["id"])[
                    "inventory_items"
                ]
            },
        )

    def test_native_state_and_inventory_debit_roll_back_as_one_transaction(self):
        account, character, generation = self.actor("buff-rollback")
        source = self.grant_item(account, character, generation, 3663)
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_buff_food_debit() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'forced inventory debit failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_buff_food_debit BEFORE DELETE ON inventory_items "
                "FOR EACH ROW EXECUTE FUNCTION reject_buff_food_debit()"
            )
        with self.assertRaisesRegex(Exception, "forced inventory debit failure"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", source["uid"], 0),
                expected_hp=character["hp"],
                in_fight=False,
            )
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(
            [(item["uid"], item["quantity"]) for item in reopened["inventory_items"]],
            [(source["uid"], 1)],
        )
        self.assertEqual(snapshot(self.store, character["id"]), ())

    def test_flat_healing_food_remains_on_legacy_healing_path_without_a_buff(self):
        account, character, generation = self.actor("healing-control")
        initialized = health_store.initialize(
            self.store, account, generation, character["id"]
        )
        health_store.sync(
            self.store, account, generation, character["id"], initialized["hp"], 10
        )
        character = self.store.character(account, character["id"])
        source = self.grant_item(account, character, generation, 8047)
        result = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=10,
            in_fight=False,
        )
        self.assertTrue(result["applied"])
        self.assertGreater(result["healed"], 0)
        self.assertEqual(snapshot(self.store, character["id"]), ())

    def test_hp_state_preserves_normal_and_heavy_canonical_wounds_without_healing(self):
        for suffix, wound_delta in (("normal", 10), ("heavy", 40)):
            with self.subTest(wounds=suffix):
                account, character, generation = self.actor(f"buff-hp-{suffix}")
                base_max = character["max_hp"]
                damage = 10 if suffix == "normal" else base_max + wound_delta
                with self.store.connection() as db:
                    apply_damage(db, character, damage, False)
                wounded = self.store.character(account, character["id"])
                source = self.grant_item(account, wounded, generation, 10376)

                used = use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qB", source["uid"], 0),
                    expected_hp=wounded["hp"],
                    in_fight=False,
                )
                saved = used["character"]
                self.assertEqual(saved["max_hp"], base_max + 20)
                self.assertEqual(saved["hp_damage"], damage)
                self.assertEqual(saved["hp"], max(1, base_max + 20 - damage))
                if suffix == "heavy":
                    self.assertEqual(saved["hp"], wounded["hp"])

                with self.store.connection() as db:
                    retire_states(self.store, db, character["id"], state_ids=(1216,))
                    restored = reconcile_health(
                        db, self.store.character(account, character["id"], db)
                    )
                self.assertEqual(
                    (restored["max_hp"], restored["hp"], restored["hp_damage"]),
                    (base_max, wounded["hp"], damage),
                )

    def test_owned_world_characteristics_include_ap_mp_wisdom_pp_and_shop_factor(self):
        # Keep event foods on separate owners: native candy completion markers
        # can retire a prior one-fight candy in the same event family.
        cases = (
            (14755, 2, 1, "buffap"),
            (14796, 3, 1, "buffmp"),
            (9811, 36, 50, "buffwisdom"),
            (9865, 33, 10, "buffprospect"),
            (27576, 118, 50, "buffshop"),
        )
        for reference, stat, amount, username in cases:
            with self.subTest(reference=reference, stat=stat):
                account, character, generation = self.actor(username)
                baseline = self._characteristic_rows(character)
                source = self.grant_item(account, character, generation, reference)
                result = use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qB", source["uid"], 0),
                    expected_hp=character["hp"],
                    in_fight=False,
                )
                projected = self._characteristic_rows(result["character"])
                self.assertEqual(projected[stat][0], baseline[stat][0] + amount)

    def test_native_550_food_emote_result_is_published_by_actual_world_route(self):
        from unittest.mock import Mock, patch
        from test_world_consumable_dispatch import WorldConsumableDispatchTests
        from wakfu_server.inventory_animation import consumable_emote

        account, character, generation = self.actor("buff-world-emote")
        source = self.grant_item(account, character, generation, 20482)
        result = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=character["hp"],
            in_fight=False,
        )
        self.assertEqual(
            result["emotes"],
            [{"effect_id": 180996, "emote_id": 20019, "forced": True}],
        )

        route = WorldConsumableDispatchTests()
        route.setUpClass()
        bindings, use_mock, send, _record, world = route.setup_route(result=result)
        bindings.update(
            STORE=self.store,
            account_id=account,
            generation=generation,
            character=dict(
                id=character["id"],
                hp=character["hp"],
                map_id=character["map_id"],
                instance_id=character["instance_id"],
                direction=character.get("direction", 0),
            ),
            position={key: character[key] for key in ("x", "y", "z")},
        )
        with (
            patch("wakfu_server.inventory_consumable_effects.use", use_mock),
            patch("wakfu_server.combat_lifecycle.outside_progression", return_value=()),
            patch(
                "wakfu_server.inventory_items.equipment_inventory",
                return_value=(12470, b"inventory"),
            ),
        ):
            exec(route.driver, bindings)

        expected_emote = consumable_emote(
            actor_id=character["id"],
            action_id=1,
            effect_uid=(1 << 48) + 1,
            effect_id=180996,
            emote_id=20019,
        )
        world.broadcast.assert_any_call(generation, character["id"], *expected_emote)
        use_mock.assert_called_once()

    def test_real_food_use_states_initialize_native_combat_profession_effects(self):
        from random import Random
        from wakfu_server.combat_effect_profession import manager_value
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests

        for username, reference, state_id, expected in (
            ("buffcombata", 20482, 4311, {"craft_speed": 50}),
            (
                "buffcombatb",
                20824,
                4564,
                {"craft_speed": 100, "plant_speed": 100, "collect_speed": 100},
            ),
        ):
            account, character, generation = self.actor(username)
            source = self.grant_item(account, character, generation, reference)
            result = use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", source["uid"], 0),
                expected_hp=character["hp"],
                in_fight=False,
            )
            persisted_states = result["character"]["consumable_states"]
            self.assertEqual({row["state_id"] for row in persisted_states}, {state_id})

            native = SpellTransactionTests()
            native_character, monster, fight = native.native_server_fixture(
                19,
                200,
                native_qi=True,
            )
            native_character = dict(
                native_character,
                map_id=1134,
                consumable_states=persisted_states,
            )
            monsters = {monster["id"]: monster}
            fight, _packets = prepare_server_initialization(
                native_character,
                monsters,
                fight,
                3,
                encode_deck([], []),
                action_id=1,
                rng=Random(1),
                fight_start=False,
            )
            actor_id = native_character["id"]
            self.assertTrue(
                any(
                    entry.reference == state_id
                    for entry in fight.actors[actor_id].state_ledger.entries
                )
            )
            self.assertEqual(
                manager_value(fight, actor_id, "craft_speed", 64, 8),
                expected["craft_speed"],
            )
            self.assertEqual(
                manager_value(fight, actor_id, "plant_speed", 64, 2),
                expected.get("plant_speed", 0),
            )
            self.assertEqual(
                manager_value(fight, actor_id, "collect_speed", 64, 3),
                expected.get("collect_speed", 0),
            )

    def test_foodclear_admin_only_preserves_wounds_and_live_position(self):
        from wakfu_server.consumable_world_lifecycle import clear_for_test

        account, character, generation = self.actor("foodclearadmin")
        base_max = character["max_hp"]
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (account,))
            apply_damage(db, character, 10, False)
        wounded = self.store.character(account, character["id"])
        source = self.grant_item(account, wounded, generation, 10376)
        used = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=wounded["hp"],
            in_fight=False,
        )
        live = dict(used["character"], x=23, y=31, z=2, direction=5)

        cleared = clear_for_test(self.store, account, generation, live)
        self.assertEqual(
            (cleared["x"], cleared["y"], cleared["z"], cleared["direction"]),
            (23, 31, 2, 5),
        )
        self.assertEqual(cleared["consumable_states"], ())
        self.assertEqual(
            (cleared["max_hp"], cleared["hp"], cleared["hp_damage"]),
            (base_max, max(1, base_max - 10), 10),
        )
        self.assertEqual(snapshot(self.store, character["id"]), ())

        other_account, other, other_generation = self.actor("foodcleardenied")
        other_source = self.grant_item(other_account, other, other_generation, 3663)
        used_other = use(
            self.store,
            other_account,
            other_generation,
            other["id"],
            struct.pack(">qB", other_source["uid"], 0),
            expected_hp=other["hp"],
            in_fight=False,
        )
        with self.assertRaises(PermissionError):
            clear_for_test(
                self.store, other_account, other_generation, used_other["character"]
            )
        self.assertEqual(len(snapshot(self.store, other["id"])), 1)

    def test_food_use_and_foodclear_preserve_selected_equipment_statistics(self):
        from wakfu_server import health_store
        from wakfu_server.consumable_world_lifecycle import clear_for_test
        from wakfu_server.combat_lifecycle import outside_progression
        from wakfu_server.consumable_buff_wire import snapshot as buff_snapshot
        from wakfu_server.equipment_stats import (
            bonuses as equipment_bonuses,
            combat_resources,
            effective_character,
        )
        from wakfu_server.wire import proto_field, proto_fields

        account = self.store.register("equippedfoodclear", "local-password")["id"]
        character = self.store.create_character(
            account,
            "Equipped Food Clear",
            breed=8,
        )
        from wakfu_server.progression import level_xp

        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (account,))
            db.execute("UPDATE characters SET level=6 WHERE id=%s", (character["id"],))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(6), character["id"]),
            )

        character = self.store.character(account, character["id"])
        container = next(
            row["uid"] for row in character["inventory_containers"] if row["kind"] == 0
        )
        gear = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=2021,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={2021},
        )
        food = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=3663,
            quantity=1,
            container=container,
            slot=1,
            allowed_references={3663},
        )
        equipment = proto_field(10, proto_field(8, gear["uid"]) + proto_field(16, 4))
        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in (
                (8, 0),
                (18, b"Equipment preservation"),
                (24, 6),
                (56, 0),
            )
        )
        self.store.save_build(
            account,
            generation,
            character["id"],
            0,
            {"sheet": sheet, "equipment": equipment, "deck": b"", "aptitudes": b""},
        )
        health_store.initialize(self.store, account, generation, character["id"])
        character = self.store.character(account, character["id"])
        with self.store.connection() as db:
            apply_damage(db, character, 10, False)
        wounded = self.store.character(account, character["id"])
        baseline_stats = equipment_bonuses(wounded)["stats"]
        self.assertEqual(baseline_stats, {2: 1, 1: 6, 9: 2, 20: 9})
        baseline_resources = combat_resources(wounded, wp=6)
        baseline_max_hp = effective_character(wounded)["max_hp"]
        wounds = wounded["hp_damage"]
        from test_world_build_stat_reset import world_rows

        def published_stats(owner):
            opcode, body = outside_progression(owner, wp=6)
            self.assertEqual(opcode, 13046)
            return world_rows(body)[1]

        baseline_panel = published_stats(wounded)

        used = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", food["uid"], 0),
            expected_hp=wounded["hp"],
            in_fight=False,
        )
        after_use = used["character"]
        self.assertEqual(after_use["hp_damage"], wounds)
        self.assertEqual(equipment_bonuses(after_use)["stats"], baseline_stats)
        self.assertEqual(combat_resources(after_use, wp=6), baseline_resources)
        used_panel = published_stats(after_use)
        self.assertEqual(used_panel[1], baseline_panel[1])
        self.assertEqual(
            tuple(used_panel[key] for key in (2, 3, 4)),
            tuple(baseline_panel[key] for key in (2, 3, 4)),
        )
        self.assertEqual(used_panel[9], baseline_panel[9])
        self.assertEqual(used_panel[20], baseline_panel[20])
        fire_key = baseline_panel.get(21, (0, 0, 0, 0))
        self.assertEqual(used_panel[21][0], fire_key[0] + 10)

        icon_packets = buff_snapshot(after_use)
        self.assertEqual([opcode for opcode, _ in icon_packets], [12613, 13420])
        icon_body = icon_packets[0][1]
        (
            _fight,
            _action,
            _parent,
            _execute,
            _effect_class,
            payload_size,
        ) = struct.unpack_from(">iiiBih", icon_body)
        icon_fields = dict(proto_fields(icon_body[19 : 19 + payload_size]))
        self.assertEqual(icon_fields[9 << 3], 1)
        self.assertEqual(icon_fields[10 << 3], (1210 << 16) | 10)

        cleared = clear_for_test(self.store, account, generation, after_use)
        self.assertEqual(cleared["consumable_states"], ())
        self.assertEqual(cleared["hp_damage"], wounds)
        self.assertEqual(cleared["max_hp"], baseline_max_hp)
        self.assertEqual(equipment_bonuses(cleared)["stats"], baseline_stats)
        self.assertEqual(combat_resources(cleared, wp=6), baseline_resources)
        self.assertEqual(published_stats(cleared), baseline_panel)
        self.assertEqual(
            cleared["builds"][0]["equipment"],
            equipment.hex(),
        )
        self.assertEqual(snapshot(self.store, character["id"]), ())
        clear_packets = consumable_delta(after_use, cleared)
        self.assertEqual([opcode for opcode, _ in clear_packets], [13560, 13420])
        removal_body = clear_packets[0][1]
        _fight, _action, _sequence, _effect_class, payload_size = struct.unpack_from(
            ">iiiih", removal_body
        )
        removal_fields = dict(proto_fields(removal_body[18 : 18 + payload_size]))
        self.assertEqual(removal_fields[9 << 3], 1)
        self.assertEqual(removal_fields[10 << 3], (1210 << 16) | 10)

    def test_percentage_foods_use_current_buffed_maximum_and_reject_full_hp(self):
        from unittest.mock import patch
        from wakfu_server.inventory_consumables import food_healing_amount
        from wakfu_server.inventory_consumable_effects import percentage_healing

        for reference, percentage, username in (
            (19313, 10, "buff-percent-ten"),
            (20416, 8, "buff-percent-eight"),
        ):
            with self.subTest(reference=reference):
                account, character, generation = self.actor(username)
                base_max = character["max_hp"]
                boost = self.grant_item(account, character, generation, 10376)
                boosted = use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qB", boost["uid"], 0),
                    expected_hp=character["hp"],
                    in_fight=False,
                )["character"]
                self.assertEqual(boosted["max_hp"], base_max + 20)
                with self.store.connection() as db:
                    apply_damage(db, boosted, 25, False)
                wounded = self.store.character(account, character["id"])
                source = self.grant_item(account, wounded, generation, reference)
                raw_heal = percentage_healing(
                    wounded["max_hp"], percentage, rng=lambda: 0.0
                )
                expected_heal = food_healing_amount(wounded, raw_heal, rng=lambda: 0.0)

                with patch(
                    "wakfu_server.inventory_consumable_effects.random.random",
                    return_value=0.0,
                ):
                    healed = use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        struct.pack(">qB", source["uid"], 0),
                        expected_hp=wounded["hp"],
                        in_fight=False,
                    )
                self.assertEqual(healed["healed"], expected_heal)
                self.assertEqual(healed["character"]["max_hp"], wounded["max_hp"])
                self.assertEqual(
                    healed["character"]["hp"], wounded["hp"] + expected_heal
                )

                current = healed["character"]
                current = health_store.sync(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    current["hp"],
                    current["max_hp"],
                )
                full_source = self.grant_item(account, current, generation, reference)
                with self.assertRaisesRegex(ValueError, "condiciones"):
                    use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        struct.pack(">qB", full_source["uid"], 0),
                        expected_hp=current["hp"],
                        in_fight=False,
                    )
                self.assertIn(
                    full_source["uid"],
                    {
                        item["uid"]
                        for item in self.store.character(account, character["id"])[
                            "inventory_items"
                        ]
                    },
                )

    @staticmethod
    def _characteristic_rows(character):
        payload = owned_public_characteristics(character)
        count = struct.unpack_from(">H", payload)[0]
        row_size = struct.calcsize(">Biiii")
        return {
            row[0]: row[1:]
            for offset in range(count)
            if (row := struct.unpack_from(">Biiii", payload, 2 + offset * row_size))
        }
