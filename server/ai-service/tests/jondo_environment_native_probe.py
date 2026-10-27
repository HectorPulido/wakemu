"""Opt-in native area components, not original encounter/victory claims.

The trap component uses an explicitly test-owned scene controller after a paid
movement boundary. It qualifies the original consumer, not the unrecovered
original841/10009 publisher or the separate adapted initial842 light scene.
"""
from copy import deepcopy
from random import Random
from functools import wraps
import json
import struct
import uuid


def _damage_diagnostics(operation):
    """Append passive source facts to actual failures without changing behavior."""

    @wraps(operation)
    def run(*args, **kwargs):
        from unittest.mock import patch
        from wakfu_server.combat_ordinary_events import OrdinaryDamageEvents

        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        original = OrdinaryDamageEvents.phase
        original_execute = EffectDispatcher.execute
        selected_effects = []

        def observe_execute(dispatcher, invocation, **options):
            result = original_execute(dispatcher, invocation, **options)
            if invocation.reference in (96020, 97583, 96026):
                effect = dispatcher.effects[str(invocation.reference)]
                selected_effects.append(
                    dict(
                        reference=invocation.reference,
                        invocation=vars(invocation),
                        result=result,
                        definition={
                            key: value
                            for key, value in effect.items()
                            if key
                            not in (
                                "parameters_by_level_spans",
                                "parameter0_by_level_spans",
                            )
                        },
                    )
                )
            return result

        def observe(events, effect, invocation, **fields):
            try:
                return original(events, effect, invocation, **fields)
            except Exception as error:
                fight = events.preview
                details = dict(
                    effect=invocation.reference,
                    family=effect["effect_class"],
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    stateUid=invocation.state_uid,
                    container=invocation.native_retained_container,
                    current=None if fight.current is None else fight.current.id,
                    turn=fight.turn_id,
                    actorIds=list(fight.actors),
                    areaIds=list(getattr(fight, "native_effect_areas", {})),
                    states={
                        str(identity): sorted(_states(actor))
                        for identity, actor in fight.actors.items()
                    },
                )
                raise ValueError(
                    str(error)
                    + "; passive native fixture: "
                    + json.dumps(details, default=str)
                ) from error

        with patch.object(OrdinaryDamageEvents, "phase", observe), patch.object(
            EffectDispatcher, "execute", observe_execute
        ):
            try:
                return operation(*args, **kwargs)
            except Exception as error:
                raise AssertionError(
                    str(error)
                    + "; selected effect receipts: "
                    + json.dumps(selected_effects, default=str)
                ) from error

    return run


def _states(actor):
    return {entry.reference for entry in actor.state_ledger.entries}


def _drain(case):
    for _ in range(64):
        if case.runtime.awaiting_ack is None:
            return
        case.runtime.acknowledge_turn(struct.pack(">i", case.runtime.awaiting_ack))
    raise AssertionError("Native acknowledgment chain exceeded64")


def _player_turn(case):
    for _ in range(32):
        _drain(case)
        if case.fight.current is not None and case.fight.current.id == 7:
            return
        case.advance()
    raise AssertionError("Native timeline did not reach the player")


def _walk(case, accepts):
    for _ in range(24):
        _player_turn(case)
        if accepts(case.fight.actors[7].position):
            return
        path = case.path_to(7, accepts)
        assert path, "No actual native path reaches the component objective"
        if not case.player_move_prefix(7, path):
            case.advance()
            continue
        _drain(case)
        if accepts(case.fight.actors[7].position):
            return
        case.advance()
    raise AssertionError("Paid movement exceeded24 player-turn components")


