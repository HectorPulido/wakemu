"""Opt-in source-backed earned scenes in disposable PostgreSQL schemas."""
from datetime import datetime, timezone
from random import Random
from types import SimpleNamespace
import struct
import uuid
import time

from postgres_case import PostgresCase


class PrivateSceneDatabase(PostgresCase):
    def runTest(self):
        pass


def build_scene(kind):
    """Use actual account/session/quest, placement, constructor and Ready APIs."""
    from wakfu_server.achievements import storage
    from wakfu_server.progression import level_xp
    from wakfu_server.health import maximum
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.monsters import owned_instance, reference as native_reference
    from wakfu_server.spells import default_deck
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from native_supreme_paid_component_runtime import PaidComponentRuntime

    started = time.monotonic()
    started_cpu = time.process_time()
    timings = {}
    owner = PrivateSceneDatabase()
    owner.setUp()
    timings["disposableSchemaMs"] = (time.monotonic() - started) * 1000
    try:
        if kind == "abomination":
            instant = datetime(2026, 2, 20, 12, tzinfo=timezone.utc)
            owner.store.clock = lambda: instant.timestamp()
        account = owner.store.register("native-scene-owner", "local-password")["id"]
        identity = owner.store.create_character(account, "Native Scene Owner", breed=8)[
            "id"
        ]
        hp = maximum(8, 200)
        with owner.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200,hp=%s,max_hp=%s,map_id=1134,instance_id=0,x=-8,y=-7,z=-1 WHERE id=%s",
                (hp, hp, identity),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(200), identity),
            )
            if kind == "abomination":
                state = storage.load_locked(db, identity)
                state.update(
                    running=[1714],
                    objectives=[],
                    completed=[],
                    tracking=[],
                    recent=[],
                    completion_dates={},
                )
                storage.store(db, identity, state)
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('placement','pve') RETURNING id"
            ).fetchone()["id"]
        generation = owner.store.begin_session(account)
        owner.store.select_character(account, generation, identity)
        with owner.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (fight_id, identity, account, generation),
            )
        character = effective_character(owner.store.character(account, identity))
        resources = combat_resources(character)
        timings["accountSessionCharacterCumulativeMs"] = (
            time.monotonic() - started
        ) * 1000
        reference = 2880 if kind == "abomination" else 5848
        level = native_reference(reference)["min_level"]
        original = owned_instance(
            reference, level, -7, map_id=1134, instance_id=0, x=-4, y=-7, z=-1, team=1
        )
        members = (original,)
        manifest = None
        if kind == "spirit":
            from wakfu_server.combat_encounter_scene_helpers import prepare_scene_roster

            members, manifest = prepare_scene_roster(owner.store, character, members)
            assert (
                manifest is not None
            ), "Source-qualified5852 book/helper scene is required"
        monsters = {m["id"]: m for m in members}
        positions = [(m["x"], m["y"], m["z"]) for m in members]
        arena = local_arena(
            1134,
            identity,
            (-8, -7, -1),
            positions if len(positions) > 1 else positions[0],
            relocate_monsters=False,
            variation_seed=17,
        )
        if manifest is not None:
            from wakfu_server.combat_encounter_scene_helpers import (
                adapt_helper_placement,
            )

            arena["native_encounter_scene_helpers"] = manifest
            adapt_helper_placement(character, members, arena)
        fight, _ = create_placement(
            character,
            list(members),
            arena,
            fight_id=fight_id,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=-300,
        )
        characters = {identity: character}
        decks = {identity: default_deck(character)}
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters=monsters,
            wp_resources={
                identity: (resources["wp"], resources["wp"]),
                **{i: (m["wp"], m["wp"]) for i, m in monsters.items()},
            },
            running_effects={i: () for i in fight.actors},
            initial_effect_uid=1,
        )
        before = dict(hp=fight.actors[identity].hp, maxHp=fight.actors[identity].max_hp)
        timings["placementAndSnapshotsCumulativeMs"] = (
            time.monotonic() - started
        ) * 1000
        with owner.store.connection() as db:
            if kind == "abomination":
                from wakfu_server.combat_abomination_scene import authorize_admission

                admission = authorize_admission(
                    owner.store,
                    db,
                    fight,
                    account_id=account,
                    generation=generation,
                    character_id=identity,
                    monster_references=(2880,),
                )
            else:
                from wakfu_server.combat_encounter_objective_spirit import (
                    authorize_spirit_scene,
                )

                admission = authorize_spirit_scene(
                    owner.store,
                    db,
                    fight,
                    account_id=account,
                    generation=generation,
                    character_id=identity,
                    monster_references=tuple(m["ref"] for m in members),
                )
            assert (
                admission is not None
            ), "Actual fenced source admission did not qualify"
        timings["fencedAdmissionCumulativeMs"] = (time.monotonic() - started) * 1000
        fight.ready(account)
        ready_started = time.monotonic()
        fight, packets = prepare_server_initialization(
            character,
            monsters,
            fight,
            account,
            decks[identity],
            action_id=1,
            rng=Random(17),
            fight_start=True,
            player_characters=characters,
            deck_blobs=decks,
        )
        timings["actualReadyInitializationMs"] = (
            time.monotonic() - ready_started
        ) * 1000
        runtime_started = time.monotonic()
        runtime_cpu = time.process_time()
        case = PaidComponentRuntime(
            fight, characters, monsters, decks, map_id=1134, seed=17
        )
        timings["runtimeConstructionMs"] = (time.monotonic() - runtime_started) * 1000
        timings["runtimeConstructionCpuMs"] = (time.process_time() - runtime_cpu) * 1000
        case.runtime.tactical_encounter_id = uuid.uuid4().hex
        turn_started = time.monotonic()
        turn_cpu = time.process_time()
        case.runtime.turn_started(arm_deadline=False)
        timings["initialTurnStartedMs"] = (time.monotonic() - turn_started) * 1000
        timings["initialTurnStartedCpuMs"] = (time.process_time() - turn_cpu) * 1000
        timings["totalSetupMs"] = (time.monotonic() - started) * 1000
        timings["totalSetupCpuMs"] = (time.process_time() - started_cpu) * 1000
        return SimpleNamespace(
            database=owner,
            case=case,
            identity=identity,
            account=account,
            generation=generation,
            beforeGrant=before,
            afterGrant=dict(
                hp=case.fight.actors[identity].hp,
                maxHp=case.fight.actors[identity].max_hp,
            ),
            readyPackets=len(packets),
            kind=kind,
            setupTimings=timings,
        )
    except BaseException:
        owner.doCleanups()
        raise


