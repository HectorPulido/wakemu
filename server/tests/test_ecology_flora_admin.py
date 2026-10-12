"""Isolated PostgreSQL regressions for durable outdoor flora administration."""
import struct
import threading
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import ecology_flora_admin as subject
from wakfu_server import ecology_flora_planner as planner
from wakfu_server.planting_runtime import Plantings


class FloraAdminPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        account = self.store.register("flora-admin", "test-password")["id"]
        with self.store.connection() as db:
            self.character = dict(
                db.execute(
                    "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                    "VALUES(%s,'Flora Admin','flora admin',1,false,0,0,'[]','{}',100,100) "
                    "RETURNING id,account_id,map_id,instance_id,x,y,z",
                    (account,),
                ).fetchone()
            )
        self.groups = type("Groups", (), {"lock": threading.RLock()})()
        self.resource = dict(
            resource_uid=710001,
            map_id=1134,
            instance_id=0,
            x=1,
            y=2,
            z=0,
            resource_reference=60,
            stage=3,
            creation_time=0,
        )

    def insert(self, resource):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource[key] for key in self.resource),
            )

    def test_nuke_fences_flora_events_preserves_monster_seeds_and_private_gardens(self):
        flora = self.resource
        monster = dict(flora, resource_uid=710002, x=3, resource_reference=192)
        private = dict(flora, resource_uid=710003, instance_id=17)
        for row in (flora, monster, private):
            self.insert(row)
        with self.store.connection() as db:
            for row in (flora, monster, private):
                subject._event(db, dict(row, flora_spawn=True))
            db.execute(
                "INSERT INTO resource_growth_decisions VALUES(%s,2,3,1,0.5,TRUE)",
                (flora["resource_uid"],),
            )
            for identity, reference in (("flora-intent", 60), ("monster-intent", 192)):
                action = next(
                    seed["action_id"]
                    for seed in subject.planting.SEEDS.values()
                    if seed["resource_reference"] == reference
                )
                db.execute(
                    "INSERT INTO ecology_planting_intents(id,world_epoch,account_id,generation,character_id,body,actor_location) VALUES(%s,'test',%s,'g',%s,%s,%s)",
                    (
                        identity,
                        self.character["account_id"],
                        self.character["id"],
                        struct.pack(">iqii", action, 1, 1, 2),
                        Jsonb({"map_id": 1134, "instance_id": 0}),
                    ),
                )
            with db.transaction():
                result = subject._nuke(db, 1134, 0, None)
            remaining = db.execute(
                "SELECT resource_uid FROM planted_resources ORDER BY resource_uid"
            ).fetchall()
            events = db.execute(
                "SELECT resource_uid,resource,published FROM planting_growth_outbox ORDER BY resource_uid"
            ).fetchall()
            intents = db.execute(
                "SELECT id,status FROM ecology_planting_intents ORDER BY id"
            ).fetchall()
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_growth_decisions"
                ).fetchone()["n"],
                0,
            )
        self.assertEqual((result["removed"], result["cancelled"]), (1, 1))
        self.assertEqual(
            remaining, [{"resource_uid": 710002}, {"resource_uid": 710003}]
        )
        self.assertEqual(events[0]["resource"]["stage"], 0)
        self.assertNotIn("flora_spawn", events[0]["resource"])
        self.assertFalse(events[0]["published"])
        self.assertEqual([event["resource"]["stage"] for event in events[1:]], [3, 3])
        self.assertEqual(
            intents,
            [
                {"id": "flora-intent", "status": "cancelled"},
                {"id": "monster-intent", "status": "pending"},
            ],
        )
        self.assertEqual([packet[0] for packet in result["packets"]], [12782])

    def test_genesis_persists_new_resources_once_and_replays_full_appearance(self):
        prepared = dict(
            map_id=1134,
            region_id=7,
            definitions={60: {"family_id": 1, "stage": 3}},
            cells=[(1, 2, 0, (60,)), (3, 4, 0, (60,))],
            targets={1: 2},
            warnings=[],
        )
        with patch.dict(
            planner.RESOURCES,
            {
                60: {
                    "family_id": 1,
                    "monster_resource": False,
                    "stage_definitions": [{"actions": [{"profession_id": 72}]}],
                }
            },
        ):
            with self.store.connection() as db:
                with db.transaction():
                    first = subject._genesis(db, 1134, 0, 7, prepared=prepared)
                with db.transaction():
                    second = subject._genesis(db, 1134, 0, 7, prepared=prepared)
        self.assertEqual((first["added"], second["added"]), (2, 0))
        self.assertEqual([packet[0] for packet in first["packets"]], [13135, 13135])
        runtime = Plantings(self.store)
        with self.assertRaisesRegex(OSError, "delivery failed"):
            runtime.publish_growth(
                self.groups,
                publish=lambda _delivery: (_ for _ in ()).throw(
                    OSError("delivery failed")
                ),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planting_growth_outbox WHERE NOT published"
                ).fetchone()["n"],
                2,
            )
        delivered = []
        replayed = runtime.publish_growth(self.groups, publish=delivered.append)
        self.assertEqual(
            {row["resource_uid"] for row in delivered},
            {event["resource_uid"] for event in first["events"]},
        )
        self.assertTrue(all(row["packets"][0][0] == 13135 for row in delivered))
        self.assertEqual(len(replayed), 2)
        self.assertEqual(
            runtime.publish_growth(self.groups, publish=delivered.append), []
        )
        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                2,
            )

    def test_authorization_rejects_before_native_planning(self):
        with patch.object(
            planner, "prepare", side_effect=AssertionError("must not plan")
        ):
            with self.assertRaisesRegex(ValueError, "administrator"):
                subject.execute(
                    self.store, self.groups, self.character, "!genesis-all-flora"
                )

    def test_execute_commits_audit_before_publication_and_leaves_failed_delivery_pending(
        self,
    ):
        with self.store.connection() as db:
            db.execute(
                "UPDATE accounts SET is_admin=TRUE WHERE id=%s",
                (self.character["account_id"],),
            )
        planned = dict(
            rows=[dict(resource_reference=60, stage=3, x=1, y=2, z=0)], warnings=[]
        )

        def publish(scoped):
            with self.store.connection() as db:
                audit = db.execute(
                    "SELECT command,outcome FROM ecology_admin_operations WHERE id=%s",
                    (scoped["operation_id"],),
                ).fetchone()
            self.assertEqual(audit["command"], "!genesis-all-flora")
            self.assertNotIn("location_packets", audit["outcome"])
            raise OSError("temporary delivery failure")

        with patch.dict(
            subject.REGIONS, {(1134, 7): {"plant_capacity": 100}}, clear=True
        ), patch.object(planner, "prepare", return_value={}), patch.object(
            planner, "plan", return_value=planned
        ):
            result = subject.execute(
                self.store,
                self.groups,
                self.character,
                "!genesis-all-flora",
                publish=publish,
            )
        self.assertEqual(result["added"], 1)
        self.assertEqual(len(result["publication_failures"]), 1)
        with self.store.connection() as db:
            self.assertFalse(
                db.execute("SELECT published FROM planting_growth_outbox").fetchone()[
                    "published"
                ]
            )

    def test_audit_failure_rolls_back_created_flora_and_outbox(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE accounts SET is_admin=TRUE WHERE id=%s",
                (self.character["account_id"],),
            )
            db.execute(
                "CREATE FUNCTION reject_flora_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced flora audit failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_flora_audit BEFORE INSERT ON ecology_admin_operations FOR EACH ROW EXECUTE FUNCTION reject_flora_audit()"
            )
        planned = dict(
            rows=[dict(resource_reference=60, stage=3, x=1, y=2, z=0)], warnings=[]
        )
        with patch.dict(
            subject.REGIONS, {(1134, 7): {"plant_capacity": 100}}, clear=True
        ), patch.object(planner, "prepare", return_value={}), patch.object(
            planner, "plan", return_value=planned
        ):
            with self.assertRaisesRegex(Exception, "forced flora audit failure"):
                subject.execute(
                    self.store, self.groups, self.character, "!genesis-all-flora"
                )
        with self.store.connection() as db:
            for table in (
                "planted_resources",
                "planting_growth_outbox",
                "ecology_admin_operations",
            ):
                self.assertEqual(
                    db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"], 0
                )
