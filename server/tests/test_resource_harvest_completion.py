from concurrent.futures import ThreadPoolExecutor
import ast
from threading import Barrier
import struct
import unittest
from pathlib import Path

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.profession_store import ensure_learned
from wakfu_server.resource_collect import (
    acknowledge_publication,
    cancel,
    complete,
    pending,
    prepare,
    reserve,
)
from wakfu_server.combat_groups import Groups
from wakfu_server.planting_runtime import Plantings
from wakfu_server.planting import RESOURCES
from wakfu_server.planting_cells import surface
from wakfu_server.ecology_population import snapshot as ecology_population
from wakfu_server.ecology_progression import native_score
from wakfu_server.wire import proto_field


def request(action_id, x, y):
    def unsigned(value):
        return value if value >= 0 else value + (1 << 64)

    return (
        proto_field(8, action_id)
        + proto_field(16, unsigned(x))
        + proto_field(24, unsigned(y))
    )


def result_packet(result=2):
    return struct.pack(">Bh", result, 3)


class ResourceHarvestCompletionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1000.0]
        self.store.clock = lambda: self.clock[0]
        self.account = self.store.register("harvest-complete", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Harvest Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [72]
        )
        self.resource = self.plant(9001, stage=3)

    def plant(self, uid, *, stage, reference=60):
        resource = dict(
            resource_uid=uid,
            map_id=self.character["map_id"],
            instance_id=self.character["instance_id"],
            x=self.character["x"],
            y=self.character["y"],
            z=self.character["z"],
            resource_reference=reference,
            stage=stage,
            creation_time=777,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        return resource

    def set_resource_definition(self, *, stage, reference):
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET stage=%s,resource_reference=%s WHERE resource_uid=%s",
                (stage, reference, self.resource["resource_uid"]),
            )
        self.resource["stage"] = stage
        self.resource["resource_reference"] = reference

    def ticket(self, action_id=100):
        prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            request(action_id, self.resource["x"], self.resource["y"]),
            reachable=lambda _actor, _resource: True,
        )
        return reserve(self.store, self.account, self.generation, prepared)

    def advance(self, seconds=3.0):
        self.clock[0] += seconds

    def assert_ecology_outcome(self, outcome, expected_fields):
        self.assertEqual(
            {key: outcome["outcome"][key] for key in expected_fields},
            expected_fields,
        )
        metadata = outcome["outcome"]["ecology"]
        # A known native map/region always records an ecology receipt and the
        # absolute gauge packet, including neutral (zero-delta) harvests.
        self.assertEqual("applied", metadata["reason"])
        packets = [body for opcode, body in outcome["packets"] if opcode == 13574]
        self.assertEqual(1, len(packets))
        receipt = metadata["receipt"]
        evidence = receipt["evidence"]
        self.assertEqual(self.character["id"], struct.unpack(">qi", packets[0])[0])
        resource = outcome["event"]
        native = surface(
            resource["map_id"], resource["x"], resource["y"], resource["z"]
        )
        self.assertEqual(
            (resource["map_id"], native["region_id"]),
            (evidence["map_id"], evidence["region_id"]),
        )
        family = RESOURCES[resource["resource_reference"]]["family_id"]
        self.assertEqual(family, evidence["family_id"])
        with self.store.connection() as db:
            population = ecology_population(
                db,
                resource["map_id"],
                resource["instance_id"],
                kinds=("plant",),
                locate=surface,
            )
            after = (
                population["regions"]
                .get(native["region_id"], {})
                .get("plant", {})
                .get(family, 0)
            )
            limit = db.execute(
                "SELECT minimum,maximum,source,revision FROM ecology_family_limits "
                "WHERE map_id=%s AND region_id=%s AND kind='plant' AND family_id=%s",
                (resource["map_id"], native["region_id"], family),
            ).fetchone()
        self.assertEqual(after, evidence["after_population"])
        self.assertEqual(
            evidence["before_population"] - evidence["after_population"],
            1 if evidence["action"] == "remove" else 0,
        )
        if limit is None:
            self.assertEqual("local_fallback", evidence["limit_source"])
            self.assertIsNone(evidence["limit_revision"])
        else:
            self.assertEqual(
                (
                    limit["minimum"],
                    limit["maximum"],
                    limit["source"],
                    limit["revision"],
                ),
                (
                    evidence["minimum"],
                    evidence["maximum"],
                    evidence["limit_source"],
                    evidence["limit_revision"],
                ),
            )
        policy = evidence["policy"]
        if evidence["distance_after"] < evidence["distance_before"]:
            expected_delta = policy["balance_delta"]
        elif evidence["distance_after"] > evidence["distance_before"]:
            expected_delta = policy["imbalance_delta"]
        else:
            expected_delta = 0
        self.assertEqual(expected_delta, receipt["requested_delta"])
        self.assertEqual(
            native_score(receipt["after_value"]), struct.unpack(">qi", packets[0])[1]
        )
        self.assertEqual(
            receipt["after_value"],
            max(-10000, min(10000, receipt["before_value"] + expected_delta)),
        )

    def row(self, table, key, value):
        with self.store.connection() as db:
            return db.execute(
                f"SELECT * FROM {table} WHERE {key}=%s", (value,)
            ).fetchone()

    def xp(self, profession_id=72):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=%s",
                (self.account, profession_id),
            ).fetchone()
        return row["xp"]

    def learn(self, profession_id):
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            [profession_id],
        )

    def test_fresno_stage2_action310_yields_sapling_then_grows_after_30s(self):
        self.learn(71)
        self.set_resource_definition(stage=2, reference=139)
        ticket = self.ticket(310)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        self.assert_ecology_outcome(
            outcome,
            {"stage": 1, "item_reference": 8063, "quantity": 1, "xp": 50},
        )
        self.assertEqual(
            struct.unpack(
                ">iq",
                next(body for opcode, body in outcome["packets"] if opcode == 12916),
            ),
            (71, 50),
        )
        self.assertEqual(self.xp(71), 50)
        item = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ][0]
        self.assertEqual((item["reference"], item["quantity"]), (8063, 1))
        self.assertEqual(
            self.row("planted_resources", "resource_uid", ticket["resource_uid"])[
                "stage"
            ],
            1,
        )

        self.clock[0] += 30
        delivered = []
        Plantings(self.store, growth_seconds=30).mature(
            Groups(), publish=delivered.append
        )
        self.assertEqual(len(delivered), 1)
        self.assertEqual(struct.unpack(">iihhqi", delivered[0]["packets"][0][1])[3], 2)
        saved = self.row("planted_resources", "resource_uid", ticket["resource_uid"])
        self.assertEqual(saved["stage"], 2)
        growth = self.row(
            "planting_growth_outbox", "resource_uid", ticket["resource_uid"]
        )
        self.assertEqual(growth["resource"]["stage"], 2)
        self.assertTrue(growth["published"])
        self.assertEqual(self.xp(71), 50)
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["quantity"],
            1,
        )

    def test_fresno_stage3_action99_yields_wood_and_removes_tree(self):
        self.learn(71)
        self.set_resource_definition(stage=3, reference=139)
        ticket = self.ticket(99)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        self.assert_ecology_outcome(
            outcome,
            {"stage": 0, "item_reference": 1723, "quantity": 1, "xp": 50},
        )
        self.assertEqual(
            struct.unpack(
                ">iq",
                next(body for opcode, body in outcome["packets"] if opcode == 12916),
            ),
            (71, 50),
        )
        item = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ][0]
        self.assertEqual((item["reference"], item["quantity"]), (1723, 1))
        self.assertIsNone(
            self.row("planted_resources", "resource_uid", ticket["resource_uid"])
        )
        self.assertEqual(self.xp(71), 50)

    def test_fresno_stage3_action538_yields_sapling_and_returns_to_stage2(self):
        self.learn(71)
        self.set_resource_definition(stage=3, reference=139)
        ticket = self.ticket(538)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        self.assert_ecology_outcome(
            outcome,
            {"stage": 2, "item_reference": 8063, "quantity": 1, "xp": 50},
        )
        self.assertEqual(
            struct.unpack(
                ">iq",
                next(body for opcode, body in outcome["packets"] if opcode == 12916),
            ),
            (71, 50),
        )
        item = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ][0]
        self.assertEqual((item["reference"], item["quantity"]), (8063, 1))
        self.assertEqual(
            self.row("planted_resources", "resource_uid", ticket["resource_uid"])[
                "stage"
            ],
            2,
        )
        self.assertEqual(self.xp(71), 50)

    def test_cardo_action100_transitions_to_stage2_grants_seed_and_50_xp_once(self):
        ticket = self.ticket(100)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        self.assertTrue(outcome["applied"])
        self.assert_ecology_outcome(
            outcome,
            {"stage": 2, "item_reference": 4275, "quantity": 1, "xp": 50},
        )
        self.assertEqual(
            len([1 for opcode, _ in outcome["packets"] if opcode == 12916]), 1
        )
        self.assertEqual(
            struct.unpack(
                ">iq",
                next(body for opcode, body in outcome["packets"] if opcode == 12916),
            ),
            (72, 50),
        )
        self.assertEqual(outcome["world_packets"][0][0], 12782)
        resource = self.row("planted_resources", "resource_uid", ticket["resource_uid"])
        self.assertEqual(resource["stage"], 2)
        self.assertEqual(resource["creation_time"], 1_003_000)
        item = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ][0]
        self.assertEqual((item["reference"], item["quantity"]), (4275, 1))
        replay = complete(self.store, ticket, result_packet())
        self.assertEqual(replay, {"applied": False, "packets": [], "world_packets": []})
        self.assertEqual(self.xp(), 50)
        self.assertEqual(
            self.row("resource_harvest_receipts", "token", ticket["token"])["result"][
                "xp"
            ],
            50,
        )

    def test_stage2_transition_supersedes_stale_growth_event(self):
        ticket = self.ticket(100)
        stale = dict(self.resource, creation_time=776, stage=1)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload,published) "
                "VALUES(%s,%s,NULL,FALSE)",
                (ticket["resource_uid"], Jsonb(stale)),
            )
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        event = self.row(
            "planting_growth_outbox", "resource_uid", ticket["resource_uid"]
        )
        self.assertEqual(event["resource"], outcome["event"])
        self.assertEqual(event["resource"]["stage"], 2)
        self.assertFalse(event["published"])

    def test_stage0_transition_replaces_stale_outbox_event(self):
        ticket = self.ticket(203)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload,published) "
                "VALUES(%s,%s,NULL,TRUE)",
                (ticket["resource_uid"], Jsonb(dict(self.resource, stage=2))),
            )
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        event = self.row(
            "planting_growth_outbox", "resource_uid", ticket["resource_uid"]
        )
        self.assertEqual(event["resource"], outcome["event"])
        self.assertEqual(event["resource"]["stage"], 0)
        self.assertFalse(event["published"])

    def test_acknowledgement_of_old_event_does_not_mark_replacement_published(self):
        ticket = self.ticket(100)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        newer = dict(
            outcome["event"],
            stage=4,
            creation_time=outcome["event"]["creation_time"] + 1,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE planting_growth_outbox SET resource=%s,published=FALSE WHERE resource_uid=%s",
                (Jsonb(newer), ticket["resource_uid"]),
            )
        acknowledge_publication(self.store, outcome)
        saved = self.row(
            "planting_growth_outbox", "resource_uid", ticket["resource_uid"]
        )
        self.assertEqual(saved["resource"], newer)
        self.assertFalse(saved["published"])

    def test_publish_failure_retries_exact_harvest_event_without_second_rewards(self):
        ticket = self.ticket(100)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        attempted = []

        def fail(delivery):
            attempted.append(delivery)
            raise OSError("world peer disconnected")

        runtime = Plantings(self.store)
        with self.assertRaisesRegex(OSError, "peer disconnected"):
            runtime.publish_growth(Groups(), publish=fail)
        event_row = self.row(
            "planting_growth_outbox", "resource_uid", ticket["resource_uid"]
        )
        self.assertFalse(event_row["published"])
        self.assertEqual(event_row["resource"], outcome["event"])
        retried = []
        published = runtime.publish_growth(Groups(), publish=retried.append)
        self.assertEqual(attempted, retried)
        self.assertEqual(published, retried)
        self.assertEqual(retried[0]["packets"][0], outcome["world_packets"][0])
        self.assertTrue(
            self.row("planting_growth_outbox", "resource_uid", ticket["resource_uid"])[
                "published"
            ]
        )
        self.assertEqual(self.xp(), 50)
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["quantity"],
            1,
        )
        self.assertEqual(
            self.row("resource_harvest_receipts", "token", ticket["token"])["result"][
                "xp"
            ],
            50,
        )

    def test_stage1_growth_replaces_its_event_with_new_stage2_event(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET stage=1,creation_time=1 WHERE resource_uid=%s",
                (self.resource["resource_uid"],),
            )
            stale = dict(self.resource, stage=1, creation_time=1)
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload,published) "
                "VALUES(%s,%s,NULL,FALSE)",
                (self.resource["resource_uid"], Jsonb(stale)),
            )
        self.clock[0] += 5
        delivered = []
        runtime = Plantings(self.store, growth_seconds=1)
        runtime.mature(Groups(), publish=delivered.append)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(struct.unpack(">iihhqi", delivered[0]["packets"][0][1])[3], 2)
        row = self.row(
            "planting_growth_outbox", "resource_uid", self.resource["resource_uid"]
        )
        self.assertEqual(row["resource"]["stage"], 2)
        self.assertTrue(row["published"])

    def test_growth_publisher_acknowledges_only_snapshot_it_sent(self):
        ticket = self.ticket(100)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        runtime = Plantings(self.store)
        new_event = dict(
            outcome["event"],
            stage=3,
            creation_time=outcome["event"]["creation_time"] + 1,
        )
        sent = []

        def replace_during_send(delivery):
            sent.append(delivery)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE planting_growth_outbox SET resource=%s,published=FALSE WHERE resource_uid=%s",
                    (Jsonb(new_event), ticket["resource_uid"]),
                )

        runtime.publish_growth(Groups(), publish=replace_during_send)
        self.assertFalse(
            self.row("planting_growth_outbox", "resource_uid", ticket["resource_uid"])[
                "published"
            ]
        )
        retried = []
        runtime.publish_growth(Groups(), publish=retried.append)
        self.assertEqual(struct.unpack(">iihhqi", sent[0]["packets"][0][1])[3], 2)
        self.assertEqual(struct.unpack(">iihhqi", retried[0]["packets"][0][1])[3], 3)
        self.assertTrue(
            self.row("planting_growth_outbox", "resource_uid", ticket["resource_uid"])[
                "published"
            ]
        )

    def test_dispatcher_routes_flora_protocol_before_combat_monster_harvest(self):
        source = (
            Path(__file__).resolve().parents[1] / "local_game_server.py"
        ).read_text()
        tree = ast.parse(source)

        def opcode_nodes(target):
            result = []
            for node in ast.walk(tree):
                if not isinstance(node, ast.If):
                    continue
                comparisons = [
                    child
                    for child in ast.walk(node.test)
                    if isinstance(child, ast.Compare)
                ]
                if any(
                    isinstance(comp.left, ast.Name)
                    and comp.left.id == "opcode"
                    and comp.ops
                    and isinstance(comp.ops[0], ast.Eq)
                    and comp.comparators
                    and isinstance(comp.comparators[0], ast.Constant)
                    and comp.comparators[0].value == target
                    for comp in comparisons
                ):
                    result.append(node)
            return result

        collect = opcode_nodes(12995)
        completions = opcode_nodes(13429)
        self.assertEqual(len(collect), 1)
        flora_completion = next(
            node
            for node in completions
            if "Bh" in ast.unparse(node.test) and "[1] == 3" in ast.unparse(node.test)
        )
        combat_completion = next(
            node for node in completions if "COMBAT_TEST" in ast.unparse(node.test)
        )
        self.assertLess(collect[0].lineno, flora_completion.lineno)
        self.assertLess(flora_completion.lineno, combat_completion.lineno)
        flora_text = ast.unparse(flora_completion)
        self.assertIn("fight is not None or bag_session is not None", flora_text)
        self.assertIn("PLANTINGS.publisher_lock", flora_text)
        self.assertIn("acknowledge_publication", flora_text)
        movement_cancellation = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "flora_ticket is not None" in ast.unparse(node.test)
            and "13331" in ast.unparse(node.test)
        )
        self.assertIn("cancel_flora()", ast.unparse(movement_cancellation))
        self.assertIn('logout_barrier("flora_occupation", cancel_flora)', source)

    def test_cardo_action203_removes_resource_and_grants_product(self):
        ticket = self.ticket(203)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        self.assert_ecology_outcome(
            outcome,
            {"stage": 0, "item_reference": 2504, "quantity": 1, "xp": 50},
        )
        self.assertIsNone(
            self.row("planted_resources", "resource_uid", ticket["resource_uid"])
        )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["reference"],
            2504,
        )
        self.assertEqual(self.xp(), 50)

    def test_stage1_uproot_has_no_product_or_xp_and_removes_resource(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET stage=1 WHERE resource_uid=%s",
                (self.resource["resource_uid"],),
            )
        self.resource["stage"] = 1
        ticket = self.ticket(329)
        self.advance()
        outcome = complete(self.store, ticket, result_packet())
        self.assert_ecology_outcome(
            outcome,
            {"stage": 0, "item_reference": 0, "quantity": 0, "xp": 0},
        )
        self.assertEqual([opcode for opcode, _ in outcome["packets"]], [13574, 349])
        self.assertIsNone(
            self.row("planted_resources", "resource_uid", ticket["resource_uid"])
        )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"],
            [],
        )
        self.assertEqual(self.xp(), 0)

    def test_cancel_keeps_resource_and_grants_nothing(self):
        ticket = self.ticket()
        outcome = complete(self.store, ticket, result_packet(3))
        self.assertEqual(
            outcome, {"applied": False, "packets": [], "world_packets": []}
        )
        self.assertIsNotNone(
            self.row("planted_resources", "resource_uid", ticket["resource_uid"])
        )
        self.assertIsNone(
            self.row("resource_harvest_occupations", "token", ticket["token"])
        )
        self.assertIsNone(
            self.row("resource_harvest_receipts", "token", ticket["token"])
        )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"],
            [],
        )
        self.assertEqual(self.xp(), 0)

    def test_early_and_expired_completion_reject_without_mutation(self):
        ticket = self.ticket()
        self.advance(2.999)
        with self.assertRaisesRegex(ValueError, "before duration"):
            complete(self.store, ticket, result_packet())
        self.advance(0.001)
        occupation = pending(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.clock[0] = occupation["expires_at"].timestamp()
        with self.assertRaisesRegex(ValueError, "expired"):
            complete(self.store, ticket, result_packet())
        self.assertIsNotNone(
            self.row("resource_harvest_occupations", "token", ticket["token"])
        )
        self.assertEqual(self.xp(), 0)
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"],
            [],
        )

    def test_actor_movement_resource_mutation_and_unlearned_profession_reject(self):
        ticket = self.ticket()
        self.advance()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET z=z+1 WHERE id=%s", (self.character["id"],)
            )
        with self.assertRaisesRegex(ValueError, "actor moved"):
            complete(self.store, ticket, result_packet())
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET z=z-1 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "UPDATE planted_resources SET stage=2 WHERE resource_uid=%s",
                (ticket["resource_uid"],),
            )
        with self.assertRaisesRegex(ValueError, "Resource changed"):
            complete(self.store, ticket, result_packet())
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET stage=3 WHERE resource_uid=%s",
                (ticket["resource_uid"],),
            )
            db.execute(
                "DELETE FROM account_professions WHERE account_id=%s AND profession_id=72",
                (self.account,),
            )
        with self.assertRaisesRegex(ValueError, "profession is unlearned"):
            complete(self.store, ticket, result_packet())
        self.assertIsNotNone(
            self.row("resource_harvest_occupations", "token", ticket["token"])
        )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"],
            [],
        )
        self.assertIsNone(
            self.row("resource_harvest_receipts", "token", ticket["token"])
        )

    def test_foreign_ticket_account_character_and_action_fail_closed(self):
        ticket = self.ticket()
        for field, value in (
            ("account_id", self.account + 1),
            ("character_id", self.character["id"] + 1),
            ("action_id", 203),
        ):
            forged = dict(ticket, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                complete(self.store, forged, result_packet())
        self.assertIsNotNone(
            self.row("resource_harvest_occupations", "token", ticket["token"])
        )

    def test_full_inventory_rolls_back_resource_receipt_xp_and_occupation(self):
        ticket = self.ticket()
        with self.store.connection() as db:
            container = self.character["inventory_containers"][0]
            for slot in range(container["capacity"]):
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                    "VALUES(%s,%s,%s,1,%s,%s)",
                    (
                        8_000_000 + slot,
                        self.character["id"],
                        4_000_000 + slot,
                        container["uid"],
                        slot,
                    ),
                )
        self.advance()
        with self.assertRaisesRegex(ValueError, "inventory full"):
            complete(self.store, ticket, result_packet())
        self.assertEqual(
            self.row("planted_resources", "resource_uid", ticket["resource_uid"])[
                "stage"
            ],
            3,
        )
        self.assertIsNotNone(
            self.row("resource_harvest_occupations", "token", ticket["token"])
        )
        self.assertIsNone(
            self.row("resource_harvest_receipts", "token", ticket["token"])
        )
        self.assertEqual(self.xp(), 0)

    def test_reward_policy_is_strict_multiplier_applies_and_catalog_stage_is_bounded(
        self,
    ):
        ticket = self.ticket()
        self.advance()
        malformed = (
            {"version": True, "product_quantity": 1, "stage_policy": "catalog_cvF"},
            {"version": 1, "product_quantity": 0, "stage_policy": "catalog_cvF"},
            {"version": 1, "product_quantity": 1, "stage_policy": "other"},
            {
                "version": 1,
                "product_quantity": 1,
                "stage_policy": "catalog_cvF",
                "extra": 1,
            },
        )
        for policy in malformed:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='resource_harvest_rewards'",
                    (Jsonb(policy),),
                )
            with self.subTest(policy=policy), self.assertRaisesRegex(
                ValueError, "reward policy"
            ):
                complete(self.store, ticket, result_packet())
            with self.store.connection() as db:
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='resource_harvest_rewards'",
                    (
                        Jsonb(
                            {
                                "version": 1,
                                "product_quantity": 1,
                                "stage_policy": "catalog_cvF",
                            }
                        ),
                    ),
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_xp'",
                (Jsonb({"multiplier_basis_points": 20000}),),
            )
        outcome = complete(self.store, ticket, result_packet())
        self.assertEqual(outcome["outcome"]["xp"], 100)
        reward_packets = [
            body for opcode, body in outcome["packets"] if opcode == 12916
        ]
        self.assertEqual(len(reward_packets), 1)
        self.assertEqual(struct.unpack(">iq", reward_packets[0]), (72, 100))

    def test_unsupported_catalog_destination_stage_rolls_back(self):
        from wakfu_server.planting import RESOURCES

        ticket = self.ticket()
        row = next(
            action
            for stage in RESOURCES[60]["stage_definitions"]
            for action in stage["actions"]
            if action["action_id"] == 100
        )
        prior = row["raw_getters"]["cvF"]
        row["raw_getters"]["cvF"] = 5
        try:
            self.advance()
            with self.assertRaisesRegex(ValueError, "destination stage"):
                complete(self.store, ticket, result_packet())
        finally:
            row["raw_getters"]["cvF"] = prior
        self.assertIsNotNone(
            self.row("resource_harvest_occupations", "token", ticket["token"])
        )
        self.assertEqual(self.xp(), 0)

    def test_same_ticket_race_applies_product_and_xp_once(self):
        ticket = self.ticket()
        self.advance()
        barrier = Barrier(2)

        def worker():
            barrier.wait()
            return complete(self.store, ticket, result_packet())

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _index: worker(), range(2)))
        self.assertEqual(sum(outcome["applied"] for outcome in outcomes), 1)
        self.assertEqual(sum(bool(outcome["packets"]) for outcome in outcomes), 1)
        self.assertEqual(self.xp(), 50)
        self.assertEqual(
            self.row("resource_harvest_receipts", "token", ticket["token"])["result"][
                "xp"
            ],
            50,
        )
        self.assertIsNone(
            self.row("resource_harvest_occupations", "token", ticket["token"])
        )

    def test_pending_durable_ticket_survives_store_reopen(self):
        ticket = self.ticket()
        reopened = self.reopen()
        reopened.clock = self.store.clock
        saved = pending(reopened, self.account, self.generation, self.character["id"])
        self.assertEqual(saved["token"], ticket["token"])
        self.assertEqual(saved["resource_uid"], ticket["resource_uid"])
        self.assertEqual(saved["action_id"], 100)
        self.assertEqual(saved["actor_map_id"], self.character["map_id"])
        self.assertEqual(saved["actor_instance_id"], self.character["instance_id"])
        self.assertEqual(saved["actor_x"], self.character["x"])
        self.assertEqual(saved["actor_y"], self.character["y"])
        self.assertEqual(saved["actor_z"], self.character["z"])
        self.assertEqual(saved["resource_snapshot"], self.resource)
        self.assertTrue(cancel(reopened, ticket))
        self.assertIsNone(
            pending(reopened, self.account, self.generation, self.character["id"])
        )


if __name__ == "__main__":
    unittest.main()