def _oracle(scene):
    from wakfu_ai.native.native_oracle import NativeOracle

    c = scene.case
    return NativeOracle(
        c.runtime,
        characters=c.characters,
        monsters=c.monsters,
        decks=c.decks,
        excluded_decks={scene.identity: frozenset()},
        viewer_id=scene.identity,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )


def _drain(case):
    for _ in range(64):
        if case.runtime.awaiting_ack is None:
            return
        case.runtime.acknowledge_turn(struct.pack(">i", case.runtime.awaiting_ack))
    raise AssertionError("Native ACK chain exceeded64")


def _player_turn(scene):
    for _ in range(64):
        if (
            scene.case.fight.current is not None
            and scene.case.fight.current.id == scene.identity
        ):
            return
        _advance_scene(scene)
    raise AssertionError("Native timeline did not reach original player")


def _advance_scene(scene):
    """Use human end input for ordinary NPCs with a real human controller."""
    from wakfu_server.combat_effective_control import effective_input_owner
    from wakfu_server.combat_timeline_snapshot import current_wire_turn

    case = scene.case
    owner = effective_input_owner(case.fight, case.fight.current)
    if owner is None:
        case.advance()
    else:
        case.runtime.end_turn(
            owner, case.fight.current.id, current_wire_turn(case.fight)
        )
        _drain(case)


