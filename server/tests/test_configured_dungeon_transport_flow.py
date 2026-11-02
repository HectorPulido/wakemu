"""Incremental real internal-transport consumption from admitted/result fixtures.

Outer admission, chosen branch and arrival at the native source are explicit
premises. Native source authorization, SQL frontier checks, travel, hydration,
company, Positions, delivery and final exit are real public consumers. Battle
wins are finished-result fixtures, never claimed as earned combat victories.
"""
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
import json, os, struct, traceback
from psycopg.types.json import Jsonb
import test_configured_dungeon_durable_flow as fixtures
from configured_dungeon_flow_fixture import variants, native_approaches


class InternalTransportFlow(fixtures.CurrentDurableFlow):
    test_all_selected_current_routes_from_finished_results = None
    test_declared_open_scene_keeps_current_encounter_authority = None

    def setUp(self):
        super().setUp()
        self.inventory = json.loads(
            Path(os.environ["WAKFU_MANUAL_TP_CASES"]).read_text()
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb(self.inventory["server_mode"]),),
            )

    def test_native_transport_consumers(self):
        selected = os.environ.get("WAKFU_MANUAL_TP_SELECT", "all").split(",")
        excluded = os.environ.get("WAKFU_MANUAL_TP_EXCLUDE", "").split(",")
        configurations = {
            (r["route"], key): (r, c) for r in self.records for key, c in variants(r)
        }
        for case in self.inventory["cases"]:
            identity = "|".join(
                str(case[k])
                for k in ("route", "variant", "source_id", "destination_id", "phase")
            )
            if identity in excluded:
                continue
            if (
                selected != ["all"]
                and identity not in selected
                and case["kind"] not in selected
                and case["route"] not in selected
            ):
                continue
            with self.subTest(case=identity):
                try:
                    record, config = configurations[case["route"], case["variant"]]
                    result = self.transport_case(record, case, config)
                except Exception as error:
                    self.results.append(
                        dict(
                            case=case,
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

    def test_existing_hero_intent_is_retired_by_next_owned_transport(self):
        if not os.environ.get("WAKFU_MANUAL_TP_OLD_CONSUMER"):
            self.skipTest("Explicit immutable pre-repair consumer source required")
        case = next(
            c
            for c in self.inventory["cases"]
            if c["kind"] == "same_stage"
            and c["minimum_frontier"] == 1
            and not c["unselected_branch"]
        )
        record = next(r for r in self.records if r["route"] == case["route"])
        config = dict(variants(record))[case["variant"]]
        self.results.append(
            self.transport_case(record, case, config, legacy_pending=True)
        )
        self.write_receipt()

    def old_consumer_intent(self, c, case):
        """Create the old pending intent through the actual immutable consumer."""
        from wakfu_server import dungeon_doors
        from wakfu_server.dungeon_transition_delivery import deliver_pending_transitions

        path = Path(os.environ["WAKFU_MANUAL_TP_OLD_CONSUMER"])
        source = path.read_text()
        self.assertNotIn('if member["selected_character_id"] != member["id"]:', source)
        old = ModuleType("wakfu_server.dungeon_doors")
        old.__file__ = str(path)
        old.__package__ = "wakfu_server"
        exec(compile(source, str(path), "exec"), old.__dict__)
        with patch.object(dungeon_doors, "_advance", old._advance):
            self.request(c, case)
        self.deliver(c["owners"], c["positions"], expect_kind="door", retry_first=True)
        with self.store.connection() as db:
            pending = db.execute(
                "SELECT event_id,character_id,status FROM dungeon_transition_outbox WHERE instance_id=%s AND status='pending'",
                (c["instance"],),
            ).fetchall()
        self.assertEqual(len(pending), 1)
        self.assertEqual(
            pending[0]["character_id"], c["everyone"][-1]["character"]["id"]
        )
        # World's pre-action delivery polls only the exact selected worker.
        # The orphan hero intent must not block either owner's next action.
        for owner in c["owners"]:
            actor = self.store.character(owner["account"], owner["character"]["id"])

            def unexpected(_):
                raise AssertionError("Orphan hero intent leaked into owner preflight")

            state = deliver_pending_transitions(
                self.delivery_store,
                owner["account"],
                owner["generation"],
                actor["id"],
                worker_generation=owner["generation"],
                current_location=lambda: {
                    k: actor[k] for k in ("map_id", "instance_id", "x", "y", "z")
                },
                in_fight=lambda: False,
                bootstrap=unexpected,
            )
            self.assertEqual(state["state"], "idle")
        self.place_company(c["owners"], c["positions"], case["approach"])
        return pending[0]["event_id"]

    def admitted_context(self, record, key, config):
        from wakfu_server import (
            dungeon_instances,
            dungeon_runtime_config,
            dungeon_progression,
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
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.combat_terrain import map_geometry

        paid = self.start_required_scene(config, owners, positions)
        return dict(
            owners=owners,
            everyone=everyone,
            ids=ids,
            leader=leader,
            party_id=party_id,
            instance=instance,
            positions=positions,
            company=company_before,
            config=config,
            entry=entry,
            main=main,
            settled=0,
            groups=PersistentGroups(self.store),
            geometry=map_geometry(mid),
            paid=paid,
        )

    def settle_next(self, context):
        from wakfu_server import dungeon_progression, dungeon_branches

        c = context
        mid = c["config"]["topology"]["asset_map_id"]
        order = c["main"][c["settled"]]
        self.place_company(
            c["owners"],
            c["positions"],
            dungeon_branches.selected_room(c["config"]["topology"], order)["anchor"],
        )
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            for member in c["everyone"]:
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
                c["instance"],
                c["party_id"],
                c["leader"]["character"]["id"],
                fight,
                player_team=0,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
            )
            result = dungeon_progression.settle_encounter(
                db, SimpleNamespace(id=fight, phase="finished", winner=0, map_id=mid)
            )
            self.assertTrue(result["victory"])
            self.assertFalse(result["replay"])
        c["settled"] += 1
        return result

    def durable_snapshot(self, c):
        with self.store.connection() as db:
            return dict(
                run=db.execute(
                    "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
                    (c["instance"],),
                ).fetchone(),
                instance=db.execute(
                    "SELECT revision,status FROM dungeon_instances WHERE instance_id=%s",
                    (c["instance"],),
                ).fetchone(),
                characters=db.execute(
                    "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s) ORDER BY id",
                    (c["ids"],),
                ).fetchall(),
                members=db.execute(
                    "SELECT character_id,status,session_generation FROM dungeon_instance_members WHERE instance_id=%s ORDER BY character_id",
                    (c["instance"],),
                ).fetchall(),
                outbox=db.execute(
                    "SELECT * FROM dungeon_transition_outbox WHERE instance_id=%s ORDER BY event_id",
                    (c["instance"],),
                ).fetchall(),
                company=self.company_snapshot(c["leader"]),
            )

    def request(self, c, case):
        from wakfu_server import dungeon_runtime, dungeon_doors, teleporter_approach
        from wakfu_server.movement import Movement

        owner = c["leader"]
        actor = self.store.character(owner["account"], owner["character"]["id"])
        with self.store.connection() as db:
            _, config = dungeon_runtime.configuration_for_instance(db, c["instance"])
            progress = db.execute(
                "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                (c["instance"],),
            ).fetchone()
        return dungeon_doors.advance(
            self.store,
            owner["account"],
            owner["generation"],
            actor["id"],
            struct.pack(">qiBi", case["source_id"], case["destination_id"], 0, 2),
            source_allowed=teleporter_approach.callback(
                Movement(actor), map_id=actor["map_id"], instance_id=c["instance"]
            ),
            room_for_position=lambda mid, x, y, z: dungeon_runtime.room_for_position(
                config, mid, x, y, z, current_room=progress["current_room"]
            ),
            in_fight=lambda _: False,
            topology=config["topology"],
            on_arrival=(
                lambda db, i: dungeon_runtime.ensure_current_room(
                    db, c["groups"], i, c["geometry"]
                )
            )
            if config["topology"].get("branch_routes")
            or config["topology"].get("entry_path_policy")
            else None,
            positions=c["positions"],
        )

    def rejected_unchanged(self, c, case, pattern):
        before = self.durable_snapshot(c)
        with self.assertRaisesRegex(ValueError, pattern):
            self.request(c, case)
        self.assertEqual(self.durable_snapshot(c), before)
        for _, position in c["positions"]._entry_snapshot():
            self.assertFalse(position["dirty"])
            self.assertEqual(
                {k: position["current"][k] for k in position["persisted"]},
                position["persisted"],
            )

    def transport_case(self, record, case, config, *, legacy_pending=False):
        from wakfu_server import generic_transports

        c = self.admitted_context(record, case["variant"], config)
        required = case["minimum_frontier"]
        negative = None
        if case["phase"] == "postboss_completed":
            while c["settled"] < len(c["main"]):
                self.settle_next(c)
        elif required > 1:
            while c["settled"] < required - 2:
                self.settle_next(c)
            self.place_company(c["owners"], c["positions"], case["approach"])
            self.rejected_unchanged(
                c,
                case,
                "no committed victory authorization|no committed checkpoint|explicitly excluded|different selected branch",
            )
            negative = (
                "Original frontier rejects before required finished-result receipt"
            )
            self.settle_next(c)
        # Native same-stage/entry transfer is originally free, so a fabricated
        # locked-before-win expectation would contradict source intent.
        if negative is None:
            source = generic_transports.source(
                config["topology"]["asset_map_id"], case["source_id"]
            )
            allowed = native_approaches(source)
            bad = next(
                tuple(cell)
                for cell in config["topology"]["exploration_geometry"]["cells"]
                if all(type(v) is int for v in cell) and tuple(cell) not in allowed
            )
            self.place_company(c["owners"], c["positions"], bad)
            self.rejected_unchanged(
                c, case, "source is not authorized|explicitly excluded"
            )
            negative = "Original free transport rejects a real floor point outside source approach"
        self.place_company(c["owners"], c["positions"], case["approach"])
        if case["unselected_branch"]:
            self.rejected_unchanged(
                c, case, "different selected branch|explicitly excluded"
            )
            positive = False
            delivered = 0
        else:
            legacy_event = self.old_consumer_intent(c, case) if legacy_pending else None
            before = self.durable_snapshot(c)
            result = self.request(c, case)
            self.assertEqual(set(result["members"]), set(c["ids"]))
            self.assertEqual(
                {key: result[key] for key in ("map_id", "x", "y", "z")},
                case["destination"],
            )
            after = self.durable_snapshot(c)
            self.assertEqual(after["run"], before["run"])
            self.assertEqual(
                after["instance"]["revision"], before["instance"]["revision"] + 1
            )
            self.assertEqual(after["members"], before["members"])
            self.assertEqual(after["company"], before["company"])
            for actor in after["characters"]:
                self.assertEqual(actor["instance_id"], c["instance"])
                self.assertEqual(
                    {k: actor[k] for k in ("map_id", "x", "y", "z")},
                    case["destination"],
                )
            delivered = self.deliver(
                c["owners"], c["positions"], expect_kind="door", retry_first=True
            )
            with self.store.connection() as db:
                pending = db.execute(
                    "SELECT character_id FROM dungeon_transition_outbox WHERE instance_id=%s AND status='pending' ORDER BY character_id",
                    (c["instance"],),
                ).fetchall()
            self.assertEqual(
                pending,
                [],
                "A nonselected hero must not retain an undeliverable transport bootstrap",
            )
            if legacy_event is not None:
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM dungeon_transition_outbox WHERE event_id=%s",
                            (legacy_event,),
                        ).fetchone()["status"],
                        "superseded",
                    )
            for _, position in c["positions"]._entry_snapshot():
                self.assertFalse(position["dirty"])
                for key in ("map_id", "x", "y", "z"):
                    self.assertEqual(position["current"][key], case["destination"][key])
            positive = True
        while c["settled"] < len(c["main"]):
            self.settle_next(c)
        delivered += self.native_exit(
            config, c["entry"], c["instance"], c["owners"], c["positions"]
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                    (c["instance"],),
                ).fetchone()["status"],
                "closed",
            )
            self.assertEqual(
                {
                    r["status"]
                    for r in db.execute(
                        "SELECT status FROM dungeon_instance_members WHERE instance_id=%s",
                        (c["instance"],),
                    ).fetchall()
                },
                {"returned"},
            )
            self.assertEqual(
                {
                    r["instance_id"]
                    for r in db.execute(
                        "SELECT instance_id FROM characters WHERE id=ANY(%s)",
                        (c["ids"],),
                    ).fetchall()
                },
                {0},
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM dungeon_transition_outbox WHERE instance_id=%s AND status='pending'",
                    (c["instance"],),
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(self.company_snapshot(c["leader"]), c["company"])
        for _, position in c["positions"]._entry_snapshot():
            self.assertFalse(position["dirty"])
            self.assertEqual(position["current"]["instance_id"], 0)
        leader = c["leader"]
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
            case=case,
            passed=True,
            negative=negative,
            positive=positive,
            blocked_unselected_branch=case["unselected_branch"],
            existing_hero_intent_recovered=legacy_pending,
            owned_members=3,
            selected_owners=2,
            acknowledged_transitions=delivered,
            company_preserved=True,
            positions_clean=True,
            real_arrival_hydration=positive
            and bool(
                config["topology"].get("branch_routes")
                or config["topology"].get("entry_path_policy")
            ),
            later_creation_and_selection=True,
            fixture_settlements=c["settled"],
        )
