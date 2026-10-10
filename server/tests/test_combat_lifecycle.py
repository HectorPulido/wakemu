import struct
import tempfile
from psycopg.pq import TransactionStatus
from postgres_case import PostgresCase
from tests import test_combat_rewards
from wakfu_server.combat_lifecycle import (
    policy_from_env,
    prepare_finish,
    return_to_world,
)
from wakfu_server.combat_rewards import Policy
from wakfu_server.progression import level_xp
from wakfu_server import health_store, health


class LifecycleTests(PostgresCase):
    def test_same_account_heroes_each_receive_rewards_with_one_native_result(self):
        from unittest.mock import patch
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_lifecycle import prepare_finish_shared
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server import combat_results

        (
            store,
            account,
            main,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        hero = store.create_character(account, "Reward Hero")
        fight.actors[hero["id"]] = Actor(
            hero["id"],
            0,
            (2, 0, 0),
            hero["hp"],
            6,
            3,
            80,
            hero["level"],
            account,
            True,
            max_hp=hero["max_hp"],
        )
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s WHERE fight_id=%s",
                (generation, fight.id),
            )
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (fight.id, hero["id"], account, generation),
            )
        metadata = {
            character["id"]: dict(
                kind="player",
                account_id=account,
                name=character["name"],
                breed=character["breed"],
                is_male=character["sex"] == 0,
            )
            for character in (main, hero)
        }
        metadata[-200] = dict(kind="monster", ref=5525)

        def settle():
            return prepare_finish_shared(
                store,
                account,
                generation,
                main["id"],
                RuntimeMessages(fight),
                metadata,
                duration_ms=100,
                fight_instance_id=fight.id,
                policy_resolver=lambda db, member, source: Policy(xp=10, kamas=3),
                loot_resolver=lambda db, member, reward: dict(
                    loots=[],
                    packets=[(13713, struct.pack(">q", member["character_id"]))],
                ),
                expected_accounts={account},
                owner_character_ids={account: main["id"]},
            )

        with patch.object(
            combat_results, "finish_messages", wraps=combat_results.finish_messages
        ) as report:
            packets = settle()[account]
            self.assertEqual(report.call_count, 1)
            self.assertEqual(report.call_args.kwargs["initiator_id"], main["id"])
        self.assertEqual(sum(opcode == 12755 for opcode, _ in packets), 1)
        self.assertEqual(sum(opcode == 13420 for opcode, _ in packets), 1)
        self.assertEqual(
            [
                struct.unpack(">q", body)[0]
                for opcode, body in packets
                if opcode == 13713
            ],
            [main["id"], hero["id"]],
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
                2,
            )
        self.assertEqual(store.character(account, main["id"])["kamas"], 6)
        self.assertEqual(store.character(account, hero["id"])["xp"], hero["xp"] + 10)
        settle()
        self.assertEqual(store.character(account, main["id"])["kamas"], 6)

    def test_shared_level_up_keeps_pre_award_drop_context_frozen(self):
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_lifecycle import prepare_finish_shared
        from wakfu_server.combat_reward_context import settlement_contexts
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.reward_policy import resolve as resolve_reward_policy
        from wakfu_server import combat_drops

        (
            store,
            account,
            character,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (generation, fight.id, character["id"]),
            )

        owned = effective_character(store.character(account, character["id"]))
        player = fight.actors[character["id"]]
        build_player_snapshot(
            owned, player, wp_current=6, wp_maximum=6, running_effects=()
        ).install(player)
        monsters = [{"id": -200, "ref": 5525, "level": 1}]
        metadata = {
            character["id"]: dict(
                kind="player",
                account_id=account,
                name=character["name"],
                breed=character["breed"],
                is_male=character["sex"] == 0,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        runtime = RuntimeMessages(fight)
        contexts = {}
        drop_replays = []

        def policy_resolver(db, member, source):
            reward_context, drop_context = settlement_contexts(
                db, fight, source, monsters
            )
            contexts[member["character_id"]] = (reward_context, drop_context)
            decision = resolve_reward_policy(
                store,
                db,
                account_id=member["account_id"],
                generation=member["session_generation"],
                character_id=member["character_id"],
                fight_id=fight.id,
                context=reward_context,
                kamas_roll_index=0,
            )
            return decision.policy

        def loot_resolver(db, member, reward):
            current = store.character(account, character["id"], db)
            self.assertEqual(current["level"], 2)
            drop_context = contexts[character["id"]][1]
            batch = combat_drops.resolve(
                store,
                db,
                account_id=account,
                generation=generation,
                character_id=character["id"],
                fight_id=fight.id,
                monsters=[{"actor_id": -200, "reference": 5525}],
                prospecting_bonus=combat_drops.native_prospection_bonus(player),
                can_loot=False,
                fight_context=drop_context,
            )
            drop_replays.append(batch.replayed)
            return {"loots": combat_drops.report_loots(batch), "packets": []}

        def settle():
            return prepare_finish_shared(
                store,
                account,
                generation,
                character["id"],
                runtime,
                metadata,
                duration_ms=100,
                fight_instance_id=fight.id,
                policy_resolver=policy_resolver,
                loot_resolver=loot_resolver,
                expected_accounts={account},
            )

        settled = settle()
        self.assertEqual(set(settled), {account})
        self.assertEqual(contexts[character["id"]][1]["downscaled"], False)
        after = store.character(account, character["id"])
        self.assertEqual(after["level"], 2)
        self.assertGreater(after["xp"], character["xp"])
        with store.connection() as db:
            policy = db.execute(
                "SELECT snapshot FROM fight_reward_policy_receipts "
                "WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            self.assertIsNotNone(policy)
            self.assertEqual(
                policy["snapshot"]["context"], contexts[character["id"]][0]
            )
            drop = db.execute(
                "SELECT snapshot FROM fight_drop_awards "
                "WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
        self.assertIsNotNone(drop)
        self.assertFalse(drop["snapshot"]["fight_context"]["downscaled"])
        replay = settle()
        self.assertEqual(set(replay), {account})
        self.assertEqual(drop_replays, [False, True])
        self.assertEqual(store.character(account, character["id"])["xp"], after["xp"])
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["count"],
                1,
            )

    def test_loot_failure_rolls_back_finish_and_reward_in_same_transaction(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        (
            store,
            account,
            char,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
            )
        before = store.character(account, char["id"])
        runtime = RuntimeMessages(fight)
        runtime.awaiting_ack = 19
        pending = [(900, b"pending")]
        runtime.pending = pending
        metadata = {
            char["id"]: dict(
                kind="player",
                account_id=account,
                name=char["name"],
                breed=char["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        calls = []

        def fail_after_reward(db, reward):
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
            self.assertTrue(reward["awarded"])
            self.assertGreater(reward["xp"], 0)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["count"],
                1,
            )
            calls.append(reward)
            raise ValueError("Injected committed-loot resolution failure")

        with self.assertRaisesRegex(ValueError, "loot resolution failure"):
            prepare_finish(
                store,
                account,
                generation,
                char,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=8,
                policy=Policy(101, 13),
                loot_resolver=fail_after_reward,
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual((runtime.awaiting_ack, runtime.pending), (19, pending))
        after = store.character(account, char["id"])
        for key in ("level", "xp", "hp", "max_hp", "kamas", "builds"):
            self.assertEqual(after[key], before[key], key)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["count"],
                0,
            )

    def test_committed_loot_is_in_native_report_and_packets_follow_result(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.wire import proto_fields

        (
            store,
            account,
            char,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        runtime = RuntimeMessages(fight)
        metadata = {
            char["id"]: dict(
                kind="player",
                account_id=account,
                name=char["name"],
                breed=char["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        calls = []

        def commit_loot(db, reward):
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
            self.assertTrue(reward["awarded"])
            calls.append(reward)
            return {
                "loots": [
                    dict(reference=2026, quantity=2),
                    dict(reference=27083, quantity=1, is_purse_loot=True),
                ],
                "packets": [(13052, b"owned loot update")],
            }

        result = prepare_finish(
            store,
            account,
            generation,
            char,
            runtime,
            metadata,
            duration_ms=1000,
            fight_instance_id=8,
            policy=Policy(),
            loot_resolver=commit_loot,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            [opcode for opcode, _ in result["packets"]], [12238, 12755, 13052]
        )
        self.assertEqual(result["packets"][-1], (13052, b"owned loot update"))
        self.assertEqual(
            result["metadata"][char["id"]]["loots"],
            [
                dict(reference=2026, quantity=2),
                dict(reference=27083, quantity=1, is_purse_loot=True),
            ],
        )

        report = dict(proto_fields(result["packets"][1][1][12:]))
        team = dict(proto_fields(report[42]))
        player_fields = list(proto_fields(team[18]))
        serialized_loots = [
            dict(proto_fields(value)) for tag, value in player_fields if tag == 58
        ]
        self.assertEqual(
            serialized_loots,
            [
                {8: 2026, 16: 2, 24: 0, 32: 0},
                {8: 27083, 16: 1, 24: 1, 32: 0},
            ],
        )

    def test_real_reward_drop_and_delivery_pipeline_commits_or_rolls_back_together(
        self,
    ):
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_drop_delivery import apply, temporary_update
        from wakfu_server.combat_drops import report_loots, resolve as resolve_drops
        from wakfu_server.combat_reward_context import build_context
        from wakfu_server.combat_results import _loots
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.inventory_bag_rules import RULES as BAG_RULES
        from wakfu_server.inventory_items import equipment_inventory
        from wakfu_server.inventory_move import synchronization
        from wakfu_server.monsters import owned_instance
        from wakfu_server.reward_policy import resolve as resolve_reward_policy

        (
            store,
            account,
            char,
            generation,
            original_fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        character = effective_character(store.character(account, char["id"]))
        player_position, monster_position = (0, 0, 0), (1, 0, 0)
        player = Actor(
            char["id"],
            0,
            player_position,
            character["hp"],
            6,
            3,
            100,
            character["effective_level"],
            account,
            True,
            max_hp=character["max_hp"],
        )
        build_player_snapshot(
            character, player, wp_current=6, wp_maximum=6, running_effects=()
        ).install(player)
        monster = owned_instance(
            44,
            23,
            -200,
            map_id=1134,
            x=monster_position[0],
            y=monster_position[1],
            z=monster_position[2],
        )
        npc = Actor(
            monster["id"],
            1,
            monster_position,
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            monster["level"],
        )
        fight = Fight(
            original_fight.id,
            [player, npc],
            [player_position, monster_position],
            {0: {player_position}, 1: {monster_position}},
        )
        fight.phase, fight.winner = "finished", 0
        runtime = RuntimeMessages(fight)
        runtime.awaiting_ack = 23
        pending = [(900, b"queued before finish")]
        runtime.pending = pending
        metadata = {
            player.id: dict(
                kind="player",
                account_id=account,
                name=char["name"],
                breed=char["breed"],
                is_male=char["sex"] == 0,
            ),
            npc.id: dict(kind="monster", ref=monster["ref"]),
        }
        monsters = [monster]
        rng = lambda upper: 0

        # Leave one ordinary bag slot: the first eligible drop fits and the
        # remaining successes must stay in the temporary inventory.
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s",
                (fight.id,),
            )
            containers = db.execute(
                "SELECT * FROM inventory_containers WHERE character_id=%s "
                "ORDER BY kind,uid",
                (char["id"],),
            ).fetchall()
            eligible = []
            for row in containers:
                if row["kind"] == 0:
                    eligible.append(row)
                    continue
                rule = BAG_RULES.get(row["reference"])
                if (
                    rule is not None
                    and not rule["accepted_types"]
                    and not rule["has_equip_criteria"]
                ):
                    eligible.append(row)
            free_slot = True
            for row in eligible:
                for slot in range(row["capacity"]):
                    if free_slot:
                        free_slot = False
                        continue
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2021,1,%s,%s)",
                        (char["id"], row["uid"], slot),
                    )
            starting_items = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s ORDER BY uid",
                (char["id"],),
            ).fetchall()

        def policy_resolver(db):
            context = build_context(fight, character, monsters)
            return resolve_reward_policy(
                store,
                db,
                account_id=account,
                generation=generation,
                character_id=char["id"],
                fight_id=fight.id,
                context=context,
                kamas_roll_index=0,
            ).policy

        def actual_loot_resolver(db, reward, *, fail_after_delivery=False):
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
            batch = resolve_drops(
                store,
                db,
                account_id=account,
                generation=generation,
                character_id=char["id"],
                fight_id=fight.id,
                monsters=[{"actor_id": npc.id, "reference": monster["ref"]}],
                prospecting_bonus=player.effect_stats[33],
                can_loot=True,
                fight_context={"in_infinite_waves": False},
                rng=rng,
            )
            apply(store, db, batch)
            loots = report_loots(batch)
            _loots(loots)
            if fail_after_delivery:
                # Prove delivery has already written rows in this transaction.
                self.assertGreater(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_drop_delivery_receipts "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight.id, char["id"]),
                    ).fetchone()["n"],
                    0,
                )
                runtime.awaiting_ack = None
                runtime.pending = []
                raise ValueError("Injected failure after real drop delivery")
            saved = store.character(account, char["id"], db)
            return {
                "loots": loots,
                "packets": [
                    synchronization(saved),
                    equipment_inventory(saved),
                    temporary_update(db, char["id"]),
                ],
            }

        def finish(*, fail_after_delivery=False):
            return prepare_finish(
                store,
                account,
                generation,
                character,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=fight.id,
                policy_resolver=policy_resolver,
                loot_resolver=lambda db, reward: actual_loot_resolver(
                    db, reward, fail_after_delivery=fail_after_delivery
                ),
            )

        with self.assertRaisesRegex(ValueError, "after real drop delivery"):
            finish(fail_after_delivery=True)
        self.assertEqual((runtime.awaiting_ack, runtime.pending), (23, pending))
        after_failure = store.character(account, char["id"])
        for key in ("xp", "kamas", "level", "hp", "max_hp"):
            self.assertEqual(after_failure[key], character[key], key)
        with store.connection() as db:
            for table in (
                "fight_rewards",
                "fight_reward_policy_receipts",
                "fight_drop_awards",
                "fight_drop_attempt_receipts",
                "fight_drop_delivery_receipts",
                "temporary_combat_items",
            ):
                self.assertEqual(
                    db.execute(
                        f"SELECT count(*) AS n FROM {table} WHERE "
                        + (
                            "fight_id=%s AND character_id=%s"
                            if table != "fight_rewards"
                            else "fight_id=%s AND character_id=%s"
                        ),
                        (fight.id, char["id"]),
                    ).fetchone()["n"],
                    0,
                    table,
                )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT uid,quantity FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (char["id"],),
                ).fetchall(),
                starting_items,
            )

        result = finish()
        self.assertTrue(result["reward"]["awarded"])
        self.assertGreater(result["reward"]["xp"], 0)
        self.assertGreater(result["reward"]["kamas"], 0)
        self.assertEqual(
            [packet[0] for packet in result["packets"][-3:]],
            [13713, 13078, 12691],
        )
        self.assertTrue(any(packet[0] == 12755 for packet in result["packets"]))
        self.assertTrue(result["metadata"][char["id"]]["loots"])
        with store.connection() as db:
            receipts = db.execute(
                "SELECT awarded_quantity,inventory_quantity,temporary_quantity "
                "FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
                (fight.id, char["id"]),
            ).fetchall()
            self.assertTrue(receipts)
            self.assertGreater(sum(row["inventory_quantity"] for row in receipts), 0)
            self.assertGreater(sum(row["temporary_quantity"] for row in receipts), 0)
            self.assertEqual(
                sum(row["awarded_quantity"] for row in receipts),
                sum(
                    row["inventory_quantity"] + row["temporary_quantity"]
                    for row in receipts
                ),
            )
            saved = store.character(account, char["id"], db)
            self.assertEqual(saved["xp"], result["reward"]["character"]["xp"])
            self.assertEqual(saved["kamas"], result["reward"]["character"]["kamas"])
            before_retry = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s ORDER BY uid",
                (char["id"],),
            ).fetchall()

        replay = finish()
        self.assertFalse(replay["reward"]["awarded"])
        self.assertEqual(replay["reward"]["xp"], result["reward"]["xp"])
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT uid,quantity FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (char["id"],),
                ).fetchall(),
                before_retry,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                    (fight.id, char["id"]),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
                    (fight.id, char["id"]),
                ).fetchone()["n"],
                len(receipts),
            )

    def test_finish_encoder_failure_rolls_back_reward_and_runtime_cleanup(self):
        from unittest.mock import patch
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = test_combat_rewards.setup_reward_state(self.store)
            with store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
                )
            before = store.character(account, char["id"])
            runtime = RuntimeMessages(fight)
            runtime.awaiting_ack = 17
            pending = [(123, b"queued")]
            runtime.pending = pending
            metadata = {
                char["id"]: dict(
                    kind="player",
                    account_id=account,
                    name=char["name"],
                    breed=char["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }

            def fail(*args, **kwargs):
                runtime.awaiting_ack = None
                runtime.pending = []
                raise ValueError("Injected finish encoder failure")

            resolutions = []

            def resolve(db):
                self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
                status = db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"]
                self.assertEqual(status, "finished")
                resolutions.append(status)
                return Policy(level_xp(3), 17)

            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                prepare_finish(
                    store,
                    account,
                    generation,
                    char,
                    runtime,
                    metadata,
                    duration_ms=1000,
                    fight_instance_id=8,
                    policy=Policy(1, 1),
                    policy_resolver=resolve,
                )
            self.assertEqual(resolutions, [])

            with patch("wakfu_server.combat_results.finish_messages", side_effect=fail):
                with self.assertRaises(ValueError):
                    prepare_finish(
                        store,
                        account,
                        generation,
                        char,
                        runtime,
                        metadata,
                        duration_ms=1000,
                        fight_instance_id=8,
                        policy_resolver=resolve,
                    )
            after = store.character(account, char["id"])
            for key in ("level", "xp", "hp", "max_hp", "kamas", "builds"):
                self.assertEqual(after[key], before[key])
            self.assertEqual(runtime.awaiting_ack, 17)
            self.assertIs(runtime.pending, pending)
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                    ).fetchone()["status"],
                    "active",
                )
            completed = prepare_finish(
                store,
                account,
                generation,
                char,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=8,
                policy_resolver=resolve,
            )
            self.assertTrue(completed["reward"]["awarded"])
            self.assertEqual(resolutions, ["finished", "finished"])

    def test_policy_is_explicit_zero_default_and_rejects_bad_native_amounts(self):
        self.assertEqual(policy_from_env({}), Policy())
        self.assertEqual(
            policy_from_env(
                {"WAKFU_LOCAL_FIGHT_XP": "103", "WAKFU_LOCAL_FIGHT_KAMAS": "7"}
            ),
            Policy(103, 7),
        )
        for value in ("-1", "1.5", "true", "１２", ""):
            with self.assertRaises(ValueError):
                policy_from_env({"WAKFU_LOCAL_FIGHT_XP": value})
        with self.assertRaises(ValueError):
            policy_from_env({"WAKFU_LOCAL_FIGHT_KAMAS": str(2**31)})

    def test_committed_rewards_report_then_matching_return_refreshes_level_hp_wallet(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = test_combat_rewards.setup_reward_state(self.store)
            char = health_store.initialize(
                store, account, generation, char["id"], coefficient=0
            )
            actor = fight.actors[char["id"]]
            actor.hp = char["hp"] - 7
            actor.max_hp = char["max_hp"]
            from wakfu_server.combat_runtime_messages import RuntimeMessages

            runtime = RuntimeMessages(fight)
            metadata = {
                char["id"]: dict(
                    kind="player",
                    account_id=account,
                    name=char["name"],
                    breed=char["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }
            done = prepare_finish(
                store,
                account,
                generation,
                char,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=8,
                policy=Policy(level_xp(2) + 1, 13),
            )
            self.assertEqual([op for op, b in done["packets"]], [13613, 12238, 12755])
            self.assertEqual(
                done["packets"][0],
                (
                    13613,
                    struct.pack(">BBqqhB", 1, 1, char["id"], level_xp(2) + 1, 1, 0),
                ),
            )
            # The native fight report contains the same committed delta and
            # absolute XP total, plus the exact kama reward from its receipt.
            from wakfu_server.combat_results import fight_report
            from wakfu_server.wire import proto_fields

            report = fight_report(
                fight,
                done["metadata"],
                duration_ms=1000,
                fight_instance_id=8,
                initiator_id=char["id"],
            )
            teams = dict(proto_fields(report))
            own = dict(proto_fields(dict(proto_fields(teams[42]))[18]))
            xp_info = dict(proto_fields(own[66]))
            self.assertEqual(
                (xp_info[8], xp_info[16], xp_info[40], xp_info[48]),
                (level_xp(2) + 1, level_xp(2) + 1, 1, 2),
            )
            self.assertEqual(own[72], 13)
            self.assertEqual(done["character"]["level"], 2)
            with self.assertRaises(ValueError):
                return_to_world(
                    store,
                    account,
                    generation,
                    char,
                    runtime,
                    struct.pack(">iB", 999, 0),
                    wp=6,
                )
            result = return_to_world(
                store,
                account,
                generation,
                done["character"],
                runtime,
                struct.pack(">iB", fight.id, 0),
                wp=6,
            )
            own = result["character"]
            self.assertEqual(own["max_hp"], health.maximum(own["breed"], 2))
            self.assertEqual(
                own["hp"], own["max_hp"] - (actor.max_hp - actor.hp)
            )  # Level-up preserves the actor's wound count as the maximum grows.
            envelope = result["packets"][2][1]
            self.assertEqual(
                struct.unpack_from(">h", envelope, 8)[0], len(envelope) - 10
            )
            progression = envelope[:8] + envelope[10:]
            self.assertEqual(
                struct.unpack_from(">q", progression, 9)[0], level_xp(2) + 1
            )
            self.assertEqual(struct.unpack_from(">i", progression, 8 + 29)[0], -1)
            self.assertEqual(result["packets"][-2], (13021, struct.pack(">q", 13)))
            from wakfu_server.wire import account_kamas

            self.assertEqual(result["packets"][-1], (13873, account_kamas(13)))
            self.assertEqual(
                store.character(account, char["id"])["haven_bag"], char["haven_bag"]
            )

    def test_losing_controlled_participant_gets_no_xp_or_kamas(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        (
            store,
            account,
            char,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        fight.winner = 1
        runtime = RuntimeMessages(fight)
        metadata = {
            char["id"]: dict(
                kind="player",
                account_id=account,
                name=char["name"],
                breed=char["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }

        def unexpected_resolver(_db):
            raise AssertionError("A losing participant must not resolve a reward")

        def unexpected_loot(_db, _reward):
            raise AssertionError("A losing participant must not resolve loot")

        result = prepare_finish(
            store,
            account,
            generation,
            char,
            runtime,
            metadata,
            duration_ms=1000,
            fight_instance_id=8,
            policy_resolver=unexpected_resolver,
            loot_resolver=unexpected_loot,
        )
        self.assertIsNone(result["reward"])
        self.assertNotIn(13613, [opcode for opcode, _ in result["packets"]])
        self.assertNotIn(13052, [opcode for opcode, _ in result["packets"]])
        self.assertEqual(result["character"]["xp"], level_xp(1))
        self.assertEqual(result["character"]["kamas"], 0)
        with store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS count FROM fight_rewards").fetchone()[
                    "count"
                ],
                0,
            )

    def test_group_removal_ecology_shares_reward_transaction_and_return_does_not_repeat_it(
        self,
    ):
        from psycopg.errors import RaiseException
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.monster_removal_ecology import finish as settle_removal
        from wakfu_server.monsters import owned_instance

        (
            store,
            account,
            char,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        groups = PersistentGroups(store, clock=lambda: 1000)
        key = groups.register(
            1134,
            0,
            761,
            [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)],
        )
        lease, _ = groups.claim(key, generation, fight.id)
        runtime = RuntimeMessages(fight)
        runtime.awaiting_ack = 1
        runtime.pending = [(123, b"pending")]
        metadata = {
            char["id"]: dict(
                kind="player",
                account_id=account,
                name=char["name"],
                breed=char["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        args = (store, account, generation, char, runtime, metadata)
        kwargs = dict(
            duration_ms=1000,
            fight_instance_id=8,
            policy=Policy(level_xp(2), 7),
            groups=groups,
            group_lease=lease,
            group_settlement=lambda db, current_lease, defeated: settle_removal(
                store,
                groups,
                current_lease,
                character_id=char["id"],
                defeated=defeated,
                locate=lambda *_: {"region_id": 79001},
                db=db,
            ),
        )

        with store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_integrated_removal() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'integrated removal rejected'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_integrated_removal BEFORE INSERT ON personal_ecology_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_integrated_removal()"
            )
        with self.assertRaisesRegex(RaiseException, "integrated removal rejected"):
            prepare_finish(*args, **kwargs)
        self.assertEqual(
            "fighting",
            next(
                row["status"] for row in groups.snapshot(*key[:2]) if row["key"] == key
            ),
        )
        self.assertEqual(
            (1, [(123, b"pending")]), (runtime.awaiting_ack, runtime.pending)
        )
        with store.connection() as db:
            self.assertEqual(
                0, db.execute("SELECT count(*) FROM fight_rewards").fetchone()["count"]
            )
            self.assertEqual(
                0,
                db.execute("SELECT count(*) FROM personal_ecology_receipts").fetchone()[
                    "count"
                ],
            )
        with store.connection() as db:
            db.execute(
                "DROP TRIGGER reject_integrated_removal ON personal_ecology_receipts"
            )

        finished = prepare_finish(*args, **kwargs)
        self.assertTrue(finished["reward"]["awarded"])
        self.assertTrue(finished["ecology"]["applied"])
        self.assertEqual(1, len(finished["ecology"]["receipts"]))
        self.assertEqual(
            [13574, 349], [opcode for opcode, _ in finished["ecology"]["packets"]]
        )
        self.assertEqual(
            "defeated",
            next(
                row["status"] for row in groups.snapshot(*key[:2]) if row["key"] == key
            ),
        )
        with store.connection() as db:
            self.assertEqual(
                (1, 1),
                (
                    db.execute("SELECT count(*) FROM fight_rewards").fetchone()[
                        "count"
                    ],
                    db.execute(
                        "SELECT count(*) FROM personal_ecology_receipts"
                    ).fetchone()["count"],
                ),
            )

        returned = return_to_world(
            store,
            account,
            generation,
            finished["character"],
            runtime,
            struct.pack(">iB", fight.id, 0),
            wp=6,
        )
        self.assertTrue(returned["applied"])
        with store.connection() as db:
            self.assertEqual(
                1,
                db.execute("SELECT count(*) FROM personal_ecology_receipts").fetchone()[
                    "count"
                ],
            )
            self.assertEqual(
                1, db.execute("SELECT count(*) FROM fight_rewards").fetchone()["count"]
            )