def abomination_component(endpoint=None):
    """Earn933, pay4121/4124, inspect real207 control, then native unapply.

    NPC turns are passed by the component driver. This is a quest/book/player
    acceptance component, not a Jondo tactic or complete Abomination victory.
    """
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_server.combat_effective_control import (
        effective_input_owner,
        effective_server_controlled,
    )
    from wakfu_server.combat_abomination_scene import cleanup

    scene = build_scene("abomination")
    c = scene.case
    events = []
    try:
        _player_turn(scene)
        o = _oracle(scene)
        stats = NativeStats(
            characters=c.characters,
            monsters=c.monsters,
            fight_id=c.fight.id,
            map_id=1134,
        )
        levels = o.owned_spells(c.fight)
        assert 4121 in levels and 4124 in levels

        def state_ids(actor):
            return {e.reference for e in actor.state_ledger.entries}

        assert 2490 in state_ids(c.fight.actors[-7])
        action = dict(
            type="cast",
            spellId=4121,
            level=levels[4121],
            targetId=-7,
            target=list(c.fight.actors[-7].position),
        )
        packets = o.commit(action, stats_serializer=stats)
        _drain(c)
        assert 2490 not in state_ids(c.fight.actors[-7])
        events.append(
            dict(action=action, packets=len(packets), bossProtectionRemoved=True)
        )
        before = set(c.fight.actors)
        wp = c.fight.actors[scene.identity].effect_stats[4]
        action = dict(
            type="cast",
            spellId=4124,
            level=o.owned_spells(c.fight)[4124],
            targetId=None,
            target=[-7, -7, -1],
        )
        packets = o.commit(action, stats_serializer=stats)
        _drain(c)
        helpers = [
            a
            for i, a in c.fight.actors.items()
            if i not in before
            and (getattr(a, "native_summon_source", None) or {}).get("ref") == 2888
        ]
        assert len(helpers) == 1
        helper = helpers[0]
        assert effective_input_owner(c.fight, helper) == scene.account
        assert not effective_server_controlled(c.fight, helper)
        assert c.fight.actors[scene.identity].effect_stats[4] == wp - 1
        events.append(
            dict(
                action=action,
                packets=len(packets),
                summonId=helper.id,
                reference=2888,
                nativeControllerOwner=scene.account,
                serverControlled=False,
            )
        )
        before_cleanup = dict(
            hp=c.fight.actors[scene.identity].hp,
            maxHp=c.fight.actors[scene.identity].max_hp,
        )
        factory = c.runtime.expiration_runtime_factory(
            action_id=c.runtime.action_id + 1
        )
        out = []
        assert cleanup(c.fight, factory, out)
        assert 4121 not in _oracle(scene).owned_spells(c.fight)
        assert 2492 not in state_ids(c.fight.actors[scene.identity])
        return dict(
            passed=True,
            kind="earned_abomination_native_component",
            nativeActions=events,
            beforeGrant=scene.beforeGrant,
            afterGrant=scene.afterGrant,
            beforeCleanup=before_cleanup,
            afterCleanup=dict(
                hp=c.fight.actors[scene.identity].hp,
                maxHp=c.fight.actors[scene.identity].max_hp,
            ),
            cleanupPackets=len(out),
            bookRestored=True,
            premise="Disposable real quest/session; source seasonal clock20February2026; ordinary initialized map1134; no full encounter victory/Jondo selection claim",
        )
    finally:
        scene.database.doCleanups()


