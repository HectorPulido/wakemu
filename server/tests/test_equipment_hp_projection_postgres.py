"""Persisted native eWO HP across real build and health transitions."""
from postgres_case import PostgresCase
import test_equipment_level_groups_postgres as _fixture
from wakfu_server import builds, health_store, wire
from wakfu_server.equipment import RULES
from wakfu_server.equipment_stats import bonuses
from wakfu_server.equipment_hp_lifecycle import load as load_projection
from wakfu_server.inventory_items import grant


class EquipmentHpProjectionPostgresTests(PostgresCase):
    _owner = _fixture.EquipmentLevelGroupsPostgresTests._owner
    _grant = _fixture.EquipmentLevelGroupsPostgresTests._grant
    _save = _fixture.EquipmentLevelGroupsPostgresTests._save

    def _sheet(self, level, name=b"HP projection", index=0):
        return b"".join(
            wire.proto_field(tag, value)
            for tag, value in ((8, index), (18, name), (24, level), (56, 0))
        )

    def _save_empty_build(self, account, generation, character, index):
        return self.store.save_build(
            account,
            generation,
            character["id"],
            index,
            dict(
                sheet=self._sheet(
                    character["level"], f"HP build {index}".encode(), index=index
                ),
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=b"",
            ),
        )

    def _projection(self, character_id):
        with self.store.connection() as db:
            return load_projection(db, character_id)

    def test_zero_action_ready_return_preserves_overcap_raw_hp_until_unequip(self):
        # Use the existing real combat Ready fixture rather than synthesizing
        # actor HP. It equips the native deterministic eWO 6583 and snapshots
        # its raw current before any combat action is taken.
        import test_equipment_null_carrier_pipeline as _pipeline
        from wakfu_server.combat_health import persist

        (
            char,
            _monster,
            _deck,
            _rng,
            runtime,
            _stats,
        ) = _pipeline.EquipmentNullCarrierPipelineTests._fixture(
            self, reference=6583, slot=13, level=40
        )
        actor = runtime.fight.actors[char["id"]]
        with self.store.connection() as db:
            generation = db.execute(
                "SELECT generation FROM sessions WHERE account_id=%s",
                (char["account_id"],),
            ).fetchone()["generation"]
        projection = self._projection(char["id"])
        self.assertEqual(len(projection["receipts"]), 1)
        self.assertEqual(projection["receipts"][0]["actual"], 15)
        ready_raw = actor.effect_hp_raw_current
        self.assertGreater(ready_raw, actor.max_hp)

        # The fixture's fight is an actual Ready fight; persist a matching
        # durable participant and take the normal no-action finished return.
        runtime.fight.phase = "finished"
        runtime.fight.winner = 0
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE "
                "VALUES(%s,'finished')",
                (runtime.fight.id,),
            )
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (runtime.fight.id, char["id"], char["account_id"]),
            )
            returned = persist(
                self.store,
                char["account_id"],
                generation,
                char,
                runtime.fight,
                reason="return",
                db=db,
            )["character"]
            exit_row = db.execute(
                "SELECT reason,return_acknowledged_at FROM fight_health_exits "
                "WHERE fight_id=%s AND character_id=%s",
                (runtime.fight.id, char["id"]),
            ).fetchone()
        self.assertEqual(exit_row["reason"], "return")
        self.assertIsNotNone(exit_row["return_acknowledged_at"])
        self.assertEqual(
            (returned["hp"], returned["max_hp"]), (actor.max_hp, actor.max_hp)
        )
        returned_projection = self._projection(char["id"])
        self.assertEqual(returned_projection["actor"].effect_hp_raw_current, ready_raw)
        self.assertGreater(
            returned_projection["actor"].effect_hp_raw_current, returned["max_hp"]
        )
        self.assertEqual(returned_projection["receipts"], projection["receipts"])

        # A real empty-build activation applies the receipt inverse. The raw
        # current then fits the restored base maximum and the physical UID stays.
        self._save_empty_build(char["account_id"], generation, returned, 1)
        restored = self.store.activate_build(
            char["account_id"],
            generation,
            char["id"],
            1,
            in_fight=False,
        )
        ordinary_hp_bonus = bonuses(char)["stats"].get(1, 0)
        self.assertEqual(
            restored["max_hp"], returned["max_hp"] + 15 - ordinary_hp_bonus
        )
        restored_projection = self._projection(char["id"])
        self.assertEqual(restored_projection["receipts"], [])
        self.assertEqual(
            restored_projection["actor"].effect_hp_raw_current, restored["max_hp"]
        )
        self.assertTrue(
            any(row["reference"] == 6583 for row in restored["inventory_items"])
        )

    def test_migration230_and_native_hp_survive_build_switch_health_and_reconnect(self):
        # PostgresCase migrates a fresh isolated schema for each test. Verify
        # the durable projection contract rather than relying on a live DB.
        account, generation, character = self._owner(40)
        with self.store.connection() as db:
            columns = {
                row["column_name"]
                for row in db.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=current_schema() "
                    "AND table_name='character_equipment_hp_projection'"
                )
            }
        self.assertTrue(
            {
                "character_id",
                "raw_current",
                "raw_maximum",
                "raw_minimum",
                "percentage",
                "frozen",
                "receipts",
                "revision",
            }.issubset(columns)
        )
        self.assertIsNone(self._projection(character["id"]))

        # At full native HP, this real one-operand source lowers the effective
        # maximum while preserving the PA raw current above that new cap.
        item = self._grant(account, generation, character, 6583, 0)
        self.assertEqual(RULES[6583]["slots"][0], 13)
        character = self.store.character(account, character["id"])
        equipped = self._save(account, generation, character, item, level=40)
        self.assertEqual(len(bonuses(equipped)["hp_operations"]), 1)
        operation = bonuses(equipped)["hp_operations"][0]
        self.assertEqual(operation["amount"], 15)
        self.assertEqual(equipped["hp_damage"], character["hp_damage"])
        ordinary_hp_bonus = bonuses(equipped)["stats"].get(1, 0)
        self.assertEqual(
            equipped["max_hp"],
            character["max_hp"] + ordinary_hp_bonus - operation["amount"],
            f"fresh baseline={character['max_hp']} ordinary HP={ordinary_hp_bonus} "
            f"operation={operation}",
        )
        self.assertEqual(
            equipped["hp"],
            character["hp"] + ordinary_hp_bonus - operation["amount"],
        )
        state = self._projection(character["id"])
        self.assertIsNotNone(state)
        self.assertEqual(len(state["receipts"]), 1)
        receipt = state["receipts"][0]
        self.assertEqual((receipt["source_uid"], receipt["actual"]), (item["uid"], 15))
        self.assertEqual(
            state["actor"].effect_hp_raw_current,
            character["max_hp"] + ordinary_hp_bonus,
        )
        self.assertGreater(state["actor"].effect_hp_raw_current, equipped["max_hp"])
        initial_revision = state["revision"]

        # Build one is a real empty sheet. Switching to it applies the exact
        # eWO inverse, and switching back reapplies the same owned UID once.
        self._save_empty_build(account, generation, equipped, 1)
        cleared = self.store.activate_build(
            account, generation, character["id"], 1, in_fight=False
        )
        self.assertEqual(
            (cleared["max_hp"], cleared["hp"], cleared["hp_damage"]),
            (character["max_hp"], character["hp"], character["hp_damage"]),
        )
        self.assertEqual(self._projection(character["id"])["receipts"], [])
        restored = self.store.activate_build(
            account, generation, character["id"], 0, in_fight=False
        )
        self.assertEqual(
            (restored["max_hp"], restored["hp"]), (equipped["max_hp"], equipped["hp"])
        )
        reopened_store = self.reopen()
        reopened = reopened_store.character(account, character["id"])
        self.assertEqual(
            (reopened["max_hp"], reopened["hp"], reopened["hp_damage"]),
            (equipped["max_hp"], equipped["hp"], equipped["hp_damage"]),
        )
        with reopened_store.connection() as db:
            persisted = load_projection(db, character["id"])
        self.assertEqual(len(persisted["receipts"]), 1)
        self.assertGreater(persisted["revision"], initial_revision)
        self.assertEqual(persisted["receipts"][0]["source_uid"], item["uid"])
        self.assertEqual(
            persisted["actor"].effect_hp_raw_current,
            character["max_hp"] + ordinary_hp_bonus,
        )

        # Ordinary damage/healing updates the projection's native current by
        # the actual HP delta; it never rebuilds raw state from visible HP.
        damaged = health_store.sync(
            self.store,
            account,
            generation,
            character["id"],
            reopened["hp"],
            reopened["hp"] - 20,
            coefficient=0,
        )
        with self.store.connection() as db:
            after_damage = load_projection(db, character["id"])
        self.assertEqual(after_damage["actor"].effect_hp_raw_current, damaged["hp"])
        healed = health_store.sync(
            self.store,
            account,
            generation,
            character["id"],
            damaged["hp"],
            damaged["hp"] + 7,
            coefficient=0,
        )
        with self.store.connection() as db:
            after_heal = load_projection(db, character["id"])
        self.assertEqual(after_heal["actor"].effect_hp_raw_current, healed["hp"])
        self.assertEqual(healed["hp_damage"], equipped["hp_damage"] + 13)

        # Editing the active sheet to remove the item is the real unequip path;
        # it applies the inverse once and leaves the physical inventory UID.
        unequipped = self._save(account, generation, healed, None, level=40)
        self.assertEqual(
            (unequipped["max_hp"], unequipped["hp"], unequipped["hp_damage"]),
            (character["max_hp"], character["max_hp"] - 13, 13),
        )
        projection_after_unequip = self._projection(character["id"])
        self.assertEqual(projection_after_unequip["receipts"], [])
        self.assertTrue(
            any(row["uid"] == item["uid"] for row in unequipped["inventory_items"])
        )
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(
            (reopened["max_hp"], reopened["hp"], reopened["hp_damage"]),
            (unequipped["max_hp"], unequipped["hp"], unequipped["hp_damage"]),
        )

    def test_finished_fight_level_reward_rebases_equipped_hp_once(self):
        from test_combat_rewards import setup_reward_state
        from wakfu_server.combat_rewards import Policy, award
        from wakfu_server.progression import level_xp

        _store, account, character, generation, fight = setup_reward_state(self.store)
        start_level = 40
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s",
                (start_level, character["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(start_level), character["id"]),
            )
        character = health_store.initialize(
            self.store, account, generation, character["id"], coefficient=0
        )
        character = self.store.save_build(
            account,
            generation,
            character["id"],
            0,
            dict(
                sheet=self._sheet(start_level, b"Level-following HP build"),
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=b"",
            ),
        )
        item = self._grant(account, generation, character, 6583, 0)
        equipment = wire.proto_field(
            10,
            wire.proto_field(8, item["uid"])
            + wire.proto_field(16, RULES[6583]["slots"][0]),
        )
        equipped = self.store.save_build(
            account,
            generation,
            character["id"],
            0,
            dict(
                sheet=self._sheet(start_level, b"Level-following HP build"),
                equipment=equipment,
                deck=b"",
                aptitudes=b"",
            ),
        )
        wounded = health_store.sync(
            self.store,
            account,
            generation,
            character["id"],
            equipped["hp"],
            max(1, equipped["hp"] - 100),
            coefficient=0,
        )
        with self.store.connection() as db:
            before_projection = load_projection(db, character["id"])
        self.assertEqual(len(before_projection["receipts"]), 1)
        prior_wound = wounded["hp_damage"]
        canonical_before_reward = self.store.character(account, character["id"])
        projection_before_reward = self._projection(character["id"])
        self.assertEqual(
            projection_before_reward["actor"].max_hp,
            canonical_before_reward["max_hp"],
            f"projection max={projection_before_reward['actor'].max_hp} "
            f"canonical max={canonical_before_reward['max_hp']}",
        )
        self.assertEqual(
            projection_before_reward["actor"].hp,
            canonical_before_reward["hp"],
            f"projection hp={projection_before_reward['actor'].hp} "
            f"canonical hp={canonical_before_reward['hp']}",
        )

        settlement = award(
            self.store,
            account,
            generation,
            character["id"],
            fight,
            Policy(xp=level_xp(start_level + 1) - level_xp(start_level)),
        )
        self.assertTrue(settlement["awarded"])
        self.assertEqual(settlement["character"]["level"], start_level + 1)
        self.assertEqual(settlement["character"]["hp_damage"], prior_wound)
        levelled = self._save(
            account, generation, settlement["character"], item, level=start_level + 1
        )
        self.assertEqual(levelled["hp_damage"], prior_wound)
        self.assertEqual(levelled["hp"], levelled["max_hp"] - prior_wound)
        with self.store.connection() as db:
            after_projection = load_projection(db, character["id"])
        self.assertEqual(len(after_projection["receipts"]), 1)
        self.assertEqual(after_projection["receipts"][0]["source_uid"], item["uid"])
        self.assertGreater(
            after_projection["actor"].effect_base_maxima[1],
            before_projection["actor"].effect_base_maxima[1],
        )

        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(
            (
                reopened["level"],
                reopened["hp"],
                reopened["max_hp"],
                reopened["hp_damage"],
            ),
            (start_level + 1, levelled["hp"], levelled["max_hp"], prior_wound),
        )
        replay = award(
            self.store,
            account,
            generation,
            character["id"],
            fight,
            Policy(xp=level_xp(start_level + 2) - level_xp(start_level + 1)),
        )
        self.assertFalse(replay["awarded"])
        with self.store.connection() as db:
            final_projection = load_projection(db, character["id"])
        self.assertEqual(final_projection["receipts"], after_projection["receipts"])
        self.assertEqual(final_projection["revision"], after_projection["revision"])

    def test_real_food_expiry_keeps_equipment_hp_receipt_and_wound(self):
        import struct
        from wakfu_server.inventory_consumable_effects import use
        from wakfu_server.items.consumable_world_lifecycle import synchronize

        clock = [1000.0]
        self.store.clock = lambda: clock[0]
        account, generation, character = self._owner(40)
        character = self.store.save_build(
            account,
            generation,
            character["id"],
            0,
            dict(
                sheet=self._sheet(40),
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=b"",
            ),
        )
        item = self._grant(account, generation, character, 6583, 0)
        equipped = self._save(account, generation, character, item, level=40)
        wound = max(1, equipped["hp"] - 80)
        wounded = health_store.sync(
            self.store,
            account,
            generation,
            character["id"],
            equipped["hp"],
            wound,
            coefficient=0,
        )
        food = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=3663,
            quantity=1,
            container=character["inventory_containers"][0]["uid"],
            slot=1,
            allowed_references={3663},
        )
        used = use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qB", food["uid"], 0),
            expected_hp=wounded["hp"],
            in_fight=False,
        )
        with self.store.connection() as db:
            projection_before = load_projection(db, character["id"])
            food_row = db.execute(
                "SELECT uid,clock,expires_ms,remaining_ms,online_anchor_ms "
                "FROM character_consumable_buffs WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
            self.assertIsNotNone(food_row)
            now_ms = int(clock[0] * 1000)
            if food_row["clock"] == "wall":
                db.execute(
                    "UPDATE character_consumable_buffs SET expires_ms=%s WHERE uid=%s",
                    (now_ms + 1, food_row["uid"]),
                )
            elif food_row["clock"] == "online":
                db.execute(
                    "UPDATE character_consumable_buffs SET remaining_ms=1,online_generation=%s,"
                    "online_anchor_ms=%s WHERE uid=%s",
                    (generation, now_ms, food_row["uid"]),
                )
            else:
                self.fail("The selected food should have an expiring native clock")
        self.assertEqual(len(projection_before["receipts"]), 1)
        clock[0] += 0.002
        after = synchronize(
            self.store,
            account,
            generation,
            used["character"],
            mode="tick",
            in_combat=False,
        )
        self.assertEqual(after["consumable_states"], ())
        self.assertEqual(after["hp_damage"], wounded["hp_damage"])
        with self.store.connection() as db:
            projection_after = load_projection(db, character["id"])
            remaining = db.execute(
                "SELECT COUNT(*) AS count FROM character_consumable_buffs WHERE character_id=%s",
                (character["id"],),
            ).fetchone()["count"]
        self.assertEqual(remaining, 0)
        self.assertEqual(projection_after["receipts"], projection_before["receipts"])
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(reopened["hp_damage"], wounded["hp_damage"])
        self.assertEqual(len(reopened["equipment_hp_projection"]["receipts"]), 1)
