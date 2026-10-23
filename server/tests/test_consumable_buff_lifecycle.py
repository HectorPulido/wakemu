"""PostgreSQL lifecycle and transaction tests for durable consumable states."""
from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.consumable_buffs import (
    active_states,
    apply_states,
    enter_combat,
    emit_events,
    pause,
    resume,
    return_from_combat,
    retire_states,
    snapshot,
)


class ConsumableBuffLifecyclePostgresTests(PostgresCase):
    def fixture(self, *, source_reference=3663):
        account = self.store.register("consumable-buff", "local-password")["id"]
        character = self.store.create_character(account, "Buff Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        character = self.store.character(account, character["id"])
        source = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=source_reference,
            quantity=2,
            container=next(
                bag["uid"]
                for bag in character["inventory_containers"]
                if bag["kind"] == 0
            ),
            slot=0,
            allowed_references={source_reference},
        )
        return account, generation, character, source

    @staticmethod
    def descriptor(
        *,
        clock="wall",
        duration_ms=900_000,
        state_id=1210,
        effect_ids=(64544, 64545, 64546),
    ):
        return dict(
            state_id=state_id,
            level=10,
            clock=clock,
            duration_ms=duration_ms,
            stacking="replace",
            effect_ids=list(effect_ids),
            removes=[],
        )

    def test_source_decrement_and_state_application_roll_back_together(self):
        account, generation, character, source = self.fixture()
        with self.assertRaisesRegex(RuntimeError, "force rollback"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                    (source["uid"],),
                )
                apply_states(
                    self.store,
                    db,
                    character["id"],
                    [self.descriptor()],
                    source_item_ref=3663,
                    source_item_uid=source["uid"],
                    generation=generation,
                    now_ms=1_000,
                )
                raise RuntimeError("force rollback")
        restored = self.store.character(account, character["id"])
        self.assertEqual(
            [(item["uid"], item["quantity"]) for item in restored["inventory_items"]],
            [(source["uid"], 2)],
        )
        self.assertEqual(snapshot(self.store, character["id"], now_ms=1_000), ())

    def test_replacement_refreshes_the_same_native_state_and_wall_deadline_expires(
        self,
    ):
        account, generation, character, source = self.fixture()
        with self.store.connection() as db:
            first = apply_states(
                self.store,
                db,
                character["id"],
                [self.descriptor(duration_ms=900)],
                source_item_ref=3663,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=1_000,
            )
        self.assertEqual(len(first), 1)
        self.assertEqual((first[0]["state_id"], first[0]["remaining_ms"]), (1210, 900))

        second_source = grant(
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
        with self.store.connection() as db:
            refreshed = apply_states(
                self.store,
                db,
                character["id"],
                [self.descriptor(duration_ms=1_000)],
                source_item_ref=3663,
                source_item_uid=second_source["uid"],
                generation=generation,
                now_ms=1_500,
            )
        self.assertEqual(len(refreshed), 1)
        self.assertEqual(refreshed[0]["source_item_uid"], second_source["uid"])
        self.assertEqual(refreshed[0]["remaining_ms"], 1_000)
        self.assertEqual(
            snapshot(self.store, character["id"], now_ms=2_499)[0]["remaining_ms"], 1
        )
        self.assertEqual(snapshot(self.store, character["id"], now_ms=2_500), ())

    def test_replacement_rejects_lower_level_without_changing_active_state(self):
        _, generation, character, source = self.fixture()
        with self.store.connection() as db:
            original = apply_states(
                self.store,
                db,
                character["id"],
                [self.descriptor()],
                source_item_ref=3663,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=1_000,
            )[0]
        weaker = self.descriptor()
        weaker["level"] = 5
        with self.assertRaisesRegex(ValueError, "nivel inferior"):
            with self.store.connection() as db:
                apply_states(
                    self.store,
                    db,
                    character["id"],
                    [weaker],
                    source_item_ref=3663,
                    source_item_uid=source["uid"],
                    generation=generation,
                    now_ms=1_001,
                )
        current = snapshot(self.store, character["id"], now_ms=1_001)
        self.assertEqual(
            [(row["uid"], row["level"], row["remaining_ms"]) for row in current],
            [(original["uid"], 10, 899_999)],
        )

    def test_online_timer_checkpoints_pauses_offline_time_and_resumes_new_generation(
        self,
    ):
        _, generation, character, source = self.fixture(source_reference=20034)
        with self.store.connection() as db:
            initial = apply_states(
                self.store,
                db,
                character["id"],
                [
                    self.descriptor(
                        clock="online",
                        duration_ms=1_000,
                        state_id=4073,
                        effect_ids=(173760, 173761, 173762),
                    )
                ],
                source_item_ref=20034,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=1_000,
            )
        self.assertEqual(initial[0]["remaining_ms"], 1_000)
        with self.store.connection() as db:
            checkpointed = active_states(
                self.store, db, character["id"], generation=generation, now_ms=1_400
            )
        self.assertEqual(checkpointed[0]["remaining_ms"], 600)
        with self.store.connection() as db:
            paused = pause(self.store, db, character["id"], generation, now_ms=1_600)
        self.assertEqual(paused[0]["remaining_ms"], 400)

        with self.store.connection() as db:
            resumed = resume(
                self.store, db, character["id"], "new-session", now_ms=50_000
            )
        self.assertEqual(resumed[0]["remaining_ms"], 400)
        with self.store.connection() as db:
            after_online = active_states(
                self.store, db, character["id"], generation="new-session", now_ms=50_250
            )
        self.assertEqual(after_online[0]["remaining_ms"], 150)
        with self.store.connection() as db:
            expired = active_states(
                self.store, db, character["id"], generation="new-session", now_ms=50_400
            )
        self.assertEqual(expired, ())

    def test_native_removal_retires_by_state_or_instance_uid(self):
        _, generation, character, source = self.fixture()
        with self.store.connection() as db:
            created = apply_states(
                self.store,
                db,
                character["id"],
                [self.descriptor()],
                source_item_ref=3663,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=1_000,
            )
        uid = created[0]["uid"]
        with self.store.connection() as db:
            retire_states(self.store, db, character["id"], uids=(uid,), now_ms=1_001)
        self.assertEqual(snapshot(self.store, character["id"], now_ms=1_001), ())

    def test_duplicate_native_state_rejects_before_replacing_any_state_in_plan(self):
        _, generation, character, source = self.fixture()
        with self.store.connection() as db:
            original = apply_states(
                self.store,
                db,
                character["id"],
                [self.descriptor()],
                source_item_ref=3663,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=1_000,
            )[0]
        replacement = self.descriptor(state_id=1211)
        replacement["removes"] = [1210]
        duplicate = self.descriptor()
        duplicate["stacking"] = "native_reject_duplicate"
        with self.assertRaisesRegex(ValueError, "ya está activo"):
            with self.store.connection() as db:
                apply_states(
                    self.store,
                    db,
                    character["id"],
                    [replacement, duplicate],
                    source_item_ref=3663,
                    source_item_uid=source["uid"],
                    generation=generation,
                    now_ms=1_001,
                )
        current = snapshot(self.store, character["id"], now_ms=1_001)
        self.assertEqual(
            [(row["uid"], row["state_id"]) for row in current],
            [(original["uid"], 1210)],
        )

    def test_online_combat_return_uses_durable_connected_clock_after_reconnect(self):
        _, generation, character, source = self.fixture(source_reference=20034)
        with self.store.connection() as db:
            created = apply_states(
                self.store,
                db,
                character["id"],
                [
                    self.descriptor(
                        clock="online",
                        duration_ms=10_000,
                        state_id=4073,
                        effect_ids=(173760, 173761, 173762),
                    )
                ],
                source_item_ref=20034,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=0,
            )
        uid = created[0]["uid"]
        with self.store.connection() as db:
            enter_combat(
                self.store, db, character["id"], 55, generation=generation, now_ms=0
            )
        with self.store.connection() as db:
            paused = pause(self.store, db, character["id"], generation, now_ms=2_000)
        self.assertEqual(paused[0]["remaining_ms"], 8_000)
        with self.store.connection() as db:
            resumed = resume(
                self.store, db, character["id"], "generation-b", now_ms=100_000
            )
        self.assertEqual(resumed[0]["remaining_ms"], 8_000)
        native = dict(
            uid=uid,
            state_id=4073,
            removed=False,
            level=10,
            clock="online",
            remaining_ms=1,
        )
        with self.store.connection() as db:
            returned = return_from_combat(
                self.store,
                db,
                character["id"],
                55,
                [native],
                generation="generation-b",
                now_ms=101_000,
            )
        # Native combat deadlines include the reconnect gap; online time uses
        # the durable connected clock and therefore keeps seven seconds.
        self.assertEqual(returned[0]["remaining_ms"], 7_000)
        self.assertIsNone(returned[0]["combat_id"])

    def test_stale_generation_cannot_pause_replacement_and_combat_return_requires_exact_uids(
        self,
    ):
        _, generation, character, source = self.fixture(source_reference=20034)
        with self.store.connection() as db:
            created = apply_states(
                self.store,
                db,
                character["id"],
                [
                    self.descriptor(
                        clock="online",
                        duration_ms=10_000,
                        state_id=4073,
                        effect_ids=(173760, 173761, 173762),
                    )
                ],
                source_item_ref=20034,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=0,
            )
        uid = created[0]["uid"]
        with self.store.connection() as db:
            enter_combat(
                self.store, db, character["id"], 56, generation=generation, now_ms=0
            )
        with self.store.connection() as db:
            resume(self.store, db, character["id"], "generation-b", now_ms=1_000)
        with self.store.connection() as db:
            pause(self.store, db, character["id"], generation, now_ms=5_000)
        with self.store.connection() as db:
            current = active_states(
                self.store, db, character["id"], generation="generation-b", now_ms=2_000
            )
        self.assertEqual(current[0]["remaining_ms"], 9_000)
        update = dict(
            uid=uid,
            state_id=4073,
            removed=False,
            level=10,
            clock="online",
            remaining_ms=9_000,
        )
        invalid = [
            [],
            [update, update],
            [dict(update, uid=uid + 99)],
            [dict(update, uid=str(uid))],
        ]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                with self.store.connection() as db:
                    return_from_combat(
                        self.store,
                        db,
                        character["id"],
                        56,
                        rows,
                        generation="generation-b",
                        now_ms=2_000,
                    )
        with self.store.connection() as db:
            returned = return_from_combat(
                self.store,
                db,
                character["id"],
                56,
                [update],
                generation="generation-b",
                now_ms=2_000,
            )
        self.assertEqual(
            (returned[0]["uid"], returned[0]["remaining_ms"]), (uid, 9_000)
        )

    def test_expired_wall_state_is_protected_in_combat_then_expires_after_return(self):
        _, generation, character, source = self.fixture()
        with self.store.connection() as db:
            created = apply_states(
                self.store,
                db,
                character["id"],
                [self.descriptor(duration_ms=10_000)],
                source_item_ref=3663,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=0,
            )
        uid = created[0]["uid"]
        with self.store.connection() as db:
            enter_combat(
                self.store, db, character["id"], 57, generation=generation, now_ms=0
            )
        with self.store.connection() as db:
            during = active_states(self.store, db, character["id"], now_ms=20_000)
        self.assertEqual((during[0]["uid"], during[0]["remaining_ms"]), (uid, 1))
        update = dict(
            uid=uid,
            state_id=1210,
            removed=False,
            level=10,
            clock="wall",
            remaining_ms=1,
        )
        with self.store.connection() as db:
            returned = return_from_combat(
                self.store,
                db,
                character["id"],
                57,
                [update],
                generation=generation,
                now_ms=20_000,
            )
        self.assertEqual(returned[0]["remaining_ms"], 1)
        self.assertEqual(snapshot(self.store, character["id"], now_ms=20_001), ())

    def test_event_food_additive_cap_self_marker_and_counter_removal(self):
        account, generation, character, source = self.fixture(source_reference=5010)
        with self.store.connection() as db:
            descriptor = db.execute(
                "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=5010"
            ).fetchone()["state"]
            state_uid = None
            for offset in range(60):
                applied = apply_states(
                    self.store,
                    db,
                    character["id"],
                    [descriptor],
                    source_item_ref=5010,
                    source_item_uid=5010,
                    generation=generation,
                    now_ms=1_000 + offset,
                )
            state_uid = applied[0]["uid"]
            self.assertEqual(
                (applied[0]["clock"], applied[0]["remaining_ms"], applied[0]["level"]),
                ("event", 0, 300),
            )

        # The cap is a native refresh=false ceiling; failed real use rolls
        # back source consumption and preserves the existing carrier.
        from wakfu_server.inventory_consumable_effects import use
        from wakfu_server.consumable_buffs import snapshot
        import struct

        before_use = snapshot(self.store, character["id"], now_ms=1_070)
        with self.assertRaisesRegex(ValueError, "nivel máximo"):
            use(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">qB", source["uid"], 0),
                expected_hp=character["hp"],
                in_fight=False,
            )
        after_use = snapshot(self.store, character["id"], now_ms=1_070)
        self.assertEqual(
            [(row["uid"], row["level"]) for row in after_use],
            [(before_use[0]["uid"], 300)],
        )
        remaining = self.store.character(account, character["id"])
        self.assertEqual(
            [(item["uid"], item["quantity"]) for item in remaining["inventory_items"]],
            [(source["uid"], 2)],
        )

        with self.store.connection() as db:
            # The emitting effect itself is excluded from its removal rule.
            emit_events(
                self.store,
                db,
                character["id"],
                [{"event_id": 2165, "effect_id": 183774}],
                generation=generation,
                now_ms=2_000,
            )
            same = active_states(self.store, db, character["id"], now_ms=2_000)
            self.assertEqual((same[0]["uid"], same[0]["level"]), (state_uid, 300))

            emit_events(
                self.store,
                db,
                character["id"],
                [1030],
                generation=generation,
                now_ms=2_001,
            )
            decremented = active_states(self.store, db, character["id"], now_ms=2_001)
            self.assertEqual(
                (decremented[0]["uid"], decremented[0]["level"]), (state_uid, 299)
            )

            # Another item's effect with the same removal event has no
            # exclusion and therefore retires the accumulated counter.
            emit_events(
                self.store,
                db,
                character["id"],
                [{"event_id": 2165, "effect_id": 293341}],
                generation=generation,
                now_ms=2_002,
            )
            self.assertEqual(
                active_states(self.store, db, character["id"], now_ms=2_002), ()
            )

    def test_native_vital_energy_return_keeps_four_charges_after_result_events(self):
        from wakfu_server.consumable_catalog import load_plan

        _account, generation, character, source = self.fixture(source_reference=18422)
        with self.store.connection() as db:
            plan = load_plan(db, 18422)
            state = apply_states(
                self.store,
                db,
                character["id"],
                plan["states"],
                source_item_ref=18422,
                source_item_uid=source["uid"],
                generation=generation,
                now_ms=1000,
            )[0]
            self.assertEqual((state["clock"], state["level"]), ("event", 5))
            enter_combat(
                self.store, db, character["id"], 55, generation=generation, now_ms=1000
            )
            returned = return_from_combat(
                self.store,
                db,
                character["id"],
                55,
                [
                    dict(
                        uid=state["uid"],
                        state_id=2786,
                        removed=False,
                        level=4,
                        clock="event",
                        remaining_ms=0,
                    )
                ],
                generation=generation,
                now_ms=2000,
            )
            self.assertEqual(
                (returned[0]["uid"], returned[0]["level"]), (state["uid"], 4)
            )
            for _retry in range(2):
                current = emit_events(
                    self.store,
                    db,
                    character["id"],
                    (1030, 1043),
                    generation=generation,
                    now_ms=2000,
                    fight_model=2,
                )
                self.assertEqual(
                    (
                        current[0]["level"],
                        current[0]["clock"],
                        current[0]["remaining_ms"],
                    ),
                    (4, "event", 0),
                )
            with self.assertRaisesRegex(ValueError, "Foreign or duplicate"):
                return_from_combat(
                    self.store,
                    db,
                    character["id"],
                    55,
                    [
                        dict(
                            uid=state["uid"],
                            state_id=2786,
                            removed=False,
                            level=3,
                            clock="event",
                            remaining_ms=0,
                        )
                    ],
                    generation=generation,
                    now_ms=2000,
                )

    def test_native_fight_counter_foods_decrement_on_matching_world_return(self):
        from wakfu_server.inventory_consumable_effects import use
        from wakfu_server.inventory_items import grant
        import struct

        account = self.store.register("four-fight-counter-foods", "local-password")[
            "id"
        ]
        character = self.store.create_character(account, "Counter Food Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        character = self.store.character(account, character["id"])
        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        refs_and_states = ((18351, 2752), (18355, 2765), (18401, 2760), (18406, 2766))
        for slot, (item_ref, state_id) in enumerate(refs_and_states):
            with self.subTest(item_ref=item_ref):
                source = grant(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    reference=item_ref,
                    quantity=2,
                    container=bag["uid"],
                    slot=slot,
                    allowed_references={item_ref},
                )
                before = self.store.character(account, character["id"])
                used = use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qB", source["uid"], 0),
                    expected_hp=before["hp"],
                    in_fight=False,
                )
                self.assertTrue(used["applied"])
                state = next(
                    row
                    for row in used["character"]["consumable_states"]
                    if row["state_id"] == state_id
                )
                self.assertEqual(state["level"], 5)
                self.assertEqual(state["clock"], "event")
                self.assertEqual(
                    next(
                        row["quantity"]
                        for row in used["character"]["inventory_items"]
                        if row["uid"] == source["uid"]
                    ),
                    1,
                )

                fight_id = 8_300 + item_ref
                with self.store.connection() as db:
                    enter_combat(
                        self.store,
                        db,
                        character["id"],
                        fight_id,
                        generation=generation,
                        now_ms=10_000,
                    )
                    unchanged = return_from_combat(
                        self.store,
                        db,
                        character["id"],
                        fight_id,
                        [
                            dict(
                                uid=state["uid"],
                                state_id=state_id,
                                removed=False,
                                level=5,
                                clock="event",
                                remaining_ms=0,
                            )
                        ],
                        generation=generation,
                        now_ms=10_001,
                    )
                    self.assertEqual(unchanged[0]["level"], 5)
                    # The counter criterion excludes model1; the real supported
                    # fight return (model2) spends one charge and preserves the
                    # item plan metadata/roots for its next eligible fight.
                    model_one = emit_events(
                        self.store,
                        db,
                        character["id"],
                        (1030, 1043),
                        generation=generation,
                        now_ms=10_002,
                        fight_model=1,
                    )
                    self.assertEqual(model_one[0]["level"], 5)
                    spent = emit_events(
                        self.store,
                        db,
                        character["id"],
                        (1030, 1043),
                        generation=generation,
                        now_ms=10_003,
                        fight_model=2,
                    )
                    self.assertEqual(
                        (spent[0]["uid"], spent[0]["level"]), (state["uid"], 4)
                    )
                    self.assertEqual(spent[0]["metadata"], state["metadata"])
                    with self.assertRaisesRegex(ValueError, "Foreign or duplicate"):
                        return_from_combat(
                            self.store,
                            db,
                            character["id"],
                            fight_id,
                            [
                                dict(
                                    uid=state["uid"],
                                    state_id=state_id,
                                    removed=False,
                                    level=5,
                                    clock="event",
                                    remaining_ms=0,
                                )
                            ],
                            generation=generation,
                            now_ms=10_004,
                        )
                    retire_states(
                        self.store,
                        db,
                        character["id"],
                        state_ids=(state_id,),
                        now_ms=10_005,
                    )