def _build(*, trap=False):
    from wakfu_server.aptitudes import validate_owned_sheet
    from wakfu_server.builds import EMPTY_EQUIPMENT
    from wakfu_server.combat_actor_snapshot import (
        initialize_fight_snapshots,
        native_actor_catalog,
    )
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
    from wakfu_server.combat_environment_participant_footprints import (
        participant_footprints,
    )
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.health import maximum
    from wakfu_server.monsters import owned_instance
    from wakfu_server.spells import default_deck
    from wakfu_server.wire import proto_field
    from native_supreme_paid_component_runtime import PaidComponentRuntime

    hp = maximum(8, 200)
    aptitudes = proto_field(24, (1 << 64) - 1) + b"".join(
        proto_field(34, proto_field(8, bonus) + proto_field(16, points))
        for bonus, points in ((19, 50), (2, 1), (3, 1))
    )
    raw = dict(
        id=7,
        account_id=3,
        map_id=1134,
        instance_id=0,
        breed=8,
        level=200,
        hp=hp,
        max_hp=hp,
        active_build_index=0,
        x=-8,
        y=-7,
        z=-1,
        builds={
            0: dict(
                sheet=proto_field(24, (1 << 64) - 1).hex(),
                equipment=EMPTY_EQUIPMENT.hex(),
                aptitudes=aptitudes.hex(),
            )
        },
        inventory_items=[],
    )
    validated = validate_owned_sheet(raw, aptitudes)
    character = effective_character(raw)
    resources = combat_resources(character)
    reference, level = (2766, 52) if trap else (2563, 138)
    monster = owned_instance(
        reference, level, -7, map_id=1134, instance_id=0, x=-4, y=-7, z=-1, team=1
    )
    catalog = native_actor_catalog()
    arena = local_arena(
        1134,
        1,
        (-8, -7, -1),
        (-4, -7, -1),
        relocate_monsters=False,
        compact=True,
        variation_seed=17,
        size_range=(7, 7),
        member_radii=(catalog["npc_profiles"][str(reference)]["physical_radius"],),
        player_radius=catalog["default_actor_radius"],
    )
    arena = prepare_encounter_scene(character, [monster], arena)
    anchor = None
    if trap:
        from wakfu_server.combat_obstacle_condition import footprint

        excluded = set(footprint((-8, -7, -1), catalog["default_actor_radius"]))
        excluded.update(
            footprint(
                (-4, -7, -1), catalog["npc_profiles"][str(reference)]["physical_radius"]
            )
        )
        excluded.update(
            tuple(cell[:2]) for cell in arena.get("native_border_cells", ())
        )
        candidates = {
            cell for cell in arena["validated_cells"] if cell[:2] not in excluded
        }
        assert candidates
        anchor = min(
            candidates, key=lambda cell: (abs(cell[0] + 8) + abs(cell[1] + 7), cell)
        )
        arena.update(
            native_initial_glyphs=[
                dict(
                    reference=841,
                    cell=list(anchor),
                    level=0,
                    activation=dict(kind="objective", reference=9001, event_id=10009),
                )
            ],
            native_initial_glyph_policy="wakemu.qa-owned-scene841-v1",
            native_initial_glyph_authority="explicit_test_owned_scene_controller",
            native_initial_glyph_source_url="wakemu:qa-paid-movement-objective",
            native_environment_participant_footprints=participant_footprints(
                character, [monster], catalog=catalog
            ),
        )
    characters, monsters = {7: character}, {-7: monster}
    decks = {7: default_deck(character)}
    fight, _ = create_placement(
        character,
        [monster],
        arena,
        fight_id=1,
        player_ap=resources["ap"],
        player_mp=resources["mp"],
        player_wp=resources["wp"],
        player_initiative=resources["initiative"],
        terrain_effect_id=arena.get("terrain_effect_id", 46),
        terrain_instance_id=300 if trap else -300,
    )
    initialize_fight_snapshots(
        fight,
        characters=characters,
        monsters=monsters,
        wp_resources={
            7: (resources["wp"], resources["wp"]),
            -7: (monster["wp"], monster["wp"]),
        },
        running_effects={identity: () for identity in fight.actors},
        initial_effect_uid=1,
    )
    fight.ready(character["account_id"])
    fight, packets = prepare_server_initialization(
        character,
        monsters,
        fight,
        character["account_id"],
        decks[7],
        action_id=1,
        rng=Random(17),
        fight_start=True,
        player_characters=characters,
        deck_blobs=decks,
    )
    case = PaidComponentRuntime(
        fight, characters, monsters, decks, map_id=1134, seed=17
    )
    case.runtime.tactical_encounter_id = uuid.uuid4().hex
    case.runtime.turn_started(arm_deadline=False)
    return case, dict(
        aptitudes=validated,
        nativeResources=resources,
        nativeMaximumHP=hp,
        readyPackets=len(packets),
        sourceArenaMap=1134,
        trapAnchor=anchor,
        noCombatStateOrStatAssignments=True,
    )