def spirit_ready_and_helper_input_component(endpoint=None):
    """Real scene Ready, earned5852 and one raw human-controlled NPC cast."""
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_effective_control import effective_input_owner
    from wakfu_server.combat_cast_delivery_source import connected_action_source
    from wakfu_server.combat_server_spell import prepare_server_spell
    from wakfu_server.combat_spell_commit import commit_spell_transaction
    from wakfu_ai.bridge.jondo_los import casting_visible
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_encounter_objective_spirit import cleanup_spirit_scene

    scene = build_scene("spirit")
    c = scene.case
    try:
        o = _oracle(scene)
        assert {8485, 8486, 8487, 8488, 8489} <= set(
            o.owned_spells(c.fight, scene.identity)
        )
        helpers = c.fight.native_scene_helper_manifest["source"]["helpers"]
        helper_id = helpers[0]["actor_id"]
        for _ in range(64):
            if c.fight.current is not None and c.fight.current.id == helper_id:
                break
            _advance_scene(scene)
        assert c.fight.current.id == helper_id
        actor = c.fight.actors[helper_id]
        assert effective_input_owner(c.fight, actor) == scene.account
        source, deck = connected_action_source(
            c.fight, c.characters, c.decks, scene.identity, scene.account, helper_id
        )
        attempts = []
        accepted = None
        for ability in native_abilities(helpers[0]["reference"], actor.effective_level)[
            :12
        ]:
            for target_id in (-7, helper_id):
                target = c.fight.actors[target_id]
                body = struct.pack(
                    ">qqiih", helper_id, ability["spell_id"], *target.position
                )
                try:
                    transaction = prepare_server_spell(
                        body,
                        source,
                        c.monsters,
                        c.fight,
                        scene.account,
                        deck,
                        action_id=c.runtime.action_id + 1,
                        critical=False,
                        rng=c.rng,
                        player_characters=c.characters,
                        deck_blobs=c.decks,
                        line_of_sight=lambda start, end, current: casting_visible(
                            1134,
                            start,
                            end,
                            current,
                            blocking_footprints={
                                a.id: footprint(a.position, a.physical_radius)
                                for a in current.actors.values()
                                if a.hp > 0
                            },
                        ),
                    )
                    before_actor = c.fight.actors[helper_id]
                    before = dict(
                        ap=before_actor.ap,
                        mp=before_actor.mp,
                        wp=before_actor.effect_stats[4],
                        bossHp=c.fight.actors[-7].hp,
                    )
                    packets = commit_spell_transaction(
                        c.runtime, transaction, stats_serializer=c.stats
                    )
                    _drain(c)
                    current = c.fight.actors[helper_id]
                    accepted = dict(
                        actorId=helper_id,
                        reference=helpers[0]["reference"],
                        spellId=ability["spell_id"],
                        targetId=target_id,
                        costs=transaction.plan["costs"],
                        packets=len(packets),
                        before=before,
                        after=dict(
                            ap=current.ap,
                            mp=current.mp,
                            wp=current.effect_stats[4],
                            bossHp=c.fight.actors[-7].hp,
                        ),
                        ordinaryNpc=True,
                        registeredSummon=getattr(current, "native_summon_source", None)
                        is not None,
                    )
                    break
                except ValueError as error:
                    attempts.append(
                        dict(
                            spellId=ability["spell_id"],
                            targetId=target_id,
                            error=str(error),
                        )
                    )
            if accepted is not None:
                break
        assert accepted is not None, "No actual raw helper cast accepted: " + repr(
            attempts
        )
        assert not accepted["registeredSummon"]
        before_cleanup = dict(
            hp=c.fight.actors[scene.identity].hp,
            maxHp=c.fight.actors[scene.identity].max_hp,
        )
        factory = c.runtime.expiration_runtime_factory(
            action_id=c.runtime.action_id + 1
        )
        out = []
        assert cleanup_spirit_scene(c.fight, factory, out)
        assert not (
            {8485, 8486, 8487, 8488, 8489}
            & set(_oracle(scene).owned_spells(c.fight, scene.identity))
        )
        return dict(
            passed=True,
            kind="spirit_earned_ready_manual_helper_component",
            beforeGrant=scene.beforeGrant,
            afterGrant=scene.afterGrant,
            beforeCleanup=before_cleanup,
            afterCleanup=dict(
                hp=c.fight.actors[scene.identity].hp,
                maxHp=c.fight.actors[scene.identity].max_hp,
            ),
            acceptedNativeHelperCast=accepted,
            rejectedPreflights=attempts,
            bookRestored=True,
            readyPackets=scene.readyPackets,
            cleanupPackets=len(out),
            premise="Disposable real account/session; explicit source-backed reconstructed map1134 admission/ordinary helpers. No13round/200k outcome or Jondo boss tactic claim.",
        )
    finally:
        scene.database.doCleanups()
