"""One original environmental group reaches the ordinary paid terminal boundary.

The battle starts at a declared preterminal fixture: earlier original enemies
are dead and their last original caster has 1 HP and no armor. A native
protected summon stays unchanged until its caster dies through the paid spell.
The player starts on a legal native combat cell.
Only the final native cast is played and paid here. This is not a full dungeon,
AI battle, travel, or complete original-scenario playthrough qualification.
"""
from copy import deepcopy
from pathlib import Path
import random
import struct
import unittest
from unittest.mock import patch

from wakfu_server import builds, fight_store, health_store, heroes
from wakfu_server.achievements import combat_adapter
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_cast import prepare_spell_cast
from wakfu_server.combat_heroes import admit_owned_heroes
from wakfu_server.combat_lifecycle import prepare_finish_shared
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_placement_policy import freeze as freeze_placement
from wakfu_server.combat_qi_fight import move_registered_actor
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_shared import Transition
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_timeline_snapshot import current_wire_turn
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.inventory import bags
from wakfu_server.monster_removal_ecology import finish as finish_world_group
from wakfu_server.objectives import environmental_group_progress as group_progress
from wakfu_server.objectives import environmental_service as events
from wakfu_server.objectives import environmental_storage as event_storage
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.spells import encode_deck
from wakfu_server.wire import proto_field