@_damage_diagnostics
def emiw_component():
    """Observe genuine553 start/1978 and original close/outside end consequences."""
    case, premise = _build()
    # Protection is earned by2190's actual first boss-start callback; it is
    # not one of the descriptor's initial triples and must never be assigned.
    for _ in range(8):
        if 2023 in _states(case.fight.actors[-7]):
            break
        case.advance()
    assert 2023 in _states(
        case.fight.actors[-7]
    ), "Native first boss start did not create2023"
    assert (case.fight.actors[7].team, case.fight.actors[-7].team) == (1, 0)
    border = {tuple(cell) for cell in case.fight.native_border_cells}
    assert any(
        row["reference"] == 553 for row in case.fight.native_effect_areas.values()
    )
    observations = []
    original_end = case.runtime.turn_end_provider

    def observe_end(phase, **kwargs):
        candidate, packets = original_end(phase, **kwargs)
        if kwargs["actor_id"] == 7:
            observations.append(
                dict(
                    turnId=phase.turn_id,
                    position=list(phase.actors[7].position),
                    beforeMark=1978 in _states(phase.actors[7]),
                    protectedAfterOriginalEnd=2023 in _states(candidate.actors[-7]),
                    statesBefore={
                        str(identity): sorted(_states(actor))
                        for identity, actor in phase.actors.items()
                    },
                    statesAfter={
                        str(identity): sorted(_states(actor))
                        for identity, actor in candidate.actors.items()
                    },
                    bossPosition=list(candidate.actors[-7].position),
                    events=deepcopy(candidate.events[len(phase.events) :]),
                )
            )
        return candidate, packets

    case.runtime.turn_end_provider = observe_end
    boss_position = case.fight.actors[-7].position
    distance = lambda cell: abs(cell[0] - boss_position[0]) + abs(
        cell[1] - boss_position[1]
    )
    _walk(case, lambda cell: cell in border and 3 <= distance(cell) <= 6)
    # End on real553 and return to the actual owned10000 start boundary.
    if 1978 not in _states(case.fight.actors[7]):
        case.advance()
        _player_turn(case)
    assert 1978 in _states(case.fight.actors[7]), "Real553 start did not earn1978"
    assert distance(case.fight.actors[7].position) > 2
    case.advance()
    assert (
        observations[-1]["beforeMark"] and observations[-1]["protectedAfterOriginalEnd"]
    )
    outside = deepcopy(observations[-1])
    _player_turn(case)
    assert 1978 in _states(
        case.fight.actors[7]
    ), "Second real553 start did not earn1978"
    path = case.path_to(7, lambda cell: 0 < distance(cell) <= 2)
    assert (
        path and len(path) <= case.fight.actors[7].mp
    ), "No single paid approach reaches circle2"
    assert case.player_move_prefix(7, path)
    _drain(case)
    assert distance(case.fight.actors[7].position) <= 2
    case.advance()
    assert (
        observations[-1]["beforeMark"]
        and not observations[-1]["protectedAfterOriginalEnd"]
    ), json.dumps(dict(observations=observations, payments=case.payments), default=str)
    close = deepcopy(observations[-1])
    assert 2023 in _states(case.fight.actors[-7]), "Native boss start did not renew2023"
    return dict(
        passed=True,
        scope="Actual Ready/native553/paid movement/end callbacks; not solo victory",
        fixture=premise,
        outside=outside,
        close=close,
        bossRenewed=True,
        payments=deepcopy(case.payments),
    )


