"""Private bounded receipt adapter tests; no game-service activation."""
import copy
import uuid
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import adapters, service
from wakfu_server.achievements import storage as native_storage


class CustomTaskAdaptersPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("adapter-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Adapter Owner")[
            "id"
        ]
        self.operation = uuid.uuid4().hex
        self.request = dict(action_id=616, item_uid=999, x=0, y=0)
        self.resource = dict(
            resource_uid=123456,
            resource_reference=192,
            map_id=9,
            instance_id=1,
            x=0,
            y=0,
            z=0,
            stage=1,
            creation_time=0,
        )
        self.seed = dict(item_reference=7361, action_id=616, resource_reference=192)
        self.definition = dict(
            resource_reference=192, monster_resource=True, monster_family_ids=[68]
        )

    def receipt(self, db, success=True, character=None):
        db.execute(
            "INSERT INTO planting_receipts "
            "(operation_id,character_id,item_uid,request,resource,success) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (
                self.operation,
                self.character if character is None else character,
                999,
                Jsonb(self.request),
                Jsonb(self.resource) if success else None,
                success,
            ),
        )

    def plant(self, db, **overrides):
        arguments = dict(
            request=copy.deepcopy(self.request),
            resource=copy.deepcopy(self.resource),
            seed=copy.deepcopy(self.seed),
            definition=copy.deepcopy(self.definition),
            actual_seed_reference=7361,
        )
        arguments.update(overrides)
        return adapters.monster_planting(
            db, self.account, self.character, self.operation, **arguments
        )

    def test_success_consumed_last_seed_absent_resource_and_replay(self):
        # Neither inventory_items nor planted_resources is needed after a receipt.
        with self.store.connection() as db:
            self.receipt(db)
            self.plant(db)
            self.assertTrue(self.plant(db)["replayed"])
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[1]["count"], 1
            )
            row = db.execute(
                "SELECT payload FROM character_custom_task_events "
                "WHERE character_id=%s",
                (self.character,),
            ).fetchone()
            self.assertEqual(row["payload"]["family_ids"], [68])

    def test_failure_missing_foreign_cancel_and_rollback_never_credit(self):
        with self.assertRaises(ValueError), self.store.connection() as db:
            self.plant(db)  # cancelled/missing receipt
        with self.store.connection() as db:
            self.receipt(db, False)
            self.assertEqual(self.plant(db)["updated"], [])
        with self.assertRaises(ValueError), self.store.connection() as db:
            adapters.monster_planting(
                db,
                self.account + 1,
                self.character,
                self.operation,
                request=self.request,
                resource=self.resource,
                seed=self.seed,
                definition=self.definition,
                actual_seed_reference=7361,
            )
        self.operation = uuid.uuid4().hex
        other = self.store.create_character(self.account, "Other Adapter")["id"]
        with self.store.connection() as db:
            self.receipt(db, character=other)
        with self.assertRaises(ValueError), self.store.connection() as db:
            self.plant(db)
        self.operation = uuid.uuid4().hex
        self.resource["resource_uid"] += 1
        with self.assertRaises(RuntimeError), self.store.connection() as db:
            self.receipt(db)
            self.plant(db)
            raise RuntimeError("Enclosing planting creation rolled back")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                0,
            )

    def test_forged_source_binding_and_conflicting_replay_rejected(self):
        with self.store.connection() as db:
            self.receipt(db)
        for changes in [
            dict(actual_seed_reference=1),
            dict(seed=dict(self.seed, action_id=1)),
            dict(definition=dict(self.definition, resource_reference=1)),
            dict(resource=dict(self.resource, resource_uid=2)),
            dict(request=dict(self.request, item_uid=2)),
        ]:
            with self.subTest(changes=changes), self.assertRaises(
                ValueError
            ), self.store.connection() as db:
                self.plant(db, **changes)
        with self.store.connection() as db:
            self.plant(db)
        with self.assertRaises(ValueError), self.store.connection() as db:
            self.plant(db, definition=dict(self.definition, monster_family_ids=[69]))

    def test_native_runtime_hex_identity_rejects_alternate_uuid_forms(self):
        # Plantings.begin constructs uuid.uuid4().hex and forwards it unchanged.
        with self.store.connection() as db:
            self.receipt(db)
            self.plant(db)
        for invalid in [
            str(uuid.UUID(self.operation)),
            self.operation.upper(),
            "0" * 32,
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(
                ValueError
            ), self.store.connection() as db:
                adapters.monster_planting(
                    db,
                    self.account,
                    self.character,
                    invalid,
                    request=self.request,
                    resource=self.resource,
                    seed=self.seed,
                    definition=self.definition,
                    actual_seed_reference=7361,
                )
        with self.store.connection() as db:
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[1]["count"], 1
            )

    def test_native_receipt_roster_only_zero_kills_and_owner_reject(self):
        with self.assertRaises(ValueError), self.store.connection() as db:
            adapters.original_kills(db, self.account, self.character, 1)
        with self.store.connection() as db:
            # Fixture freezes the exact native _event shape; no adapter roster argument.
            native_storage.record_event(
                db,
                self.character,
                "fight:1",
                dict(
                    fight_id=1,
                    original_monsters=[[-1, 1], [-2, 2]],
                    original_breeds=[1, 2],
                    completed_dungeon_id=None,
                ),
            )
            adapters.original_kills(db, self.account, self.character, 1)
            self.assertTrue(
                adapters.original_kills(db, self.account, self.character, 1)["replayed"]
            )
            native_storage.record_event(
                db,
                self.character,
                "fight:2",
                dict(
                    fight_id=2,
                    original_monsters=[],
                    original_breeds=[],
                    completed_dungeon_id=None,
                ),
            )
            self.assertEqual(
                adapters.original_kills(db, self.account, self.character, 2)["updated"],
                [],
            )
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[0]["count"], 2
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                1,
            )
        with self.assertRaises(ValueError), self.store.connection() as db:
            adapters.original_kills(db, self.account + 1, self.character, 1)
