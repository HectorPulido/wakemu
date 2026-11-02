"""A skipped worker scene cannot strand an already committed owned transition."""

from unittest.mock import patch
from types import SimpleNamespace

from postgres_case import PostgresCase
import test_dungeon_instances
from wakfu_server import dungeon_exit, dungeon_instances
from wakfu_server.dungeon_hydration import prepare_transition
from wakfu_server.dungeon_transition_delivery import deliver_pending_transitions
from wakfu_server.position_buffer import Positions
from wakfu_server.dungeon_transition_recovery import DungeonExitDeferred


class DungeonDeliveryRecoveryPostgresTests(PostgresCase):
    install_context_policy = (
        test_dungeon_instances.DungeonInstanceTests.install_context_policy
    )
    player = test_dungeon_instances.DungeonInstanceTests.player
    party = test_dungeon_instances.DungeonInstanceTests.party
    enter = test_dungeon_instances.DungeonInstanceTests.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        # These unequipped fixture actors exercise travel ownership only. No
        # resource effect is installed, so compiled combat publication is not
        # a dependency of their empty equipment projection.
        resources = patch(
            "wakfu_server.equipment_resource_bonuses.baseline", return_value=None
        )
        resources.start()
        self.addCleanup(resources.stop)
        self.install_context_policy(1)

    def test_missed_entry_then_exit_reconciles_worker_position_and_preserves_companion(
        self,
    ):
        members, party_id = self.party(2)
        main, companion = members
        account, generation, character_id = (
            main["account"],
            main["generation"],
            main["character"]["id"],
        )
        worker = dict(main["character"])
        positions = Positions(
            self.store,
            lease_active=lambda *key: key == (account, generation, character_id),
        )
        positions.attach(account, generation, worker)
        run = self.enter(main)
        destination = dict(map_id=527, x=-245, y=-89, z=0)
        configuration = {
            "topology": {
                "policy": "local_accessible_anchor_policy",
                "asset_map_id": 1086,
                "completion_destination": {
                    **destination,
                    "provenance": {"policy": "native_entry_approved_walkable_approach"},
                },
            }
        }
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, configuration),
        ):
            dungeon_exit.leave_automatic(
                self.store,
                account,
                generation,
                character_id,
                in_fight=lambda _identity: False,
                positions=positions,
            )

        def bootstrap(event):
            plan = prepare_transition(
                self.store, account, generation, character_id, event
            )
            positions.attach(account, generation, plan.character)
            worker.update(plan.character)
            self.assertEqual(
                [opcode for opcode, _ in plan.packets], [13256, 13974, 12318]
            )
            return True

        result = deliver_pending_transitions(
            self.store,
            account,
            generation,
            character_id,
            worker_generation=generation,
            current_location=lambda: {
                key: worker[key] for key in ("map_id", "instance_id", "x", "y", "z")
            },
            in_fight=lambda: False,
            bootstrap=bootstrap,
        )
        self.assertEqual(result["state"], "delivered")
        self.assertEqual({key: worker[key] for key in destination}, destination)
        self.assertEqual(worker["instance_id"], 0)
        baseline = positions.entries[(account, generation, character_id)]
        self.assertFalse(baseline["dirty"])
        self.assertEqual(baseline["persisted"]["instance_id"], 0)
        self.assertEqual(baseline["persisted"]["y"], destination["y"])
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,status FROM dungeon_instance_members WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchall()
            outbox = db.execute(
                "SELECT transition_kind,status FROM dungeon_transition_outbox WHERE character_id=%s ORDER BY event_id",
                (character_id,),
            ).fetchall()
            social = db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                (party_id,),
            ).fetchall()
        self.assertEqual(
            {row["character_id"]: row["status"] for row in rows},
            {
                character_id: "returned",
                companion["character"]["id"]: "active",
            },
        )
        self.assertEqual(
            [row["status"] for row in outbox], ["superseded", "acknowledged"]
        )
        self.assertEqual(
            {row["character_id"] for row in social},
            {member["character"]["id"] for member in members},
        )
        self.assertEqual(
            self.store.character(companion["account"], companion["character"]["id"])[
                "instance_id"
            ],
            run["instance_id"],
        )
        self.assertEqual(
            dungeon_instances.pending_transitions(
                self.store, account, generation, character_id
            ),
            (),
        )

    def test_broken_hydration_exit_requires_verified_admission_and_keeps_durable_delivery(
        self,
    ):
        members, _ = self.party(2)
        main, companion = members
        account, generation, character_id = (
            main["account"],
            main["generation"],
            main["character"]["id"],
        )
        run = self.enter(main)
        private = self.store.character(account, character_id)
        positions = Positions(
            self.store,
            lease_active=lambda *key: key == (account, generation, character_id),
        )
        positions.attach(account, generation, private)
        source = main["character"]
        from wakfu_server import combat_geometry

        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            side_effect=ValueError("Retired room geometry"),
        ), patch.object(
            combat_geometry,
            "published_geometry",
            return_value=SimpleNamespace(cells=()),
        ):
            with self.assertRaises(DungeonExitDeferred):
                dungeon_exit.leave_recovery(
                    self.store,
                    account,
                    generation,
                    character_id,
                    in_fight=lambda _identity: False,
                    positions=positions,
                )
        self.assertEqual(
            self.store.character(account, character_id)["instance_id"],
            run["instance_id"],
        )
        # The recorded source is from the admitted account's real entry intent;
        # only installed traversable geometry is injected for this fixture.
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            side_effect=ValueError("Retired room geometry"),
        ), patch.object(
            combat_geometry,
            "published_geometry",
            return_value=SimpleNamespace(
                cells={(source["x"], source["y"], source["z"])}
            ),
        ):
            result = dungeon_exit.leave_recovery(
                self.store,
                account,
                generation,
                character_id,
                in_fight=lambda _identity: False,
                positions=positions,
            )
        self.assertEqual(result["instance_id"], 0)
        (event,) = dungeon_instances.pending_transitions(
            self.store, account, generation, character_id
        )
        self.assertEqual(event["transition_kind"], "exit")
        self.assertEqual(event["source_instance_id"], run["instance_id"])
        self.assertEqual(event["destination_instance_id"], 0)
        self.assertEqual(
            tuple(event["destination_" + key] for key in ("map_id", "x", "y", "z")),
            tuple(source[key] for key in ("map_id", "x", "y", "z")),
        )
        self.assertEqual(
            positions.entries[(account, generation, character_id)]["persisted"][
                "instance_id"
            ],
            0,
        )
        self.assertEqual(
            self.store.character(companion["account"], companion["character"]["id"])[
                "instance_id"
            ],
            run["instance_id"],
        )
