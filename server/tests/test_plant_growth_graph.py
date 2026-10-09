from contextlib import contextmanager
import struct
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import unittest

from psycopg.errors import CheckViolation
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.combat_groups import Groups
from wakfu_server.planting import RESOURCES, SEEDS
from wakfu_server.planting_runtime import Plantings, state_packet
from wakfu_server.profession_store import ensure_learned
from wakfu_server.resource_collect import complete, prepare, reserve
from wakfu_server.wire import proto_field
from wakfu_server import native_catalog


def harvest_request(action_id, x, y):
    def unsigned(value):
        return value if value >= 0 else value + (1 << 64)

    return (
        proto_field(8, action_id)
        + proto_field(16, unsigned(x))
        + proto_field(24, unsigned(y))
    )


def collect_result():
    return struct.pack(">Bh", 2, 3)


class PlantGrowthGraphTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1000.0]
        self.store.clock = lambda: self.clock[0]
        self.groups = Groups()
        self.deliveries = []
        self.runtime = Plantings(self.store)

    def add_resource(
        self, uid, reference=60, stage=1, *, creation_time=None, x=None, y=None
    ):
        resource = dict(
            resource_uid=uid,
            map_id=1134,
            instance_id=0,
            x=uid if x is None else x,
            y=uid + 1 if y is None else y,
            z=0,
            resource_reference=reference,
            stage=stage,
            creation_time=int(self.clock[0] * 1000)
            if creation_time is None
            else creation_time,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        return resource

    def resource_row(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planted_resources WHERE resource_uid=%s", (uid,)
            ).fetchone()

    def outbox_row(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planting_growth_outbox WHERE resource_uid=%s", (uid,)
            ).fetchone()

    def set_growth_probability(self, reference, from_stage, probability):
        with self.store.connection() as db:
            db.execute(
                "UPDATE resource_growth_transitions SET probability=%s "
                "WHERE resource_reference=%s AND from_stage=%s",
                (probability, reference, from_stage),
            )

    @staticmethod
    def optional_variant_references():
        project_root = Path(__file__).resolve().parents[1]
        path = project_root / "protocol" / "flora-variant-classification.json"
        if not path.is_file():
            path = Path("/app/protocol/flora-variant-classification.json")
        return {
            row["resource_reference"]
            for row in json.loads(native_catalog.read_text(path))["resources"]
            if row["optional_variant_policy"]
        }

    def mature(self, runtime=None, publish=None, random_draw=None):
        options = {}
        if random_draw is not None:
            options["random_draw"] = random_draw
        return (runtime or self.runtime).mature(
            self.groups,
            publish=self.deliveries.append if publish is None else publish,
            **options,
        )

    def test_migration_graph_has_401_valid_local_edges(self):
        optional_variants = self.optional_variant_references()
        with self.store.connection() as db:
            transitions = list(
                db.execute(
                    "SELECT * FROM resource_growth_transitions ORDER BY resource_reference,from_stage"
                )
            )
        self.assertEqual(len(transitions), 401)
        edge_references = {row["resource_reference"] for row in transitions}
        self.assertEqual(len(edge_references), 141)
        for row in transitions:
            definition = RESOURCES.get(row["resource_reference"])
            self.assertIsNotNone(definition)
            self.assertFalse(definition["monster_resource"])
            stages = set(definition["stages"])
            self.assertIn(row["from_stage"], stages)
            self.assertIn(row["to_stage"], stages)
            self.assertNotIn(row["from_stage"], (0, 16))
            self.assertNotIn(row["to_stage"], (0, 16))
            self.assertGreater(row["to_stage"], row["from_stage"])
            ordered = sorted(stage for stage in stages if stage not in (0, 16))
            self.assertIn(
                (row["from_stage"], row["to_stage"]), tuple(zip(ordered, ordered[1:]))
            )
            self.assertEqual(row["delay_ms"], 30000)
            expected_probability = (
                0.01
                if row["resource_reference"] in optional_variants
                and (row["from_stage"], row["to_stage"]) == (3, 4)
                else 1.0
            )
            self.assertEqual(row["probability"], expected_probability)
        stage1_only = {
            seed["resource_reference"]
            for seed in SEEDS.values()
            if seed["resource_reference"] in RESOURCES
            and not RESOURCES[seed["resource_reference"]]["monster_resource"]
            and sorted(
                stage
                for stage in RESOURCES[seed["resource_reference"]]["stages"]
                if stage not in (0, 16)
            )
            == [1]
        }
        self.assertEqual(stage1_only, {309, 331, 466, 495, 861})
        self.assertTrue(stage1_only.isdisjoint(edge_references))
        self.assertEqual(len(edge_references | stage1_only), 146)

    def test_variant_policy_matches_every_native_classified_late_seed_product(self):
        classified = self.optional_variant_references()
        self.assertEqual(88, len(classified))
        self.assertNotIn(825, classified)  # same UNUSUAL primary item
        self.assertNotIn(843, classified)  # mixed normal-stage rarity
        updated_by_033 = classified - {60, 139}
        self.assertEqual(86, len(updated_by_033))

        with self.store.connection() as db:
            actual = {
                row["resource_reference"]: row["probability"]
                for row in db.execute(
                    "SELECT resource_reference,probability FROM resource_growth_transitions "
                    "WHERE from_stage=3 AND to_stage=4"
                )
            }
        for reference in classified:
            with self.subTest(resource_reference=reference):
                self.assertIn(reference, RESOURCES)
                self.assertFalse(RESOURCES[reference]["monster_resource"])
                self.assertIn(3, RESOURCES[reference]["stages"])
                self.assertIn(4, RESOURCES[reference]["stages"])
                self.assertEqual(0.01, actual[reference])
        for reference in (825, 843):
            with self.subTest(excluded_reference=reference):
                if (
                    3 in RESOURCES[reference]["stages"]
                    and 4 in RESOURCES[reference]["stages"]
                ):
                    self.assertEqual(1.0, actual[reference])

    def test_every_seedable_resource_follows_each_filtered_catalog_stage_with_stable_uid(
        self,
    ):
        seedable = sorted(
            {
                seed["resource_reference"]
                for seed in SEEDS.values()
                if seed["resource_reference"] in RESOURCES
                and not RESOURCES[seed["resource_reference"]]["monster_resource"]
            }
        )
        paths = {
            reference: sorted(
                stage
                for stage in RESOURCES[reference]["stages"]
                if stage not in (0, 16)
            )
            for reference in seedable
        }
        self.assertEqual(146, len(seedable))
        self.assertEqual(141, sum(len(stages) > 1 for stages in paths.values()))
        self.assertEqual(5, sum(len(stages) == 1 for stages in paths.values()))
        self.assertTrue(all(stages for stages in paths.values()))

        # This graph-completeness test isolates stage wiring from the local
        # optional Cardo roll; it does not assert that the roll is guaranteed.
        with self.store.connection() as db:
            db.execute("UPDATE resource_growth_transitions SET probability=1")
            transitions = {
                (row["resource_reference"], row["from_stage"]): row
                for row in db.execute(
                    "SELECT * FROM resource_growth_transitions ORDER BY resource_reference,from_stage"
                )
            }
        for reference, stages in paths.items():
            for source, destination in zip(stages, stages[1:]):
                self.assertEqual(
                    destination,
                    transitions[(reference, source)]["to_stage"],
                    (reference, source),
                )
            self.assertTrue(
                all((reference, source) in transitions for source in stages[:-1])
            )

        uid_for_ref = {
            reference: 20_000 + index for index, reference in enumerate(seedable)
        }
        initial_creation_ms = 1_000_000
        for reference in seedable:
            self.add_resource(
                uid_for_ref[reference],
                reference,
                paths[reference][0],
                creation_time=initial_creation_ms,
            )

        max_edges = max(len(stages) - 1 for stages in paths.values())
        for edge_index in range(max_edges):
            self.clock[0] = 1000 + (edge_index + 1) * 30
            expected = {
                uid_for_ref[reference]: stages[edge_index + 1]
                for reference, stages in paths.items()
                if len(stages) > edge_index + 1
            }
            emitted = self.mature()
            self.assertEqual(
                set(expected), {event["resource_uid"] for event in emitted}
            )
            for event in emitted:
                uid = event["resource_uid"]
                reference = next(
                    ref
                    for ref, assigned_uid in uid_for_ref.items()
                    if assigned_uid == uid
                )
                row = self.resource_row(uid)
                self.assertEqual(reference, row["resource_reference"])
                self.assertEqual(expected[uid], row["stage"])
                self.assertEqual(
                    initial_creation_ms + (edge_index + 1) * 30_000,
                    row["creation_time"],
                )
                self.assertEqual(uid, event["resource_uid"])
                opcode, body = event["packets"][0]
                self.assertEqual(12782, opcode)
                x, y, z, packet_stage, owner_account, owner_nation = struct.unpack(
                    ">iihhqi", body
                )
                self.assertEqual(
                    (row["x"], row["y"], row["z"], row["stage"], 0, 0),
                    (x, y, z, packet_stage, owner_account, owner_nation),
                )
                outbox = self.outbox_row(uid)
                self.assertTrue(outbox["published"])
                self.assertEqual(uid, outbox["resource"]["resource_uid"])
                self.assertEqual(row["stage"], outbox["resource"]["stage"])

            for reference, stages in paths.items():
                row = self.resource_row(uid_for_ref[reference])
                expected_current = stages[min(edge_index + 1, len(stages) - 1)]
                self.assertEqual(expected_current, row["stage"])

        self.clock[0] += 30
        self.assertEqual([], self.mature())
        for reference, stages in paths.items():
            row = self.resource_row(uid_for_ref[reference])
            self.assertEqual(stages[-1], row["stage"])

    def test_state_packets_keep_public_owner_zero_for_cardo_and_fresno_all_stages(self):
        public_resource = dict(
            x=-12,
            y=34,
            z=-2,
            creation_time=1_791_072_000_000,
        )
        for reference in (60, 139):
            stages = sorted(set(RESOURCES[reference]["stages"]) | {0})
            for stage in stages:
                with self.subTest(resource_reference=reference, stage=stage):
                    opcode, body = state_packet(public_resource, stage)
                    self.assertEqual(opcode, 12782)
                    self.assertEqual(
                        struct.unpack(">iihhqi", body),
                        (-12, 34, -2, stage, 0, 0),
                    )

    def test_transition_constraints_reject_invalid_stages_and_delays(self):
        invalid = (
            (60, 16, 17, 30000),
            (60, 1, 16, 30000),
            (60, 2, 1, 30000),
            (60, 1, 2, 999),
            (60, 1, 2, 86400001),
        )
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(CheckViolation):
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO resource_growth_transitions(resource_reference,from_stage,to_stage,delay_ms) "
                        "VALUES(%s,%s,%s,%s)",
                        row,
                    )

    def test_growth_decision_constraints_bind_the_draw_to_the_recorded_outcome(self):
        invalid = (
            (
                31_001,
                3,
                4,
                0.01,
                0.02,
                True,
            ),  # outcome disagrees with strict comparison
            (31_002, 3, 3, 0.01, 0.00, True),  # no forward transition
            (31_003, 16, 17, 0.50, 0.00, True),  # non-growing catalog stage
            (31_004, 3, 4, 0.01, 1.00, False),  # draw must be below one
            (31_005, 3, 4, 1.01, 0.00, True),  # probability outside [0,1]
        )
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(CheckViolation):
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO resource_growth_decisions "
                        "(resource_uid,from_stage,to_stage,probability,draw,accepted) "
                        "VALUES(%s,%s,%s,%s,%s,%s)",
                        row,
                    )

    def assert_trajectory(self, reference, uid):
        # Deterministic trajectory coverage explicitly enables every edge in
        # this test fixture, including Cardo's configurable 3->4 edge.
        with self.store.connection() as db:
            db.execute(
                "UPDATE resource_growth_transitions SET probability=1 "
                "WHERE resource_reference=%s",
                (reference,),
            )
        self.add_resource(uid, reference, 1, creation_time=1_000_000)
        for index, stage in enumerate((2, 3, 4), start=1):
            self.clock[0] = 1000 + 30 * index
            result = self.mature()
            self.assertEqual(len(result), 1)
            event = result[0]
            self.assertEqual(event["resource_uid"], uid)
            self.assertEqual(struct.unpack(">iihhqi", event["packets"][0][1])[3], stage)
            row = self.resource_row(uid)
            self.assertEqual(row["stage"], stage)
            self.assertEqual(row["creation_time"], 1_000_000 + index * 30_000)
            outbox = self.outbox_row(uid)
            self.assertEqual(outbox["resource"]["stage"], stage)
            self.assertTrue(outbox["published"])
            self.assertEqual(self.mature(), [])
        self.clock[0] += 30
        self.assertEqual(self.mature(), [])
        self.assertEqual(self.resource_row(uid)["stage"], 4)

    def test_cardo_and_fresno_follow_30_60_90_second_graph_to_terminal_stage(self):
        self.assert_trajectory(60, 9501)
        self.clock[0] = 1000.0
        self.assert_trajectory(139, 9502)

    def actor(self, profession_id):
        account = self.store.register(
            f"growth-actor-{profession_id}", "local-password"
        )["id"]
        name = {71: "Ash Gatherer", 72: "Herb Gatherer"}[profession_id]
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        ensure_learned(
            self.store, account, generation, character["id"], [profession_id]
        )
        return account, character, generation

    def harvest_to_stage2_and_mature(self, *, reference, profession_id, action_id, uid):
        self.set_growth_probability(reference, 3, 1.0)
        account, character, generation = self.actor(profession_id)
        resource = dict(
            resource_uid=uid,
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            x=character["x"] + (uid % 100),
            y=character["y"],
            z=character["z"],
            resource_reference=reference,
            stage=3,
            creation_time=int(self.clock[0] * 1000),
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        prepared = prepare(
            self.store,
            account,
            generation,
            character["id"],
            harvest_request(action_id, resource["x"], resource["y"]),
            reachable=lambda _actor, _resource: True,
        )
        ticket = reserve(self.store, account, generation, prepared)
        self.clock[0] += 3
        outcome = complete(self.store, ticket, collect_result())
        self.assertEqual(outcome["outcome"]["stage"], 2)
        self.assertEqual(outcome["outcome"]["xp"], 50)
        self.clock[0] += 30
        result = self.mature()
        self.assertEqual(len(result), 1)
        self.assertEqual(self.resource_row(uid)["stage"], 3)
        self.clock[0] += 30
        result = self.mature()
        self.assertEqual(len(result), 1)
        self.assertEqual(self.resource_row(uid)["stage"], 4)
        self.clock[0] += 30
        self.assertEqual(self.mature(), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=%s",
                    (account, profession_id),
                ).fetchone()["xp"],
                50,
            )
        self.assertEqual(
            self.store.character(account, character["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )

    def test_harvested_seed_return_for_cardo_and_fresno_regrows_stages3_and4(self):
        self.harvest_to_stage2_and_mature(
            reference=60, profession_id=72, action_id=100, uid=9510
        )
        self.clock[0] = 1000.0
        self.harvest_to_stage2_and_mature(
            reference=139, profession_id=71, action_id=538, uid=9511
        )

    def test_every_catalog_final_stage5_transition_is_supported_and_terminal(self):
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT resource_reference FROM resource_growth_transitions WHERE to_stage=5 ORDER BY resource_reference"
                )
            )
        self.assertGreater(len(rows), 0)
        ids = []
        for index, row in enumerate(rows):
            reference = row["resource_reference"]
            self.assertIn(5, RESOURCES[reference]["stages"])
            uid = 9600 + index
            ids.append(uid)
            self.add_resource(
                uid, reference, 4, creation_time=2_000_000, x=uid, y=uid + 1
            )
        self.clock[0] = 2030.0
        result = self.mature()
        self.assertEqual({delivery["resource_uid"] for delivery in result}, set(ids))
        self.assertTrue(all(self.resource_row(uid)["stage"] == 5 for uid in ids))
        self.clock[0] += 30
        self.assertEqual(self.mature(), [])

    def test_sql_delay_override_controls_real_growth_time(self):
        uid = 9701
        self.add_resource(uid, 60, 1, creation_time=1_000_000)
        with self.store.connection() as db:
            db.execute(
                "UPDATE resource_growth_transitions SET delay_ms=5000 WHERE resource_reference=60 AND from_stage=1"
            )
        self.clock[0] = 1004.999
        self.assertEqual(self.mature(), [])
        self.clock[0] = 1005.0
        result = self.mature()
        self.assertEqual(len(result), 1)
        self.assertEqual(self.resource_row(uid)["stage"], 2)
        self.assertEqual(self.resource_row(uid)["creation_time"], 1_005_000)

    def test_live_harvest_occupation_pauses_due_transition_until_expiry(self):
        account, character, generation = self.actor(72)
        resource = dict(
            resource_uid=9801,
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            x=character["x"],
            y=character["y"],
            z=character["z"],
            resource_reference=60,
            stage=1,
            creation_time=1_000_000,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
            db.execute(
                "UPDATE resource_growth_transitions SET delay_ms=5000 WHERE resource_reference=60 AND from_stage=1"
            )
        prepared = prepare(
            self.store,
            account,
            generation,
            character["id"],
            harvest_request(329, character["x"], character["y"]),
            reachable=lambda _actor, _resource: True,
        )
        ticket = reserve(self.store, account, generation, prepared)
        self.clock[0] = 1005.0
        self.assertEqual(self.mature(), [])
        self.assertEqual(self.resource_row(resource["resource_uid"])["stage"], 1)
        occupation = self.store.connection
        with occupation() as db:
            expires = (
                db.execute(
                    "SELECT expires_at FROM resource_harvest_occupations WHERE token=%s",
                    (ticket["token"],),
                )
                .fetchone()["expires_at"]
                .timestamp()
            )
        self.clock[0] = expires
        result = self.mature()
        self.assertEqual(len(result), 1)
        self.assertEqual(self.resource_row(resource["resource_uid"])["stage"], 2)

    def test_stage_clock_survives_reopen_and_catchup_advances_one_edge_each_call(self):
        uid = 9901
        self.set_growth_probability(60, 3, 1.0)
        self.add_resource(uid, 60, 1, creation_time=1_000_000)
        self.clock[0] = 1090.0
        for expected_stage, entered_at in (
            (2, 1_030_000),
            (3, 1_060_000),
            (4, 1_090_000),
        ):
            delivered = self.mature()
            self.assertEqual(len(delivered), 1)
            saved = self.resource_row(uid)
            self.assertEqual(saved["stage"], expected_stage)
            self.assertEqual(saved["creation_time"], entered_at)
            reopened = self.reopen()
            reopened.clock = self.store.clock
            self.runtime = Plantings(reopened)
        self.assertEqual(self.mature(), [])
        self.assertEqual(self.resource_row(uid)["stage"], 4)

    def test_failed_publish_retries_same_stage_and_no_future_edge_runs_early(self):
        uid = 9902
        self.add_resource(uid, 60, 1, creation_time=1_000_000)
        self.clock[0] = 1030.0
        attempted = []

        def fail(delivery):
            attempted.append(delivery)
            raise OSError("world emit unavailable")

        with self.assertRaisesRegex(OSError, "emit unavailable"):
            self.mature(publish=fail)
        self.assertEqual(self.resource_row(uid)["stage"], 2)
        self.assertFalse(self.outbox_row(uid)["published"])
        retried = self.mature()
        self.assertEqual(attempted, retried)
        self.assertEqual(self.resource_row(uid)["stage"], 2)
        self.assertEqual(self.mature(), [])
        self.clock[0] = 1060.0
        next_edge = self.mature()
        self.assertEqual(len(next_edge), 1)
        self.assertEqual(self.resource_row(uid)["stage"], 3)

    def test_native_invalid_destination_and_stale_policy_recheck_skip_transition(self):
        uid = 9903
        self.add_resource(uid, 60, 1, creation_time=1_000_000)
        with self.store.connection() as db:
            db.execute(
                "UPDATE resource_growth_transitions SET to_stage=127 WHERE resource_reference=60 AND from_stage=1"
            )
        self.clock[0] = 1030.0
        with self.assertRaisesRegex(ValueError, "absent from native"):
            self.mature()
        self.assertEqual(self.resource_row(uid)["stage"], 1)
        self.assertIsNone(self.outbox_row(uid))
        with self.store.connection() as db:
            db.execute(
                "UPDATE resource_growth_transitions SET to_stage=2,delay_ms=30000 "
                "WHERE resource_reference=60 AND from_stage=1"
            )
        original = self.store.connection
        calls = [0]

        @contextmanager
        def change_policy_after_candidate_read():
            calls[0] += 1
            current_call = calls[0]
            with original() as db:
                yield db
            if current_call == 1:
                with original() as db:
                    db.execute(
                        "UPDATE resource_growth_transitions SET delay_ms=60000 "
                        "WHERE resource_reference=60 AND from_stage=1"
                    )

        self.store.connection = change_policy_after_candidate_read
        self.assertEqual(self.mature(), [])
        self.assertEqual(self.resource_row(uid)["stage"], 1)
        self.assertIsNone(self.outbox_row(uid))

    def test_cardo_and_fresno_rejections_are_durable_across_ticks_restart_and_concurrent_recovery(
        self,
    ):
        uids = (9910, 9915)
        self.add_resource(uids[0], 60, 3, creation_time=1_000_000)
        self.add_resource(uids[1], 139, 3, creation_time=1_000_000)
        self.clock[0] = 1030.0
        draws = []

        def reject_at_boundary():
            draws.append(0.01)
            return 0.01

        self.assertEqual([], self.mature(random_draw=reject_at_boundary))
        self.assertEqual([0.01, 0.01], draws)
        for uid in uids:
            self.assertEqual(3, self.resource_row(uid)["stage"])
            self.assertIsNone(self.outbox_row(uid))
        with self.store.connection() as db:
            decisions = list(
                db.execute(
                    "SELECT probability,draw,accepted FROM resource_growth_decisions "
                    "WHERE resource_uid=ANY(%s) AND from_stage=3 ORDER BY resource_uid",
                    (list(uids),),
                )
            )
            self.assertEqual(
                [(0.01, 0.01, False)] * 2, [tuple(row.values()) for row in decisions]
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM profession_xp_receipts"
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
            )

        reopened = self.reopen()
        reopened.clock = self.store.clock
        runtimes = (Plantings(reopened), Plantings(self.store))
        calls = []

        def forbidden_reroll():
            calls.append(True)
            raise AssertionError("persisted rejection must not reroll")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    runtime.mature,
                    self.groups,
                    publish=self.deliveries.append,
                    random_draw=forbidden_reroll,
                )
                for runtime in runtimes
            ]
            self.assertEqual(
                [[], []], [future.result(timeout=10) for future in futures]
            )
        self.assertEqual([], calls)
        for uid in uids:
            self.assertEqual(3, self.resource_row(uid)["stage"])
            self.assertIsNone(self.outbox_row(uid))

    def test_probability_zero_rejects_once_and_probability_one_skips_the_draw(self):
        rejected_uids = (9911, 9916)
        self.add_resource(rejected_uids[0], 60, 3, creation_time=1_000_000)
        self.add_resource(rejected_uids[1], 139, 3, creation_time=1_000_000)
        self.set_growth_probability(60, 3, 0.0)
        self.set_growth_probability(139, 3, 0.0)
        draws = []
        self.clock[0] = 1030.0
        self.assertEqual([], self.mature(random_draw=lambda: draws.append(0.0) or 0.0))
        self.assertEqual([0.0, 0.0], draws)
        for uid in rejected_uids:
            self.assertEqual(3, self.resource_row(uid)["stage"])
            self.assertIsNone(self.outbox_row(uid))
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT probability,draw,accepted FROM resource_growth_decisions "
                    "WHERE resource_uid=ANY(%s) ORDER BY resource_uid",
                    (list(rejected_uids),),
                )
            )
            self.assertEqual(
                [(0.0, 0.0, False)] * 2, [tuple(row.values()) for row in rows]
            )

        accepted_uids = (9912, 9917)
        self.add_resource(accepted_uids[0], 60, 3, creation_time=1_000_000)
        self.add_resource(accepted_uids[1], 139, 3, creation_time=1_000_000)
        self.set_growth_probability(60, 3, 1.0)
        self.set_growth_probability(139, 3, 1.0)
        result = self.mature(
            random_draw=lambda: (_ for _ in ()).throw(
                AssertionError("probability one does not draw")
            )
        )
        self.assertEqual(
            set(accepted_uids), {event["resource_uid"] for event in result}
        )
        for uid in accepted_uids:
            self.assertEqual(4, self.resource_row(uid)["stage"])
            self.assertIsNotNone(self.outbox_row(uid))
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM resource_growth_decisions WHERE resource_uid=ANY(%s)",
                    (list(accepted_uids),),
                ).fetchone()["n"],
            )

    def test_probability_zero_rejection_is_generic_for_other_flora(self):
        uid = 9920
        self.add_resource(uid, 23, 3, creation_time=1_000_000)
        self.set_growth_probability(23, 3, 0.0)
        self.clock[0] = 1030.0
        self.assertEqual([], self.mature(random_draw=lambda: 0.0))
        self.assertEqual(3, self.resource_row(uid)["stage"])
        self.assertIsNone(self.outbox_row(uid))
        with self.store.connection() as db:
            decision = db.execute(
                "SELECT probability,draw,accepted FROM resource_growth_decisions "
                "WHERE resource_uid=%s",
                (uid,),
            ).fetchone()
        self.assertEqual((0.0, 0.0, False), tuple(decision.values()))

    def test_invalid_growth_draw_has_no_decision_and_can_retry(self):
        self.clock[0] = 1030.0
        for uid, reference in ((9913, 60), (9918, 139)):
            with self.subTest(reference=reference):
                self.add_resource(uid, reference, 3, creation_time=1_000_000)
                with self.assertRaisesRegex(ValueError, "planting roll"):
                    self.mature(random_draw=lambda: 1.0)
                self.assertEqual(3, self.resource_row(uid)["stage"])
                self.assertIsNone(self.outbox_row(uid))
                with self.store.connection() as db:
                    self.assertIsNone(
                        db.execute(
                            "SELECT 1 FROM resource_growth_decisions WHERE resource_uid=%s",
                            (uid,),
                        ).fetchone()
                    )
                result = self.mature(random_draw=lambda: 0.0)
                self.assertEqual({uid}, {event["resource_uid"] for event in result})
                self.assertEqual(4, self.resource_row(uid)["stage"])

    def test_growth_sql_failure_rolls_back_decision_stage_and_outbox_then_retries(self):
        from psycopg.errors import RaiseException

        uids = (9914, 9919)
        self.add_resource(uids[0], 60, 3, creation_time=1_000_000)
        self.add_resource(uids[1], 139, 3, creation_time=1_000_000)
        self.clock[0] = 1030.0
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION fail_flora_growth_update() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'growth update blocked'; "
                "END $$"
            )
            db.execute(
                "CREATE TRIGGER fail_flora_growth_update BEFORE UPDATE ON planted_resources "
                "FOR EACH ROW WHEN (NEW.resource_uid IN (9914,9919)) "
                "EXECUTE FUNCTION fail_flora_growth_update()"
            )
        with self.assertRaisesRegex(RaiseException, "growth update blocked"):
            self.mature(random_draw=lambda: 0.0)
        for uid in uids:
            self.assertEqual(3, self.resource_row(uid)["stage"])
            self.assertIsNone(self.outbox_row(uid))
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM resource_growth_decisions WHERE resource_uid=ANY(%s)",
                    (list(uids),),
                ).fetchone()["n"],
            )
            db.execute("DROP TRIGGER fail_flora_growth_update ON planted_resources")
            db.execute("DROP FUNCTION fail_flora_growth_update()")
        result = self.mature(random_draw=lambda: 0.0)
        self.assertEqual(set(uids), {event["resource_uid"] for event in result})
        for uid in uids:
            self.assertEqual(4, self.resource_row(uid)["stage"])


if __name__ == "__main__":
    unittest.main()
