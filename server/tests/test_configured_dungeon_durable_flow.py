"""Current route settlement boundary using explicit finished-result fixtures.

Admission, completed route choice and arrival at each battle are fixture premises.
A required paid scene is started through its real consumer with an explicitly
granted inventory-item premise; its receipt/payment is never fabricated. No
earned native victory, outer entry-criteria validation, combat AI or socket
bootstrap claim follows from this test. Persistent progression, ordinary exit and delivery consumers are
real and execute only in PostgresCase's disposable schema.
"""
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import json, os, struct, traceback
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from test_dungeon_progression import DungeonProgressionPostgresTests as PartyFixture
from configured_dungeon_flow_fixture import (
    variants,
    native_approaches,
    declared_initial_open_scene,
)


class CurrentDurableFlow(PostgresCase):
    player = PartyFixture.player
    party = PartyFixture.party

    def setUp(self):
        if not os.environ.get("WAKFU_FLOW_SNAPSHOT"):
            self.skipTest(
                "Exported canonical flow fixture required via WAKFU_FLOW_SNAPSHOT"
            )
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.snapshot = json.loads(Path(os.environ["WAKFU_FLOW_SNAPSHOT"]).read_text())
        from wakfu_server import (
            dungeon_runtime_config,
            dungeon_instances,
            native_scene_start,
        )

        policy = patch.object(
            native_scene_start, "_policy_database", return_value=self.store
        )
        policy.start()
        self.addCleanup(policy.stop)
        native_scene_start._runtime_rules.cache_clear()
        native_scene_start._source_identities.cache_clear()
        self.addCleanup(native_scene_start._runtime_rules.cache_clear)
        self.addCleanup(native_scene_start._source_identities.cache_clear)
        self.records = []
        with self.store.connection() as db:
            from tools.export_native_scene_seed import scene_sql

            schema = db.execute("SELECT current_schema() AS name").fetchone()["name"]
            for statement in scene_sql(
                self.snapshot["normalized_scene_tables"], schema=schema
            ):
                db.execute(statement)
            for original in self.snapshot["configurations"]:
                config = deepcopy(original["configuration"])
                present = db.execute(
                    "SELECT configuration FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s",
                    (original["route"], original["version"]),
                ).fetchone()
                if present is not None and present["configuration"] != config:
                    # Existing migrations may seed a historical document at the
                    # same version. Preserve it and isolate this exact source.
                    config["version"] = 900000 + original["version"]
                    config["context_policy"]["policy_version"] = config["version"]
                dungeon_runtime_config.install_configuration(db, config)
                self.records.append(dict(original, configuration=config))
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb(dict(schema_version=1, routes=self.snapshot["routes"])),),
            )
        self.routes = dungeon_instances.load_runtime_routes(self.store)
        self.results = []
        self.delivery_store = self.reopen()

    def test_all_selected_current_routes_from_finished_results(self):
        requested = os.environ.get("WAKFU_FLOW_ROUTES", "all")
        for record in self.records:
            for key, config in variants(record):
                identity = record["route"] + "|" + key
                if (
                    requested != "all"
                    and record["route"] not in requested.split(",")
                    and identity not in requested.split(",")
                ):
                    continue
                with self.subTest(route=record["route"], variant=key):
                    try:
                        result = self.journey(record, key, config)
                    except Exception as error:
                        self.results.append(
                            dict(
                                route=record["route"],
                                variant=key,
                                passed=False,
                                error=type(error).__name__,
                                detail=str(error),
                                traceback=traceback.format_exc(),
                            )
                        )
                        self.write_receipt()
                        raise
                    self.results.append(result)
                    self.write_receipt()
        self.assertTrue(self.results)

    def write_receipt(self):
        if not os.environ.get("WAKFU_FLOW_RECEIPT"):
            return
        output = Path(os.environ["WAKFU_FLOW_RECEIPT"])
        output.write_text(
            json.dumps(
                dict(
                    scope="Owned admitted instance + canonical chosen-route premises; finished battle result fixtures, not earned native combat or live bootstrap",
                    canonical_snapshot=self.snapshot["captured_at"],
                    passed=sum(r["passed"] for r in self.results),
                    failed=sum(not r["passed"] for r in self.results),
                    cases=self.results,
                ),
                indent=2,
                default=str,
            )
            + "\n"
        )

    def test_declared_open_scene_keeps_current_encounter_authority(self):
        selected = [
            r
            for r in self.records
            if declared_initial_open_scene(r["configuration"]["topology"])
        ]
        self.assertTrue(selected)
        for record in selected:
            with self.subTest(route=record["route"]):
                self.results.append(
                    self.journey(
                        record,
                        "canonical",
                        record["configuration"],
                        probe_open_scene=True,
                    )
                )
                self.write_receipt()

    def journey(self, record, key, config, *, probe_open_scene=False):
        from wakfu_server import (
            dungeon_instances,
            dungeon_runtime_config,
            dungeon_progression,
            dungeon_auto_transition,
            dungeon_auto_exit,
            dungeon_native_flow,
            dungeon_branches,
            heroes,
        )
        from wakfu_server.position_buffer import Positions

        members, party_id = self.party(2)
        leader = members[0]
        hero = self.store.create_character(
            leader["account"],
            "Hero " + "".join(chr(65 + int(x)) for x in str(leader["character"]["id"])),
        )
        heroes.add(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            hero["id"],
        )
        company = [
            dict(
                account=leader["account"],
                generation=leader["generation"],
                character=hero,
            )
        ]
        owners = members
        everyone = members + company
        ids = [m["character"]["id"] for m in everyone]
        route = config["route"]
        entry = next(r for r in self.routes if r.key == route["key"])
        topology = config["topology"]
        mid = topology["asset_map_id"]
        if key.startswith("entry:"):
            selected = key.split(":", 1)[1]
            source = next(
                s
                for s in topology["entry_path_policy"]["entry_sources"]
                if s["path"] == selected
            )
            entry = dungeon_instances.route_for_entry(
                source["map_id"], source["source_id"], source["destination_id"]
            )
        plan = dungeon_runtime_config.plan_from_configuration(config)
        main = [room.order for room in plan.rooms]
        first = dungeon_branches.selected_room(topology, main[0])
        with self.store.connection() as db:
            party = db.execute(
                "SELECT leader_id,revision FROM player_parties WHERE id=%s", (party_id,)
            ).fetchone()
            instance = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id,context_route_key,context_policy_version) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING instance_id",
                (
                    party_id,
                    party["revision"],
                    party["leader_id"],
                    entry.template_id,
                    entry.definition_id,
                    entry.entry_map_id,
                    entry.entry_object_id,
                    entry.destination_id,
                    entry.start_map_id,
                    route["key"],
                    config["version"],
                ),
            ).fetchone()["instance_id"]
            for member in everyone:
                identity = member["character"]["id"]
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        instance,
                        party_id,
                        identity,
                        member["generation"],
                        party["revision"],
                        "leader" if identity == party["leader_id"] else "member",
                    ),
                )
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (mid, instance, *first["anchor"], identity),
                )
            run = dungeon_progression.initialize_run(db, instance, party_id, plan)
            if key.startswith(("entry:", "branch:")):
                db.execute(
                    "UPDATE dungeon_room_runs SET branch_key=%s WHERE instance_id=%s",
                    (key.split(":", 1)[1], instance),
                )
            elif key.startswith("rotation:"):
                from wakfu_server.dungeon_excavation import digest

                selector = int(key.split(":", 1)[1])
                db.execute(
                    "UPDATE dungeon_room_runs SET branch_key=%s WHERE instance_id=%s",
                    (str(selector), instance),
                )
                db.execute(
                    "INSERT INTO dungeon_excavation_runs(instance_id,catalog_hash,rule_sha256,selected_source_id,selected_rooms_sha256) VALUES(%s,%s,%s,%s,%s)",
                    (
                        instance,
                        run["catalog_hash"],
                        topology["excavation_access"]["rule_sha256"],
                        selector,
                        digest(run["rooms"]),
                    ),
                )
        positions = Positions(self.store, lease_active=lambda *_: True)
        for member in owners:
            positions.attach(
                member["account"],
                member["generation"],
                self.store.character(member["account"], member["character"]["id"]),
            )
        company_before = self.company_snapshot(leader)
        paid_scene = self.start_required_scene(config, owners, positions)
        settlements = []
        delivered = 0
        control = None
        if probe_open_scene:
            from wakfu_server.combat_group_store import PersistentGroups
            from wakfu_server.combat_terrain import map_geometry

            control = dict(
                groups=PersistentGroups(self.store),
                geometry=map_geometry(mid),
                checks=[],
                previous=None,
            )
        for order in main:
            room = dungeon_branches.selected_room(topology, order)
            # A completed battle at this admitted room is the test input; world
            # path reachability has a separate read-only native graph audit.
            self.place_company(owners, positions, room["anchor"])
            if control is not None:
                self.probe_current_group(control, instance, config, order)
            with self.store.connection() as db:
                fight = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                for member in everyone:
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,session_generation,team) VALUES(%s,%s,%s,%s,0)",
                        (
                            fight,
                            member["character"]["id"],
                            member["account"],
                            member["generation"],
                        ),
                    )
                dungeon_progression.bind_encounter(
                    db,
                    instance,
                    party_id,
                    leader["character"]["id"],
                    fight,
                    player_team=0,
                )
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
                )
                outcome = SimpleNamespace(
                    id=fight, phase="finished", winner=0, map_id=mid
                )
                result = dungeon_progression.settle_encounter(db, outcome)
                replay = dungeon_progression.settle_encounter(db, outcome)
                self.assertTrue(result["victory"])
                self.assertFalse(result["replay"])
                self.assertTrue(replay["replay"])
                self.assertEqual(result["revision"], replay["revision"])
                self.assertEqual(result["completed"], order == main[-1])
            if control is not None and result["completed"]:
                from wakfu_server import dungeon_runtime

                with self.store.connection() as db:
                    self.assertIsNone(
                        dungeon_runtime.ensure_current_room(
                            db, control["groups"], instance, control["geometry"]
                        )
                    )
            settlements.append(
                dict(
                    room=order,
                    fight_id=fight,
                    completed=result["completed"],
                    revision=result["revision"],
                )
            )
            if topology["policy"] == "local_accessible_anchor_policy":
                if result["completed"]:
                    moved = dungeon_auto_exit.complete(
                        self.store,
                        instance,
                        fight,
                        topology=topology,
                        in_fight=lambda _: False,
                    )
                else:
                    moved = dungeon_auto_transition.advance(
                        self.store,
                        instance,
                        fight,
                        topology=topology,
                        in_fight=lambda _: False,
                    )
                self.assertFalse(moved.get("deferred", False))
                delivered += self.deliver(
                    owners,
                    positions,
                    expect_kind="exit" if result["completed"] else "door",
                    retry_first=True,
                )
            else:
                packets = dungeon_native_flow.packets(
                    dict(topology, _entry_main_completed=result["completed"]),
                    map_id=mid,
                    instance_id=instance,
                    unlocked_room=result["current_room"],
                    completed=result["completed"],
                )
                self.assertTrue(
                    packets
                )  # May include native presentation packets after Door state.
            self.assertEqual(self.company_snapshot(leader), company_before)
            with self.store.connection() as db:
                self.assertEqual(
                    {
                        r["character_id"]
                        for r in db.execute(
                            "SELECT character_id FROM player_party_members WHERE party_id=%s",
                            (party_id,),
                        ).fetchall()
                    },
                    {m["character"]["id"] for m in owners},
                )
        if topology["policy"] != "local_accessible_anchor_policy":
            delivered += self.native_exit(config, entry, instance, owners, positions)
        with self.store.connection() as db:
            run = db.execute(
                "SELECT status,current_room FROM dungeon_room_runs WHERE instance_id=%s",
                (instance,),
            ).fetchone()
            self.assertEqual(
                (run["status"], run["current_room"]), ("completed", main[-1])
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["status"],
                "closed",
            )
            rows = db.execute(
                "SELECT character_id,status FROM dungeon_instance_members WHERE instance_id=%s",
                (instance,),
            ).fetchall()
            self.assertEqual({r["character_id"] for r in rows}, set(ids))
            self.assertEqual({r["status"] for r in rows}, {"returned"})
            self.assertEqual(
                {
                    r["instance_id"]
                    for r in db.execute(
                        "SELECT instance_id FROM characters WHERE id=ANY(%s)", (ids,)
                    ).fetchall()
                },
                {0},
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM dungeon_transition_outbox WHERE instance_id=%s AND status='pending'",
                    (instance,),
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(self.company_snapshot(leader), company_before)
        for _, item in positions._entry_snapshot():
            self.assertFalse(item["dirty"])
            self.assertEqual(item["persisted"]["instance_id"], 0)
            self.assertEqual(item["current"]["instance_id"], 0)
        later = self.store.create_character(
            leader["account"],
            "Later "
            + "".join(chr(65 + int(x)) for x in str(leader["character"]["id"])),
        )
        self.assertEqual(
            self.store.select_character(
                leader["account"], leader["generation"], later["id"]
            )["instance_id"],
            0,
        )
        self.assertEqual(
            self.store.select_character(
                leader["account"], leader["generation"], leader["character"]["id"]
            )["instance_id"],
            0,
        )
        return dict(
            route=record["route"],
            source_version=record["version"],
            fixture_version=config["version"],
            variant=key,
            passed=True,
            policy=topology["policy"],
            mandatory_rooms=len(main),
            settlements=settlements,
            owned_members=3,
            selected_owners=2,
            owned_heroes=1,
            acknowledged_transitions=delivered,
            paid_scene=paid_scene,
            open_scene_group_control=None if control is None else control["checks"],
            company_preserved=True,
            positions_clean=True,
            later_creation_and_selection=True,
            reopened_store_delivery=True,
            scope="Main settlement and exit only; optional battle and initial room hydration are outside this test",
        )

    def probe_current_group(self, control, instance, config, order):
        from wakfu_server import dungeon_runtime, dungeon_branches

        topology = config["topology"]
        room = dungeon_branches.selected_room(topology, order)
        with self.store.connection() as db:
            group = dungeon_runtime.ensure_current_room(
                db, control["groups"], instance, control["geometry"]
            )
            self.assertEqual(group["room_order"], order)
            key = (topology["asset_map_id"], instance, group["group_id"])
            points = [tuple(m[k] for k in ("x", "y", "z")) for m in group["members"]]
            self.assertTrue(
                dungeon_runtime.combat_room_cells(
                    db, key, tuple(room["anchor"]), points
                )
            )
            receipts = db.execute(
                "SELECT room_order FROM dungeon_room_spawn_receipts WHERE instance_id=%s ORDER BY room_order",
                (instance,),
            ).fetchall()
            self.assertEqual(
                [r["room_order"] for r in receipts], list(range(1, order + 1))
            )
            replay = dungeon_runtime.ensure_current_room(
                db, control["groups"], instance, control["geometry"]
            )
            self.assertEqual(replay["group_id"], group["group_id"])
            if control["previous"] is None:
                future = dungeon_branches.selected_room(topology, order + 1)
                with self.assertRaisesRegex(ValueError, "outside its pinned room"):
                    dungeon_runtime.combat_room_cells(
                        db, key, tuple(future["anchor"]), points
                    )
            else:
                previous = control["previous"]
                self.assertNotEqual(previous["key"], key)
                with self.assertRaisesRegex(ValueError, "not the current dungeon room"):
                    dungeon_runtime.combat_room_cells(
                        db, previous["key"], previous["anchor"], previous["positions"]
                    )
            control["previous"] = dict(
                key=key, anchor=tuple(room["anchor"]), positions=points
            )
            control["checks"].append(
                dict(
                    room=order,
                    group_id=group["group_id"],
                    spawned_only_through_current_room=True,
                    current_combat_area_admitted=True,
                    future_area_or_prior_group_rejected=True,
                    idempotent_group_replay=True,
                )
            )

    def start_required_scene(self, config, owners, positions):
        from wakfu_server import native_scene_start, combat_terrain, dungeon_difficulty
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.inventory_items import grant

        rule = native_scene_start.binding(config["topology"])
        if rule is None:
            return None
        payer = owners[0]
        identity = payer["character"]["id"]
        # Inventory acquisition is outside this test. Consumption, ownership,
        # persisted profile, ordinary spawn and duplicate charge protection are real.
        item, quantity = native_scene_start._native_source(rule)
        self.place_company(owners, positions, rule["approaches"][0])
        actor = self.store.character(payer["account"], identity)
        with self.store.connection() as db:
            choice = dungeon_difficulty.selection(db, actor["instance_id"])
            self.assertTrue(choice["competitive"])
            self.assertEqual(
                choice["competitive_max_level"], rule["competitive_ceiling"]
            )
            grant(
                self.store,
                payer["account"],
                payer["generation"],
                identity,
                reference=item,
                quantity=quantity,
                container=actor["inventory_containers"][0]["uid"],
                slot=0,
                allowed_references={item},
                db=db,
            )
        groups = PersistentGroups(self.store)
        geometry = combat_terrain.map_geometry(rule["map_id"])
        body = struct.pack(">qHH", rule["source_id"], rule["wire_action"], 0)

        def start():
            return native_scene_start.start(
                self.store,
                payer["account"],
                payer["generation"],
                self.store.character(payer["account"], identity),
                body,
                groups=groups,
                geometry=geometry,
                blocked=False,
                is_hero=False,
            )

        started = start()
        self.assertFalse(started["replay"])
        self.assertTrue(started["group"]["members"])
        repeated = start()
        self.assertTrue(repeated["replay"])
        self.assertEqual(started["profile"], repeated["profile"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COALESCE(sum(quantity),0) n FROM inventory_items WHERE character_id=%s AND reference=%s",
                    (identity, item),
                ).fetchone()["n"],
                0,
            )
            receipts = db.execute(
                "SELECT payment,profile FROM native_scene_start_receipts WHERE instance_id=%s",
                (actor["instance_id"],),
            ).fetchall()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["profile"], started["profile"])
        self.assertTrue(receipts[0]["payment"])
        return dict(
            policy_id=rule["policy_id"],
            payment_item=item,
            quantity=quantity,
            real_payment=True,
            duplicate_no_second_charge=True,
            inventory_acquisition="Explicit test premise, not a gameplay acquisition claim",
            started_native_group=True,
            native_ready_and_victory="Outside this finished-result consumer test",
        )

    def company_snapshot(self, leader):
        with self.store.connection() as db:
            return dict(
                roster=db.execute(
                    "SELECT leader_id,revision FROM account_hero_rosters WHERE account_id=%s",
                    (leader["account"],),
                ).fetchone(),
                slots=db.execute(
                    "SELECT slot,character_id FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                    (leader["account"],),
                ).fetchall(),
            )

    def place_company(self, owners, positions, point):
        for member in owners:
            actor = self.store.character(member["account"], member["character"]["id"])
            self.store.move(
                member["account"],
                member["generation"],
                actor["id"],
                {k: actor[k] for k in ("x", "y", "z")},
                dict(zip(("x", "y", "z"), point)),
            )
            from wakfu_server.heroes import follow_main

            with self.store.connection() as db:
                follow_main(
                    db, self.store, member["account"], member["generation"], actor["id"]
                )
            positions.rebind_selected(
                member["account"], member["generation"], actor["id"]
            )

    def deliver(self, owners, positions, *, expect_kind, retry_first):
        from wakfu_server import dungeon_instances
        from wakfu_server.dungeon_transition_delivery import deliver_pending_transitions

        count = 0
        for index, member in enumerate(owners):
            account, generation, identity = (
                member["account"],
                member["generation"],
                member["character"]["id"],
            )
            pending = dungeon_instances.pending_transitions(
                self.store, account, generation, identity
            )
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["transition_kind"], expect_kind)
            original = self.store.character(account, identity)
            kwargs = dict(
                worker_generation=generation,
                current_location=lambda: {
                    k: original[k] for k in ("map_id", "instance_id", "x", "y", "z")
                },
                in_fight=lambda: False,
            )
            if retry_first and index == 0:
                failed = deliver_pending_transitions(
                    self.store,
                    account,
                    generation,
                    identity,
                    bootstrap=lambda _: False,
                    **kwargs,
                )
                self.assertEqual(failed["state"], "bootstrap_incomplete")
                self.assertEqual(
                    len(
                        dungeon_instances.pending_transitions(
                            self.store, account, generation, identity
                        )
                    ),
                    1,
                )

            def bootstrap(event):
                positions.rebind_selected(account, generation, identity)
                return True  # Explicit complete-write fixture, not a socket/UI claim.

            result = deliver_pending_transitions(
                self.delivery_store,
                account,
                generation,
                identity,
                bootstrap=bootstrap,
                **kwargs,
            )
            self.assertFalse(
                dungeon_instances.pending_transitions(
                    self.store, account, generation, identity
                )
            )
            count += 1
        return count

    def native_exit(self, config, entry, instance, owners, positions):
        from wakfu_server import dungeon_exit, generic_transports, teleporter_approach
        from wakfu_server.movement import Movement

        topology = config["topology"]
        mid = topology["asset_map_id"]
        choices = []
        for binding in topology["physical_exit_objects"]:
            source = generic_transports.source(mid, binding["source_id"])
            candidates = [
                d
                for d in source["destinations"]
                if (
                    d["destination_id"] == binding["destination_id"]
                    if "destination_id" in binding
                    else d["map_id"] == entry.entry_map_id
                    and not d.get("criterion", "").strip()
                )
            ]
            if len(candidates) == 1:
                approaches = set(
                    map(tuple, binding.get("native_approach_cells", ()))
                ) or native_approaches(source)
                # Use original integral floor coordinates matching the native
                # approach exactly; never round/coerce a source object's float.
                floor = [tuple(c) for c in topology["exploration_geometry"]["cells"]]
                points = sorted(
                    c
                    for c in floor
                    if all(type(v) is int for v in c) and c in approaches
                )
                self.assertTrue(
                    points,
                    f"Exit {source['id']} has no integral source-qualified floor approach",
                )
                choices.append((binding, source, candidates[0], points[0]))
        self.assertTrue(choices)
        binding, source, destination, point = max(
            choices, key=lambda choice: choice[0]["room_order"]
        )
        self.place_company(owners, positions, point)
        for member in owners:
            actor = self.store.character(member["account"], member["character"]["id"])
            result = dungeon_exit.leave(
                self.store,
                member["account"],
                member["generation"],
                actor["id"],
                struct.pack(">qiBi", source["id"], destination["destination_id"], 0, 2),
                source_allowed=teleporter_approach.callback(
                    Movement(actor), map_id=mid, instance_id=instance
                ),
                in_fight=lambda _: False,
                positions=positions,
            )
            self.assertEqual(result["instance_id"], 0)
        return self.deliver(owners, positions, expect_kind="exit", retry_first=True)