def trap_consumer_component():
    """Real841→147092→842, with a disclosed test-owned scene objective producer."""
    from wakfu_server.combat_scene_area_activation import (
        OwnedSceneEventReceipt,
        activate_declared_scene_traps,
    )
    from wakfu_server.combat_server_spell import server_runtime
    from wakfu_server.combat_effect_area_targets import area_targets
    from wakfu_server.combat_state_managers import registered_area_pv

    case, premise = _build(trap=True)
    _walk(case, lambda cell: tuple(cell) == tuple(premise["trapAnchor"]))
    movements = [
        event
        for event in case.fight.events
        if event["kind"] == "movement" and event["actor_id"] == 7
    ]
    assert (
        movements and movements[-1]["cost"] > 0
    ), "The fixture objective requires a real paid action"
    row = next(
        row
        for row in case.fight.native_effect_areas.values()
        if row["reference"] == 841
    )
    uid = row["uid"]
    assert "effect_uid" not in row and row["remaining_activations"] == 1
    receipt = OwnedSceneEventReceipt(
        case.fight.id,
        7,
        case.fight.turn_id,
        case.fight.sequence,
        movements[-1]["sequence"],
        "objective",
        9001,
        "wakemu.qa-owned-scene841-v1",
        "explicit_test_owned_scene_controller",
    )
    case.fight.native_scene_event_receipts = {receipt.source_uid: receipt}
    factory, _ = server_runtime(
        case.characters[7],
        case.monsters,
        case.decks[7],
        action_id=case.runtime.action_id + 1,
        critical=False,
        rng=case.rng,
        player_characters=case.characters,
        deck_blobs=case.decks,
    )
    dispatcher, packets = factory(
        case.fight, {"native_retained_container": {"present": False}}
    )
    with case.fight.effect_resolution():
        outcomes = activate_declared_scene_traps(dispatcher, 7, receipt)
    created = [
        area
        for area in case.fight.native_effect_areas.values()
        if area["reference"] == 842 and area["owner_id"] == uid
    ]
    assert outcomes and len(created) == 1, "Original147092 did not create one owned842"
    child = created[0]
    assert child["effect_reference"] == 147092 and child["effect_class"] == 315
    assert len(child["native_cells_xy"]) == 25
    assert (
        uid not in case.fight.native_effect_areas
    ), "Finite841 did not retire from actual Qs"
    assert any(target.id == child["uid"] for target in area_targets(case.fight))
    owner_retained = registered_area_pv(case.fight, uid) is not None
    try:
        assert activate_declared_scene_traps(dispatcher, 7, receipt) == ()
        replay_guard = "retired_original_area"
    except ValueError:
        assert case.fight.sequence != receipt.sequence
        replay_guard = "stale_completed_boundary"
    assert (
        len(
            [
                area
                for area in case.fight.native_effect_areas.values()
                if area["reference"] == 842 and area["owner_id"] == uid
            ]
        )
        == 1
    )
    return dict(
        passed=True,
        scope="Original native consumer; original10009 publisher unrecovered",
        testOwnedProducer="Declared objective after actual paid movement",
        fixture=premise,
        original841=uid,
        created842=child["uid"],
        nativeOwnerRetained=owner_retained,
        nativeChildOwner=child["owner_id"],
        nativeChildAreaTarget=True,
        native315Effect=child["effect_uid"],
        packets=len(packets),
        replayGuard=replay_guard,
        payments=deepcopy(case.payments),
    )
