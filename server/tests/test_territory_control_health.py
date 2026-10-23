"""Regional health contributions must change maximum HP without free healing."""
import unittest
from unittest.mock import Mock, patch

from wakfu_server import territory_bonuses, equipment_stats, health, wire


class TerritoryControlHealthTests(unittest.TestCase):
    def character(self):
        return dict(
            id=1,
            account_id=1,
            breed=8,
            level=6,
            hp=41,
            map_id=527,
            x=1,
            y=2,
            z=0,
            inventory_items=[],
            builds={
                0: dict(equipment="", sheet=wire.proto_field(24, (1 << 64) - 1).hex())
            },
        )

    def test_native_control_health_transitions_do_not_stack_or_heal(self):
        original = self.character()
        baseline = equipment_stats.effective_character(original)
        for delta in (1, 2, -1, 0, 1, 0):
            with self.subTest(delta=delta):
                projected = dict(original, territory_stat_bonuses={1: delta})
                actual = equipment_stats.effective_character(projected)
                self.assertEqual(actual["max_hp"], baseline["max_hp"] + delta)
                self.assertEqual(actual["hp"], original["hp"])
                self.assertEqual(
                    equipment_stats.effective_character(actual)["max_hp"],
                    actual["max_hp"],
                )
                packet = wire.owned_public_characteristics(projected)
                import struct

                count = struct.unpack_from(">H", packet)[0]
                rows = [
                    struct.unpack_from(">Biiii", packet, 2 + i * 17)
                    for i in range(count)
                ]
                hp = next(row for row in rows if row[0] == 1)
                self.assertEqual(hp[3], actual["max_hp"])
        self.assertNotIn("territory_stat_bonuses", original)

    def test_policy_has_no_missing_database_fallback(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        with self.assertRaisesRegex(ValueError, "health policy"):
            territory_bonuses.control_health_policy(db)
        db.execute.return_value.fetchone.return_value = {
            "value": {"schema_version": 1, "states": {"1915": 1, "1916": 2, "1917": -1}}
        }
        self.assertEqual(territory_bonuses.control_health_policy(db)["1915"], 1)

    def test_health_follows_each_native_satisfaction_state(self):
        policy = {"1915": 1, "1916": 2, "1917": -1}
        for state, value in policy.items():
            self.assertEqual(
                territory_bonuses.stat_bonuses(
                    {"state_id": int(state), "effects": []}, health_policy=policy
                ),
                {1: value},
            )
        self.assertEqual(territory_bonuses.stat_bonuses(None, health_policy=policy), {})

    def test_native_permanent_state_icons_change_without_applying_characteristics(self):
        from wakfu_server.territory_bonus_wire import _STATES, _records, delta, snapshot

        expected = {
            1915: (94088, 94089, 94331, 94332),
            1916: (94090, 94091, 94329, 94330),
            1917: (252635, 252636, 252637, 252638),
        }
        for state in (1915, 1916, 1917):
            with self.subTest(state=state):
                records = _records(40, state)
                self.assertEqual(
                    expected[state], tuple(row[0] for row in _STATES[state])
                )
                self.assertEqual(
                    (
                        310,
                        166 if state != 1917 else 167,
                        162 if state != 1917 else 163,
                        2007,
                        2008,
                    ),
                    tuple(row[1] for row in records),
                )
                self.assertEqual(5, len({row[0] for row in records}))
                packets = snapshot(
                    40, state, allocate_action=iter(range(1, 20)).__next__
                )
                self.assertEqual(
                    [12613] * 5 + [13420], [opcode for opcode, _ in packets]
                )
                self.assertEqual(6, len({payload for _, payload in packets}))
        changed = delta(40, 1915, 1916, allocate_action=iter(range(30, 60)).__next__)
        self.assertEqual(
            [13560] * 5 + [12613] * 5 + [13420], [opcode for opcode, _ in changed]
        )
        removed = delta(40, 1917, None, allocate_action=iter(range(60, 80)).__next__)
        self.assertEqual([13560] * 5 + [13420], [opcode for opcode, _ in removed])

    def test_attached_actor_enters_combat_with_matching_owned_maximum(self):
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import build_player_snapshot

        original = equipment_stats.effective_character(self.character())
        baseline = original["max_hp"]
        policy = {"1915": 1, "1916": 2, "1917": -1}
        for state, delta in ((1915, 1), (1916, 2), (1917, -1), (None, 0)):
            region = None if state is None else {"state_id": state, "effects": []}
            with self.subTest(state=state), patch.object(
                territory_bonuses, "current_region", return_value=region
            ), patch.object(
                territory_bonuses, "control_health_policy", return_value=policy
            ):
                attached = territory_bonuses.attach_character(object(), original)
                self.assertEqual(attached["max_hp"], baseline + delta)
                self.assertEqual(attached["hp"], original["hp"])
                actor = Actor(
                    1,
                    0,
                    (1, 2, 0),
                    attached["hp"],
                    6,
                    3,
                    0,
                    6,
                    owner_id=1,
                    controlled=True,
                    max_hp=attached["max_hp"],
                )
                snapshot = build_player_snapshot(
                    attached, actor, wp_current=6, wp_maximum=6, running_effects=()
                )
                snapshot.install(actor)
                self.assertEqual(actor.max_hp, baseline + delta)
                self.assertEqual(
                    territory_bonuses.attach_character(object(), attached)["max_hp"],
                    baseline + delta,
                )
        self.assertNotIn("territory_stat_bonuses", original)


from postgres_case import PostgresCase


class TerritoryControlHealthPostgresTests(PostgresCase):
    """Isolated HP/lease component; no ecosystem or full-battle qualification."""

    def test_owned_region_health_lifecycle_preserves_wounds_regeneration_and_main_hero_sessions(
        self,
    ):
        from copy import deepcopy
        from types import SimpleNamespace
        from psycopg.types.json import Jsonb
        from wakfu_server import health_store, health_policy, heroes, fight_store
        from wakfu_server.combat_heroes import player_actor, admit_owned_heroes
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_health import persist_owned

        store = self.store
        clock = [1000.0]
        store.clock = lambda: clock[0]
        account = store.register("territory-health-owner", "test-password")["id"]
        main = store.create_character(account, "Territory Main")
        hero = store.create_character(account, "Territory Hero")
        generation = store.begin_session(account)
        store.select_character(account, generation, main["id"])
        identities = (main["id"], hero["id"])
        with store.connection() as db:
            # Explicit isolated policy only; the actual runtime policy is not
            # touched. First reproduce the old projection-versus-CAS mismatch.
            db.execute(
                "UPDATE settings SET value=%s WHERE name='territory_control_health_policy'",
                (
                    Jsonb(
                        dict(schema_version=1, states={"1915": 0, "1916": 0, "1917": 0})
                    ),
                ),
            )
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=30,y=0,z=0 WHERE id=ANY(%s)",
                (list(identities),),
            )
        heroes.add(store, account, generation, main["id"], hero["id"])
        region_states = {10: 1916, 20: 1917}

        def region(_db, character):
            state = region_states.get(character["x"])
            return (
                None
                if state is None
                else dict(territory_id=17, map_id=527, state_id=state, effects=[])
            )

        with patch.object(territory_bonuses, "current_region", side_effect=region):
            main = health_store.initialize(
                store, account, generation, main["id"], coefficient=1, now_ms=1000000
            )
            base = main["max_hp"]
            self.assertEqual(main["hp"], base)
            with store.connection() as db:
                raw = store.character(account, main["id"], db)
                legacy = dict(raw, territory_stat_bonuses={1: -1})
                legacy.pop("territory_health_projection", None)
                legacy = equipment_stats.effective_character(legacy)
                self.assertEqual((legacy["hp"], legacy["max_hp"]), (base - 1, base - 1))
                with self.assertRaisesRegex(
                    ValueError, "Stale canonical health transition"
                ):
                    with db.transaction():
                        health_policy.apply(db, legacy, legacy["hp"] - 1)
                self.assertEqual(
                    db.execute(
                        "SELECT hp FROM characters WHERE id=%s", (main["id"],)
                    ).fetchone()["hp"],
                    base,
                )
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='territory_control_health_policy'",
                    (
                        Jsonb(
                            dict(
                                schema_version=1,
                                states={"1915": 1, "1916": 2, "1917": -1},
                            )
                        ),
                    ),
                )
                for identity, wound in ((main["id"], 10), (hero["id"], 17)):
                    character = store.character(account, identity, db)
                    health_policy.apply(db, character, character["hp"] - wound)
            main = health_store.initialize(
                store, account, generation, main["id"], coefficient=1, now_ms=1000000
            )

            def canonical(identity):
                character = store.character(account, identity)
                with store.connection() as db:
                    row = db.execute(
                        "SELECT hp,max_hp,hp_damage,health_dead,hp_zero_valid FROM characters WHERE id=%s",
                        (identity,),
                    ).fetchone()
                self.assertEqual(tuple(character[k] for k in row), tuple(row.values()))
                return character

            def observe(identity, x, *, lease=None):
                with store.connection() as db:
                    db.execute("UPDATE characters SET x=%s WHERE id=%s", (x, identity))
                character = canonical(identity)
                return territory_bonuses.reconcile_owned(
                    store,
                    account,
                    lease or generation,
                    character,
                    selected_character_id=main["id"],
                )

            entered = observe(main["id"], 10)
            self.assertEqual(
                (entered["hp"], entered["max_hp"], entered["hp_damage"]),
                (base - 10, base + 2, 12),
            )
            self.assertEqual(entered["territory_health_projection"]["applied_flat"], 2)
            with store.connection() as db:
                regen_before = dict(
                    db.execute(
                        "SELECT * FROM character_regeneration WHERE character_id=%s",
                        (main["id"],),
                    ).fetchone()
                )
            repeated = observe(main["id"], 10)
            self.assertEqual(
                repeated["territory_health_projection"],
                entered["territory_health_projection"],
            )
            with store.connection() as db:
                self.assertEqual(
                    dict(
                        db.execute(
                            "SELECT * FROM character_regeneration WHERE character_id=%s",
                            (main["id"],),
                        ).fetchone()
                    ),
                    regen_before,
                )
            clock[0] += 4
            ticked = health_store.tick(
                store,
                account,
                generation,
                main["id"],
                entered["hp"],
                now_ms=int(clock[0] * 1000),
            )
            gained = min(12, regen_before["coefficient"])
            self.assertEqual(
                (ticked["hp"], ticked["hp_damage"]),
                (entered["hp"] + gained, 12 - gained),
            )
            healed = health_store.sync(
                store,
                account,
                generation,
                main["id"],
                ticked["hp"],
                ticked["hp"] + 2,
                now_ms=int(clock[0] * 1000),
            )
            damaged = health_store.sync(
                store,
                account,
                generation,
                main["id"],
                healed["hp"],
                healed["hp"] - 5,
                now_ms=int(clock[0] * 1000),
            )
            self.assertEqual(damaged["hp_damage"], ticked["hp_damage"] + 3)
            actual_hp = damaged["hp"]
            malus = observe(main["id"], 20)
            self.assertEqual((malus["hp"], malus["max_hp"]), (actual_hp, base - 1))
            outside = observe(main["id"], 30)
            self.assertEqual((outside["hp"], outside["max_hp"]), (actual_hp, base))
            self.assertIsNone(outside["territory_health_projection"]["state_id"])
            self.assertEqual(outside["territory_health_projection"]["applied_flat"], 0)
            main = observe(main["id"], 10)
            hero_state = observe(hero["id"], 20)
            self.assertEqual(
                (hero_state["hp"], hero_state["max_hp"]), (base - 17, base - 1)
            )
            self.assertEqual(main["max_hp"], base + 2)
            self.assertEqual(
                canonical(main["id"])["territory_health_projection"]["state_id"], 1916
            )
            self.assertEqual(
                canonical(hero["id"])["territory_health_projection"]["state_id"], 1917
            )

            # Real owned placement/admission and native player HP snapshots.
            # The tiny enemy/arena is a declared health-boundary component;
            # no original species, paid spell or full battle is claimed.
            main = canonical(main["id"])
            fight_id = fight_store.create(store, account, generation, main["id"])
            leader = player_actor(main, 0)
            x, y, z = leader.position
            cells = [(x + i, y, z) for i in range(4)]
            enemy = Actor(-700, 1, cells[3], 40, 6, 3, 0, 1)
            fight = Fight(
                fight_id, [leader, enemy], cells, {0: set(cells[:2]), 1: {cells[3]}}
            )
            session = SimpleNamespace(
                account_id=account,
                generation=generation,
                character_id=main["id"],
                map_id=527,
                instance_id=0,
            )
            with store.connection() as db:
                admission = admit_owned_heroes(db, store, session, fight)
            fight = admission["fight"]
            self.assertIn(hero["id"], fight.actors)
            entries = {identity: canonical(identity) for identity in identities}
            for identity in identities:
                self.assertEqual(
                    fight.actors[identity].max_hp, entries[identity]["max_hp"]
                )
                self.assertEqual(
                    fight.actors[identity].effect_maxima[1], entries[identity]["max_hp"]
                )
                self.assertEqual(
                    entries[identity]["territory_health_projection"]["applied_flat"], 2
                )
            with store.connection() as db:
                members = db.execute(
                    "SELECT character_id,session_generation,entry_hp,entry_max_hp FROM combat_fight_participants WHERE fight_id=%s ORDER BY character_id",
                    (fight_id,),
                ).fetchall()
                self.assertEqual({r["character_id"] for r in members}, set(identities))
                for row in members:
                    self.assertEqual(
                        (
                            row["session_generation"],
                            row["entry_hp"],
                            row["entry_max_hp"],
                        ),
                        (
                            generation,
                            entries[row["character_id"]]["hp"],
                            entries[row["character_id"]]["max_hp"],
                        ),
                    )
            fight.ready(account)
            fight_store.activate(store, account, generation, main["id"], fight_id)
            fight.apply_effect_damage(enemy.id, main["id"], 6)
            fight.apply_effect_healing(main["id"], hero["id"], 4)
            fight.apply_effect_damage(main["id"], enemy.id, enemy.hp)
            self.assertEqual((fight.phase, fight.winner), ("finished", 0))
            with store.connection() as db:
                fight_store.finish(store, db, account, generation, main["id"], fight_id)
            returned = persist_owned(
                store, account, generation, entries[main["id"]], fight
            )
            self.assertTrue(returned["applied"])
            self.assertEqual(
                returned["characters"][main["id"]]["hp"], entries[main["id"]]["hp"] - 6
            )
            self.assertEqual(
                returned["characters"][hero["id"]]["hp"], entries[hero["id"]]["hp"] + 4
            )
            returned_hp = {
                identity: canonical(identity)["hp"] for identity in identities
            }
            duplicate = persist_owned(
                store, account, generation, entries[main["id"]], fight
            )
            self.assertFalse(duplicate["applied"])
            self.assertEqual(
                {identity: canonical(identity)["hp"] for identity in identities},
                returned_hp,
            )
            main = canonical(main["id"])
            old_snapshot = deepcopy(main)
            current = health_store.sync(
                store,
                account,
                generation,
                main["id"],
                main["hp"],
                main["hp"] + 1,
                now_ms=int(clock[0] * 1000),
            )
            self.assertFalse(
                persist_owned(store, account, generation, entries[main["id"]], fight)[
                    "applied"
                ]
            )
            self.assertEqual(canonical(main["id"])["hp"], current["hp"])
            with self.assertRaisesRegex(
                ValueError, "Stale owned territorial health observation"
            ):
                territory_bonuses.reconcile_owned(
                    store, account, generation, old_snapshot
                )
            outside = observe(main["id"], 30)
            self.assertEqual(outside["hp"], current["hp"])
            self.assertEqual(outside["max_hp"], base)
            old_generation = generation
            generation = store.begin_session(account, previous_generation=generation)
            store.select_character(account, generation, main["id"])
            reconnected = health_store.initialize(
                store,
                account,
                generation,
                main["id"],
                coefficient=0,
                now_ms=int(clock[0] * 1000),
            )
            self.assertEqual(
                (reconnected["hp"], reconnected["max_hp"]), (outside["hp"], base)
            )
            with self.assertRaises(ValueError):
                territory_bonuses.reconcile_owned(
                    store, account, old_generation, reconnected
                )
            with self.assertRaises(ValueError):
                health_store.sync(
                    store,
                    account,
                    old_generation,
                    main["id"],
                    reconnected["hp"],
                    reconnected["hp"] - 1,
                )
            self.assertEqual(canonical(main["id"])["hp"], reconnected["hp"])

    def test_food_territory_projection_preserves_canonical_wounds_and_native_raw_receipts(
        self,
    ):
        native_region = patch.object(
            territory_bonuses, "current_region", return_value=None
        )
        native_region.start()
        self.addCleanup(native_region.stop)
        from copy import deepcopy
        from psycopg.types.json import Jsonb
        from wakfu_server import health_store, equipment_hp_lifecycle as lifecycle
        from wakfu_server.consumable_buffs import apply_states, retire_states
        from wakfu_server.consumable_characteristics import reconcile_health
        from wakfu_server.combat_heroes import player_actor

        store = self.store
        account = store.register("territory-food-owner", "test-password")["id"]
        character = store.create_character(account, "Territory Food")
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        character = health_store.initialize(
            store, account, generation, character["id"], coefficient=0
        )
        base = character["max_hp"]
        with store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='territory_control_health_policy'",
                (
                    Jsonb(
                        dict(
                            schema_version=1, states={"1915": 1, "1916": 2, "1917": -1}
                        )
                    ),
                ),
            )
        with patch.object(territory_bonuses, "current_region", return_value=None):
            character = territory_bonuses.reconcile_owned(
                store, account, generation, character
            )
        base = character["max_hp"]
        with store.connection() as db:
            descriptor = db.execute(
                "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=8215"
            ).fetchone()["state"]
            # This installs the original native descriptor, not an inventory
            # consumption or paid-food interaction claim.
            apply_states(
                store,
                db,
                character["id"],
                [descriptor],
                source_item_ref=8215,
                source_item_uid=8215,
                generation=generation,
            )
        character = health_store.initialize(
            store, account, generation, character["id"], coefficient=0
        )
        food_maximum = character["max_hp"]
        self.assertGreater(food_maximum, base)
        self.assertEqual(equipment_stats.effective_character(character)["max_hp"], base)
        character = health_store.sync(
            store,
            account,
            generation,
            character["id"],
            character["hp"],
            food_maximum - 10,
        )
        with store.connection() as db:
            lifecycle.save(
                db,
                character["id"],
                lifecycle.OwnedEwoHPReplay(
                    lifecycle.NativeHPActor(character["hp"], base)
                ),
                expected_revision=None,
            )
        character = store.character(account, character["id"])
        region = dict(
            territory_id=17, map_id=character["map_id"], state_id=1916, effects=[]
        )
        with patch.object(territory_bonuses, "current_region", return_value=region):
            entered = territory_bonuses.reconcile_owned(
                store, account, generation, character
            )
            self.assertEqual(
                (entered["hp"], entered["max_hp"], entered["hp_damage"]),
                (food_maximum - 10, food_maximum + 2, 12),
            )
            with store.connection() as db:
                attached = territory_bonuses.attach_character(db, entered)
                projection = lifecycle.load(db, character["id"])
            self.assertEqual(attached["max_hp"], base + 2)
            actor = player_actor(attached, 0)
            self.assertEqual(
                (actor.hp, actor.max_hp), (attached["hp"], attached["max_hp"])
            )
            self.assertEqual(projection["receipts"], [])
            reopened = self.reopen().character(account, character["id"])
            self.assertEqual(
                (reopened["hp"], reopened["max_hp"], reopened["hp_damage"]),
                (entered["hp"], entered["max_hp"], 12),
            )
            repeated = territory_bonuses.reconcile_owned(
                store, account, generation, reopened
            )
            self.assertEqual(
                repeated["equipment_hp_projection"], entered["equipment_hp_projection"]
            )
            with store.connection() as db:
                retire_states(
                    store, db, character["id"], state_ids=[descriptor["state_id"]]
                )
                reconcile_health(db, store.character(account, character["id"], db))
            expired = store.character(account, character["id"])
            self.assertEqual(
                (expired["hp"], expired["max_hp"], expired["hp_damage"]),
                (base - 10, base + 2, 12),
            )

        # Persisted chance receipts and exact latent raw values are independent
        # of a maximum-only territorial projection. These are declared PA
        # component fixtures, not claims of equipped native item acquisition.
        for raw_current, damage, zero_valid in (
            (-9, base, True),
            (base + 25, 0, False),
        ):
            with self.subTest(raw_current=raw_current), store.connection() as db:
                with db.transaction(force_rollback=True):
                    db.execute(
                        "DELETE FROM character_equipment_hp_projection WHERE character_id=%s",
                        (character["id"],),
                    )
                    raw = lifecycle.NativeHPActor(raw_current, base)
                    replay = lifecycle.OwnedEwoHPReplay(raw)
                    replay.apply(
                        dict(
                            source_uid=991,
                            slot=4,
                            effect_index=0,
                            amount=50,
                            definition_type=0,
                            restore_current=True,
                            reduce_current=True,
                            chance=50,
                            chance_roll=99,
                        )
                    )
                    receipts = deepcopy(replay.plain_receipts())
                    lifecycle.save(db, character["id"], replay, expected_revision=None)
                    before = dict(
                        expired,
                        consumable_states=[],
                        equipment_hp_projection=None,
                        territory_health_projection=None,
                        hp=max(0, min(base, raw_current)),
                        max_hp=base,
                        hp_damage=damage,
                        hp_zero_valid=zero_valid,
                        health_dead=False,
                    )
                    # A lower maximum does not reveal over-cap HP or change
                    # visible zero, so native raw current must remain exact.
                    after = dict(
                        before,
                        territory_health_projection={"applied_flat": -1},
                        max_hp=base - 1,
                        hp=max(0, min(base - 1, raw_current)),
                        hp_damage=damage - 1 if damage else 0,
                    )
                    lifecycle.reconcile_territory_projection(
                        db, before, after, hp=after["hp"]
                    )
                    saved = lifecycle.load(db, character["id"])
                    self.assertEqual(
                        saved["actor"].plain()["raw_current"],
                        raw_current if raw_current < 0 else raw_current - 1,
                    )
                    self.assertEqual(saved["actor"].plain()["raw_maximum"], base - 1)
                    self.assertEqual(saved["receipts"], receipts)