class EnvironmentalOwnedCombatRouteTests(unittest.TestCase):
    def test_original_spawn_paid_final_hit_normal_shared_finish_hero_rewards_and_reconnect_once(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, account, generation = fixture.store, fixture.account, fixture.generation
        main = fixture.character["id"]
        hero = store.create_character(account, "Env Combat Hero")
        identities = (main, hero["id"])
        deck = encode_deck([4820])
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET breed=9,level=81 WHERE id=ANY(%s)",
                (list(identities),),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=ANY(%s)",
                (XP_BY_LEVEL[81], list(identities)),
            )
            for identity in identities:
                db.execute(
                    "INSERT INTO character_builds VALUES(%s,0,%s,%s,%s,%s) "
                    "ON CONFLICT(character_id,build_index) DO UPDATE SET deck=EXCLUDED.deck,sheet=EXCLUDED.sheet",
                    (
                        identity,
                        proto_field(24, 0xFFFFFFFF),
                        builds.EMPTY_EQUIPMENT,
                        deck,
                        builds.EMPTY_APTITUDES,
                    ),
                )
        fixture.character = health_store.initialize(store, account, generation, main)
        heroes.add(store, account, generation, main, hero["id"])
        self.assertTrue(store.heartbeat(account, generation, ttl=1800))
        fixture.world.leave(main, generation)
        fixture.world.join(generation, object(), fixture.character)
        groups = PersistentGroups(store)
        key = "group-native-1331-327-56601"
        # Import only the previously qualified original profile, retaining its
        # two native groups, pool, thresholds, 600s window and reward bands.
        selected = []
        for fragment in (
            (Path(__file__).parents[1] / "seeds/environmental_group_profiles.sql")
            .read_text()
            .split(";\n")
        ):
            statement = fragment.strip()
            if "E'" + key + "'" in statement and (
                statement.startswith("INSERT INTO environmental_profile_")
                or statement.startswith("INSERT INTO environmental_runtime_profiles")
                or statement.startswith(
                    "UPDATE environmental_runtime_profiles SET sealed=TRUE"
                )
            ):
                selected.append(statement + ";")
        self.assertGreater(len(selected), 10)
        with store.connection() as db:
            for statement in selected:
                db.execute(statement, prepare=False)
            # Original exported anchors stay untouched. As in the qualified
            # public pipeline, an occupied regional schedule opens a fresh
            # window instead of replaying an expired epoch-zero legacy window.
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('fixture-native-paid-group',1,327,56601,'wakemu_round_robin','occupied_sequential_windows',0,"
                "'one original candidate, bounded paid-terminal qualification',%s)",
                ("0" * 64,),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_candidates VALUES('fixture-native-paid-group',1,0,%s,1)",
                (key,),
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true WHERE policy_key='fixture-native-paid-group'"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                (key,),
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET enabled=true WHERE singleton"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
        initial = events.refresh(
            store,
            account,
            generation,
            main,
            location=fixture.location,
            now_ms=fixture.now_ms,
            groups=groups,
        )
        self.assertTrue(
            initial.get("instances"),
            dict(
                inactive_scope=initial.get("inactive_scope"),
                now_ms=fixture.now_ms,
                location=fixture.location,
                character_level=store.character(account, main)["level"],
            ),
        )
        event_id = initial["instances"][0]["instance_id"]
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            self.assertEqual((event["profile_key"], event["state"]), (key, "active"))
            owned = db.execute(
                "SELECT * FROM environmental_owned_groups WHERE instance_id=%s ORDER BY group_id",
                (event_id,),
            ).fetchall()
            self.assertEqual(len(owned), 2)
            group_key = (327, 0, owned[0]["group_id"])
            members = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                group_key,
            ).fetchone()["members"]
            self.assertTrue(2 <= len(members) <= 5)
            self.assertTrue({m["ref"] for m in members} <= {4424, 4425, 4426})
            participant_ids = {
                r["character_id"]
                for r in db.execute(
                    "SELECT character_id FROM environmental_participants WHERE instance_id=%s",
                    (event_id,),
                )
            }
            self.assertEqual(participant_ids, set(identities))
        fight_id = fight_store.create(store, account, generation, main)
        lease, originals = groups.claim(group_key, generation, fight_id)
        character = store.character(account, main)
        resources = combat_resources(character)
        terrain = local_arena(
            327,
            fight_id,
            tuple(character[k] for k in ("x", "y", "z")),
            [(m["x"], m["y"], m["z"]) for m in originals],
            variation_seed=0,
        )
        terrain = freeze_placement(
            store,
            account_id=account,
            generation=generation,
            character_id=main,
            fight_id=fight_id,
            map_id=327,
            instance_id=0,
            selected_arena=terrain,
            seeds={
                0: [tuple(character[k] for k in ("x", "y", "z"))],
                1: [(m["x"], m["y"], m["z"]) for m in originals],
            },
        )
        fight, placement_packets = create_placement(
            character,
            originals,
            terrain,
            fight_id=fight_id,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=terrain["terrain_effect_id"],
            terrain_instance_id=-300,
        )
        self.assertTrue(placement_packets)
        monsters = {m["id"]: m for m in originals}
        initialize_fight_snapshots(
            fight,
            characters={main: character},
            monsters=monsters,
            wp_resources={
                main: (resources["wp"], resources["wp"]),
                **{m["id"]: (m["wp"], m.get("max_wp", m["wp"])) for m in originals},
            },
            running_effects={identity: () for identity in fight.actors},
            initial_effect_uid=1,
        )
        adapter = CombatSessionAdapter(store)
        session = adapter.session(account, generation, character)
        with store.connection() as db:
            admission = admit_owned_heroes(db, store, session, fight)
        fight = admission["fight"]
        self.assertIn(hero["id"], fight.actors)
        adapter.register(session, fight, group_lease=lease)
        adapter.execute(
            session,
            fight_id,
            main,
            lambda candidate, runtime: adapter.ready_transition(
                session, candidate, runtime, True, monsters
            ),
            require_turn=False,
        )
        fight_store.activate(store, account, generation, main, fight_id)

        def shared():
            return adapter.registry.lookup(fight_id)

        def acknowledge():
            for _ in range(8):
                runtime = shared().runtime
                if runtime.awaiting_ack is None:
                    return
                adapter.drain(session, fight_id)
                adapter.acknowledge(
                    session,
                    fight_id,
                    struct.pack(">i", runtime.awaiting_ack),
                    lambda candidate, current, body: current.acknowledge_turn(body),
                )
            self.fail("Native ACK did not reach a stable boundary")

        acknowledge()
        for _ in range(len(fight.actors) + 1):
            current = shared().fight.current
            if current.id == main:
                break
            if current.controlled:
                adapter.execute(
                    session,
                    fight_id,
                    current.id,
                    lambda candidate, runtime: runtime.end_turn(
                        account, current.id, current_wire_turn(candidate)
                    ),
                )
            else:
                adapter.registry.execute_server(
                    fight_id,
                    current.id,
                    lambda candidate, runtime: runtime.end_server_turn(
                        current.id, candidate.turn_id
                    ),
                    expected_sequence=shared().sequence,
                )
            acknowledge()
        self.assertEqual(shared().fight.current.id, main)
        # Declared preterminal setup, never a played/unpaid kill claim. Use the
        # actual HP characteristic mutator so native raw HP, global life and
        # timeline authority stay consistent. No quest fact is injected.
        boundary = shared().fight
        original_ids = {member["id"] for member in originals}
        opposing_team = 1 - boundary.actors[main].team
        protected = {
            actor.id: actor
            for actor in boundary.actors.values()
            if actor.team == opposing_team
            and actor.hp > 0
            and isinstance(actor.effect_minima, dict)
            and actor.effect_minima.get(1, 0) > 0
            and isinstance(getattr(actor, "native_summon_source", None), dict)
        }
        protected_casters = {
            actor.native_summon_source["caster_id"] for actor in protected.values()
        }
        self.assertTrue(protected_casters <= original_ids, protected_casters)
        self.assertLessEqual(
            len(protected_casters),
            1,
            "One paid-final-hit boundary requires a common actual caster",
        )
        # Prior fixture damage does not replay every native death reaction.
        # Keep a protected summon's actual original caster as the last target,
        # so the paid spell executes that original native death callback chain.
        last = (
            next(iter(protected_casters)) if protected_casters else originals[-1]["id"]
        )
        protected_before = {
            identity: (actor.hp, dict(actor.effect_minima), dict(actor.effect_stats))
            for identity, actor in protected.items()
        }
        before_boundary_sequence = boundary.sequence
        hostile_ids = [
            actor.id
            for actor in tuple(boundary.actors.values())
            if actor.team == opposing_team
            and actor.hp > 0
            and actor.id not in protected
        ]
        self.assertIn(last, hostile_ids)
        for identity in hostile_ids:
            target = boundary.actors[identity]
            if target.hp > 0:
                boundary.apply_effect_damage(
                    main, target.id, target.hp - (1 if target.id == last else 0)
                )
        from wakfu_server.combat_stat_handler import _write

        target = boundary.actors[last]
        self.assertIn(97, target.effect_stats)
        _write(boundary, main, target, 97, 0)
        self.assertEqual(
            (boundary.phase, target.hp, target.effect_stats[97]), ("active", 1, 0)
        )
        from wakfu_server.combat_death import newly_registered_death_messages

        prior_deaths = newly_registered_death_messages(
            shared().runtime,
            after_sequence=before_boundary_sequence,
            prepare_delivery=False,
        )
        if prior_deaths:
            shared().runtime.prepare_delivery(tuple(prior_deaths))
        boundary = shared().fight
        boundary_facts = [
            dict(
                id=a.id,
                team=a.team,
                hp=a.hp,
                in_play=boundary._in_play(a),
                armor=None if a.effect_stats is None else a.effect_stats.get(97),
                hp_minimum=None if a.effect_minima is None else a.effect_minima.get(1),
                summon=getattr(a, "native_summon_source", None),
            )
            for a in boundary.actors.values()
        ]
        self.assertEqual(
            {
                a.id
                for a in boundary.actors.values()
                if a.team == opposing_team and boundary._in_play(a)
            },
            {last, *protected},
            boundary_facts,
        )
        self.assertEqual(
            {
                identity: (
                    actor.hp,
                    dict(actor.effect_minima),
                    dict(actor.effect_stats),
                )
                for identity, actor in protected.items()
            },
            protected_before,
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_progress_facts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
        # The declared preterminal boundary may start the caster on any native
        # combat cell. This proves no paid movement or placement-phase route.
        # Preserve real walkability, physical occupancy, QI and native LOS;
        # exactly one spell transaction below executes and pays the final hit.
        characters, decks = adapter.player_sources(boundary)
        rng = random.Random(0)
        _, authority = server_runtime(
            characters[main],
            monsters,
            decks[main],
            action_id=shared().runtime.action_id + 1,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )

        def los(origin, target, state):
            return authoritative_visible(
                327,
                origin,
                target,
                state,
                blocking_footprints={
                    a.id: set(footprint(a.position[:2], a.physical_radius))
                    for a in state.actors.values()
                    if a.hp > 0
                },
            )

        target_cell = boundary.actors[last].position
        request = struct.pack(">qqiih", main, (main << 32) | 4820, *target_cell)
        occupied = set()
        for actor in boundary.actors.values():
            if actor.id != main and actor.hp > 0:
                occupied.update(footprint(actor.position[:2], actor.physical_radius))
        cells = sorted(
            (point for point in boundary.walkable if point[:2] not in occupied),
            key=lambda p: (abs(p[0] - target_cell[0]) + abs(p[1] - target_cell[1]), p),
        )
        admitted = None
        failures = []
        resolved = None
        for point in cells:
            distance = abs(point[0] - target_cell[0]) + abs(point[1] - target_cell[1])
            if (
                resolved is not None
                and not resolved["minimum"] <= distance <= resolved["maximum"]
            ):
                continue
            preview = deepcopy(boundary)
            try:
                move_registered_actor(preview, preview.actors[main], point)
                plan = prepare_spell_cast(
                    request,
                    characters[main],
                    preview,
                    account,
                    decks[main],
                    wp=preview.actors[main].effect_stats[4],
                    line_of_sight=los,
                    conditional_context=lambda req, state: authority.cast_condition(
                        state, req
                    ),
                )
            except ValueError as error:
                diagnostic = getattr(error, "cast_diagnostics", {})
                casting = diagnostic.get("resolved_casting") or {}
                if (
                    type(casting.get("minimum")) is int
                    and type(casting.get("maximum")) is int
                ):
                    resolved = casting
                failures.append(
                    dict(
                        error=str(error),
                        point=point,
                        distance=distance,
                        casting=casting,
                        native=getattr(error, "native_casting_diagnostic", None),
                    )
                )
                continue
            admitted = point, plan
            break
        self.assertIsNotNone(
            admitted,
            dict(
                failures=failures[:5],
                resolved=resolved,
                target=target_cell,
                native_cell_count=len(cells),
                distances=sorted(
                    {
                        abs(p[0] - target_cell[0]) + abs(p[1] - target_cell[1])
                        for p in cells
                    }
                ),
            ),
        )
        point, planned = admitted
        move_registered_actor(boundary, boundary.actors[main], point)
        paid = {}
        before_ap = boundary.actors[main].ap

        def final_cast(candidate, runtime):
            transaction = prepare_server_spell(
                request,
                characters[main],
                monsters,
                candidate,
                account,
                decks[main],
                action_id=runtime.action_id + 1,
                line_of_sight=los,
                critical=None,
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
            )
            paid["costs"] = dict(transaction.plan["costs"])
            packets = commit_spell_transaction(
                runtime, transaction, stats_serializer=runtime.runtime_stats_serializer
            )
            return Transition(runtime.fight, runtime, tuple(packets))

        adapter.execute(session, fight_id, main, final_cast)
        acknowledge()
        terminal = shared().fight
        self.assertEqual(
            (terminal.phase, terminal.winner),
            ("finished", 0),
            dict(
                target=last,
                paid=paid,
                actors=[
                    dict(
                        id=a.id,
                        team=a.team,
                        hp=a.hp,
                        armor=None
                        if a.effect_stats is None
                        else a.effect_stats.get(97),
                        in_play=terminal._in_play(a),
                    )
                    for a in terminal.actors.values()
                ],
                events=terminal.events[-20:],
            ),
        )
        self.assertTrue(all(terminal.actors[m["id"]].hp == 0 for m in originals))
        self.assertGreater(paid["costs"]["ap"], 0)
        self.assertEqual(terminal.actors[main].ap, before_ap - paid["costs"]["ap"])
        self.assertTrue(
            all(terminal.actors[identity].hp > 0 for identity in identities)
        )
        metadata = {
            identity: dict(
                kind="player",
                account_id=account,
                name=characters[identity]["name"],
                breed=characters[identity]["breed"],
                is_male=characters[identity]["sex"] == 0,
            )
            for identity in identities
        }
        metadata.update(
            {m["id"]: dict(kind="monster", ref=m["ref"]) for m in originals}
        )
        # Match normal World finish: Ready-created native summons remain in
        # the report roster even after their owned death/retirement.
        from wakfu_server.combat_terminal_metadata import registered_summon_metadata

        metadata.update(registered_summon_metadata(terminal))
        callbacks = []

        def progression(db, participants, candidate):
            origin = adapter.registry.lookup(candidate.id)
            result = combat_adapter.settle_participants(
                db,
                store,
                candidate,
                participants,
                originals,
                environmental_scene=dict(
                    map_id=origin.map_id,
                    instance_id=origin.instance_id,
                    group_lease=origin.group_lease,
                ),
            )
            callbacks.append(result)
            return result["packets_by_owner"]

        from wakfu_server.storage import combat_reward_context, reward_policy

        def policy(db, member, current):
            return reward_policy.resolve(
                store,
                db,
                account_id=account,
                generation=generation,
                character_id=member["character_id"],
                fight_id=fight_id,
                context=combat_reward_context.build_context(
                    terminal, current, originals
                ),
            ).policy

        def group_finish(db, owner, identity, defeated):
            return finish_world_group(
                store, groups, lease, character_id=identity, defeated=defeated, db=db
            )

        def settle():
            with groups.lock:
                return prepare_finish_shared(
                    store,
                    account,
                    generation,
                    main,
                    shared().runtime,
                    metadata,
                    duration_ms=1000,
                    fight_instance_id=fight_id,
                    policy_resolver=policy,
                    group_settlement=group_finish,
                    progression_resolver=progression,
                    expected_accounts={account},
                    owner_character_ids={account: main},
                )

        # An actual callback failure rolls back the normal group settlement,
        # combat rewards and environmental entitlement in their shared TX.
        original_progression = progression

        def abort_progression(*args):
            original_progression(*args)
            raise RuntimeError("rollback original environmental finish")

        progression = abort_progression
        with self.assertRaisesRegex(
            RuntimeError, "rollback original environmental finish"
        ):
            settle()
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    group_key,
                ).fetchone()["status"],
                "fighting",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
        progression = original_progression
        result_packets = settle()
        self.assertIn(account, result_packets)
        self.assertTrue(callbacks[-1]["environmental_updates"])
        with store.connection() as db:
            completed = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            self.assertEqual(completed["state"], "completed")
            claim_now_ms = (
                max(completed["terminal_at_ms"], int(store.clock() * 1000)) + 100
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    group_key,
                ).fetchone()["status"],
                "defeated",
            )
            for identity in identities:
                participant = db.execute(
                    "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
                    (event_id, identity),
                ).fetchone()
                self.assertEqual(
                    group_progress.counters(db, completed, participant, "monster"),
                    (len(originals), len(originals)),
                )
                components = db.execute(
                    "SELECT c.kind,c.reference,c.quantity FROM environmental_reward_components c "
                    "JOIN environmental_reward_entitlements e USING(entitlement_id) "
                    "WHERE e.instance_id=%s AND e.character_id=%s ORDER BY c.ordinal",
                    (event_id, identity),
                ).fetchall()
                self.assertEqual(
                    [(r["kind"], r["reference"], r["quantity"]) for r in components],
                    [("xp", None, 703662), ("item", 21118, 5)],
                )
            before_claim = {
                identity: store.character(account, identity, db)
                for identity in identities
            }

            def tokens(connection, identity):
                return connection.execute(
                    "SELECT COALESCE(sum(quantity),0)::bigint AS n FROM inventory_items "
                    "WHERE character_id=%s AND reference=21118",
                    (identity,),
                ).fetchone()["n"]

            before_items = {identity: tokens(db, identity) for identity in identities}
        # Claim via the real selected World service. A failed socket write may
        # not erase earned rewards; reconnect replays absolute state once.
        from test_environmental_company import EnvironmentalCompanyPostgresTests

        template, roster = EnvironmentalCompanyPostgresTests().native_template()
        cursor = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster, groups=groups
        )
        with patch.object(
            fixture.world, "send_batch_to", return_value=False
        ) as failed_write:
            self.assertFalse(
                cursor.refresh(
                    store,
                    fixture.world,
                    account,
                    generation,
                    main,
                    location=fixture.location,
                    ready=True,
                    checkpoint=lambda: None,
                    now_ms=claim_now_ms,
                )
            )
            failed_packets = failed_write.call_args.args[2]

        def assert_physical_delivery(packets):
            current = {
                identity: store.character(account, identity) for identity in identities
            }
            physical = [body for op, body in packets if op == 13713 and body[8] == 35]
            self.assertEqual(len(physical), 1)
            self.assertEqual(struct.unpack(">qB", physical[0][:9]), (main, 35))
            self.assertEqual(physical[0][9:], bags(current[main]))
            hero_bodies = [
                body
                for op, body in packets
                if op == 13046
                and struct.unpack_from(">q", body)[0] == hero["id"]
                and body[10] == 10
            ]
            self.assertEqual(len(hero_bodies), 1)
            self.assertIn(bags(current[hero["id"]]), hero_bodies[0][10:])
            self.assertNotIn(12470, [op for op, _ in packets])
            self.assertNotIn(12471, [op for op, _ in packets])

        assert_physical_delivery(failed_packets)
        with store.connection() as db:
            for identity in identities:
                current = store.character(account, identity, db)
                self.assertEqual(current["xp"], before_claim[identity]["xp"] + 703662)
                self.assertEqual(tokens(db, identity), before_items[identity] + 5)
            self.assertTrue(
                db.execute(
                    "SELECT 1 FROM environmental_publication_outbox WHERE acknowledged_at_ms IS NULL"
                ).fetchone()
            )
        fixture.world.leave(main, generation)
        generation = store.begin_session(account, previous_generation=generation)
        store.select_character(account, generation, main)
        fixture.character = store.character(account, main)
        fixture.world.join(generation, object(), fixture.character)
        reconnect = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster, groups=groups
        )
        with patch.object(
            fixture.world, "send_batch_to", wraps=fixture.world.send_batch_to
        ) as native_send:
            self.assertTrue(
                reconnect.refresh(
                    store,
                    fixture.world,
                    account,
                    generation,
                    main,
                    location=fixture.location,
                    ready=True,
                    checkpoint=lambda: None,
                    now_ms=claim_now_ms + 100,
                )
            )
            assert_physical_delivery(native_send.call_args.args[2])
        with store.connection() as db:
            for identity in identities:
                current = store.character(account, identity, db)
                self.assertEqual(current["xp"], before_claim[identity]["xp"] + 703662)
                self.assertEqual(tokens(db, identity), before_items[identity] + 5)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                2,
            )
        reconnect.refresh(
            store,
            fixture.world,
            account,
            generation,
            main,
            location=fixture.location,
            ready=True,
            checkpoint=lambda: None,
            now_ms=claim_now_ms + 200,
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                2,
            )
            for identity in identities:
                self.assertEqual(
                    store.character(account, identity, db)["xp"],
                    before_claim[identity]["xp"] + 703662,
                )
                self.assertEqual(tokens(db, identity), before_items[identity] + 5)
