"""Explicit admitted-room premises for the native constructor/Ready census.

No victory or combat phase is fabricated. Final-room progress, selected route
and starting position are fixture inputs; public group, paid scene, publication,
placement and Ready consumers are the behavior under test.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import struct


def project(configuration, variant):
    from wakfu_server import (
        dungeon_gate_presentation,
        dungeon_entry_paths,
        dungeon_rotation,
    )

    config = dungeon_gate_presentation.project_configuration(
        configuration, validated_pin=True
    )
    kind, _, value = variant.partition(":")
    if kind == "entry":
        return dungeon_entry_paths.project_configuration(config, value)
    if kind == "rotation":
        return dungeon_rotation.project(config, int(value))
    if kind == "branch":
        config = deepcopy(config)
        config["topology"]["selected_branch"] = value
    return config


def admitted_run(test, db, case, config, owners, party_id):
    from wakfu_server import dungeon_runtime_config, dungeon_progression

    route = case["contexts"][0]["entry"]
    party = db.execute(
        "SELECT leader_id,revision FROM player_parties WHERE id=%s", (party_id,)
    ).fetchone()
    instance = db.execute(
        "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,"
        "entry_map_id,entry_object_id,entry_destination_id,start_map_id,context_route_key,context_policy_version) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING instance_id",
        (
            party_id,
            party["revision"],
            party["leader_id"],
            route["template_id"],
            route["definition_id"],
            route["entry_map_id"],
            route["entry_object_id"],
            route["destination_id"],
            route["start_map_id"],
            config["route"]["key"],
            config["version"],
        ),
    ).fetchone()["instance_id"]
    for member in owners:
        identity = member["character"]["id"]
        db.execute(
            "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                instance,
                party_id,
                identity,
                member["generation"],
                party["revision"],
                "leader" if identity == party["leader_id"] else "member",
            ),
        )
    plan = dungeon_runtime_config.plan_from_configuration(config)
    run = dungeon_progression.initialize_run(db, instance, party_id, plan)
    variant = case["contexts"][0]["variant"]
    if variant.startswith(("entry:", "branch:")):
        db.execute(
            "UPDATE dungeon_room_runs SET branch_key=%s WHERE instance_id=%s",
            (variant.split(":", 1)[1], instance),
        )
    elif variant.startswith("rotation:"):
        from wakfu_server.dungeon_excavation import digest

        selector = int(variant.split(":", 1)[1])
        db.execute(
            "UPDATE dungeon_room_runs SET branch_key=%s WHERE instance_id=%s",
            (str(selector), instance),
        )
        db.execute(
            "INSERT INTO dungeon_excavation_runs(instance_id,catalog_hash,rule_sha256,selected_source_id,selected_rooms_sha256) "
            "VALUES(%s,%s,%s,%s,%s)",
            (
                instance,
                run["catalog_hash"],
                config["topology"]["excavation_access"]["rule_sha256"],
                selector,
                digest(run["rooms"]),
            ),
        )
    # This is the declared prior-room admission premise, not a battle result.
    db.execute(
        "UPDATE dungeon_room_runs SET current_room=%s WHERE instance_id=%s",
        (case["room"], instance),
    )
    point = case["terrain"]["anchor"]
    for member in owners:
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
            (case["map_id"], instance, *point, member["character"]["id"]),
        )
    from wakfu_server.dungeon_modulation_health import reconcile

    reconcile(test.store, db, [member["character"]["id"] for member in owners])
    return instance


def paid_start(test, store, db, case, owners, instance, groups, geometry):
    from wakfu_server import native_scene_start, dungeon_runtime, dungeon_difficulty
    from wakfu_server.inventory_items import grant

    _, config = dungeon_runtime.configuration_for_instance(db, instance)
    rule = native_scene_start.binding(config["topology"], db=db)
    if rule is None:
        return None
    test.assertEqual(len(owners), 3)
    payer = owners[0]
    identity = payer["character"]["id"]
    db.execute(
        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
        (*rule["approaches"][0], identity),
    )
    actor = store.character(payer["account"], identity, db)
    selection = dungeon_difficulty.selection(db, instance)
    test.assertTrue(selection["competitive"])
    test.assertEqual(selection["competitive_max_level"], rule["competitive_ceiling"])
    item, quantity = native_scene_start._native_source(rule)
    occupied = {
        r["slot"]
        for r in db.execute(
            "SELECT slot FROM inventory_items WHERE character_id=%s AND container=%s",
            (identity, actor["inventory_containers"][0]["uid"]),
        ).fetchall()
    }
    slot = next(i for i in range(100) if i not in occupied)
    grant(
        store,
        payer["account"],
        payer["generation"],
        identity,
        reference=item,
        quantity=quantity,
        container=actor["inventory_containers"][0]["uid"],
        slot=slot,
        allowed_references={item},
        db=db,
    )
    wanted = {
        row["state"]: row["level"] for row in case["paid_start"]["selected_profile"]
    }
    profile = rule["profile"]
    if profile.get("kind") == "configured_native_roster_v1":
        draws = []
    elif "native_state_choices" in profile:
        draws = [
            row["levels"].index(wanted.get(row["id"]))
            for row in profile["native_state_choices"]
        ]
    else:
        draws = [
            sum(
                (wanted[identity] - 1) << n
                for n, identity in enumerate(profile["native_binary_state_ids"])
            )
        ]
    selections = iter(draws)

    def randbelow(bound):
        choice = next(selections)
        test.assertIn(choice, range(bound))
        return choice

    body = struct.pack(">qHH", rule["source_id"], rule["wire_action"], 0)
    with patch.object(
        native_scene_start, "secrets", SimpleNamespace(randbelow=randbelow)
    ):
        started = native_scene_start.start(
            store,
            payer["account"],
            payer["generation"],
            actor,
            body,
            groups=groups,
            geometry=geometry,
            blocked=False,
            is_hero=False,
        )
    test.assertFalse(started["replay"])
    test.assertTrue(started["payment"])
    test.assertEqual(
        {
            row["id"]: row["level"]
            for row in started["profile"].get("native_states", [])
        },
        {identity: level for identity, level in wanted.items() if level is not None},
    )
    repeated = native_scene_start.start(
        store,
        payer["account"],
        payer["generation"],
        actor,
        body,
        groups=groups,
        geometry=geometry,
        blocked=False,
        is_hero=False,
    )
    test.assertTrue(repeated["replay"])
    test.assertEqual(repeated["profile"], started["profile"])
    test.assertEqual(
        db.execute(
            "SELECT COALESCE(sum(quantity),0) n FROM inventory_items WHERE character_id=%s AND reference=%s",
            (identity, item),
        ).fetchone()["n"],
        0,
    )
    return dict(
        profile=started["profile"],
        payment_item=item,
        quantity=quantity,
        policy_id=rule["policy_id"],
        repeat_without_second_payment=True,
    )


def construct_case(test, store, db, case, canonical, owners, party_id):
    from wakfu_server import (
        dungeon_runtime,
        fight_store,
        dungeon_progression,
        combat_terrain,
    )
    from wakfu_server.combat_group_store import PersistentGroups
    from wakfu_server.combat_instance_publication import InstancePublicationTracker
    from wakfu_server.dungeon_hydration import prepare_transition
    from native_dungeon_bound_ready import construct
    from collections import Counter

    config = project(canonical, case["contexts"][0]["variant"])
    instance = admitted_run(test, db, case, config, owners, party_id)
    groups = PersistentGroups(store)
    geometry = combat_terrain.map_geometry(case["map_id"])
    payment = paid_start(test, store, db, case, owners, instance, groups, geometry)
    # Arrival at this encounter is an explicit premise. A paid start may have
    # moved the payer to its actual source approach before consumption.
    for member in owners:
        db.execute(
            "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
            (*case["terrain"]["anchor"], member["character"]["id"]),
        )
    group = dungeon_runtime.ensure_current_room(db, groups, instance, geometry)
    test.assertIsNotNone(
        group, "A real room producer deferred spawn; do not fabricate a roster"
    )
    expected = Counter()
    for row in case["roster"]:
        expected[(row["reference"], row["grade"])] += row["count"]
    actual = Counter((r["ref"], r["level"]) for r in group["members"])
    test.assertEqual(actual, expected, "Native roster/grade differs from manifest")
    publications = []
    for member in owners:
        actor = store.character(member["account"], member["character"]["id"], db)
        event = dict(
            character_id=actor["id"],
            session_generation=member["generation"],
            transition_kind="enter",
            **{
                "destination_" + k: actor[k]
                for k in ("map_id", "instance_id", "x", "y", "z")
            }
        )
        hydration = prepare_transition(
            store, member["account"], member["generation"], actor["id"], event
        )
        tracker = InstancePublicationTracker()
        scope = (
            member["account"],
            member["generation"],
            actor["id"],
            actor["map_id"],
            instance,
        )
        for opcode, body in hydration.packets:
            tracker.after_write(struct.pack(">IH", 6 + len(body), opcode) + body, scope)
        publications.append((tracker, scope))
    first = owners[0]
    fight_id = fight_store.create(
        store, first["account"], first["generation"], first["character"]["id"]
    )
    for member in owners[1:]:
        fight_store.join_participant(
            store,
            db,
            member["account"],
            member["generation"],
            member["character"]["id"],
            fight_id,
            target_character_id=first["character"]["id"],
            team=0,
        )
    dungeon_progression.bind_encounter(
        db, instance, party_id, first["character"]["id"], fight_id, player_team=0
    )
    lease, roster = groups.claim(
        (case["map_id"], instance, group["group_id"]), "ready-census", fight_id
    )
    test.assertEqual(roster, group["members"])
    ready = construct(test, store, owners, group, fight_id, publications)
    fight_store.activate(
        store, first["account"], first["generation"], first["character"]["id"], fight_id
    )
    test.assertEqual(
        db.execute(
            "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
        ).fetchone()["status"],
        "active",
    )
    test.assertEqual(ready.fight.phase, "active")
    test.assertIsNone(ready.fight.winner)
    test.assertEqual(set(ready.characters), {m["character"]["id"] for m in owners})
    references = {}
    for identity, actor in ready.fight.actors.items():
        source = ready.monsters.get(identity) or getattr(
            actor, "native_summon_source", {}
        )
        if source.get("ref") is not None:
            references[identity] = source["ref"]
    counts = Counter(references.values())
    for expectation in case["ready_expectations"]:
        kind = expectation["kind"]
        if kind == "phase_initial_identity":
            test.assertGreater(counts[expectation["initial_reference"]], 0)
        elif kind == "original_spawn":
            actual_count = counts[expectation["reference"]]
            if "count" in expectation:
                test.assertEqual(actual_count, expectation["count"])
            else:
                test.assertGreater(actual_count, 0)
        elif kind == "original_spawns":
            test.assertEqual(
                sum(counts[ref] for ref in expectation["references"]),
                expectation["count"],
            )
            test.assertTrue(all(counts[ref] for ref in expectation["references"]))
        elif kind == "original_constructor_position":
            actors = [
                ready.fight.actors[i]
                for i, ref in references.items()
                if ref == expectation["reference"]
            ]
            test.assertTrue(actors)
            test.assertEqual({a.position for a in actors}, {tuple(expectation["cell"])})
        else:
            raise ValueError("Unsupported manifest Ready expectation: " + kind)
    from wakfu_server.combat_qi_fight import current_registry

    registry = current_registry(ready.fight)
    test.assertIsNotNone(registry)
    return dict(
        instance_id=instance,
        fight_id=fight_id,
        group_id=group["group_id"],
        phase=ready.fight.phase,
        winner=ready.fight.winner,
        actor_count=len(ready.fight.actors),
        initial_npc_count=len(ready.monsters),
        ready_references=dict(counts),
        ready_expectations=case["ready_expectations"],
        paid_start=payment,
        scope="Native constructor and Ready only; admission and prior-room progress are explicit premises",
    )
