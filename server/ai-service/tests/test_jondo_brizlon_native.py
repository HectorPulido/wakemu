"""Opt-in native prisoner-chain qualification; never a complete encounter claim."""
from copy import deepcopy
from random import Random
import os
import struct
import unittest
import uuid


def build_fixture(
    reference, *, boss_position=(-4, -6, -1), player_position=(-8, -7, -1)
):
    """Use genuine placement, native resources and Ready on map1134."""
    if reference not in (4251, 4280, 2157):
        raise ValueError("Unsupported prisoner-chain reference")
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.health import maximum
    from wakfu_server.monsters import owned_instance
    from wakfu_server.spells import default_deck
    from native_supreme_paid_component_runtime import PaidComponentRuntime
    from wakfu_server.aptitudes import validate_owned_sheet
    from wakfu_server.builds import EMPTY_EQUIPMENT
    from wakfu_server.wire import proto_field

    position = tuple(player_position)
    hp = maximum(8, 200)
    allocations = ((19, 50), (2, 1), (3, 1))
    aptitude_blob = proto_field(24, (1 << 64) - 1) + b"".join(
        proto_field(34, proto_field(8, bonus) + proto_field(16, points))
        for bonus, points in allocations
    )
    raw_character = dict(
        id=7,
        account_id=3,
        map_id=1134,
        instance_id=0,
        breed=8,
        level=200,
        hp=hp,
        max_hp=hp,
        active_build_index=0,
        x=position[0],
        y=position[1],
        z=position[2],
        builds={
            0: dict(
                sheet=proto_field(24, (1 << 64) - 1).hex(),
                equipment=EMPTY_EQUIPMENT.hex(),
                aptitudes=aptitude_blob.hex(),
            )
        },
        inventory_items=[],
    )
    aptitude_validation = validate_owned_sheet(raw_character, aptitude_blob)
    character = effective_character(raw_character)
    resources = combat_resources(character)
    monster = owned_instance(
        reference,
        23 if reference == 2157 else 98,
        -7,
        map_id=1134,
        x=boss_position[0],
        y=boss_position[1],
        z=boss_position[2],
        team=1,
        instance_id=0,
    )
    characters, monsters = {7: character}, {-7: monster}
    deck = default_deck(character)
    decks = {7: deck}
    arena = local_arena(
        1134, 1, position, boss_position, relocate_monsters=False, variation_seed=17
    )
    fight, _ = create_placement(
        character,
        [monster],
        arena,
        fight_id=1,
        player_ap=resources["ap"],
        player_mp=resources["mp"],
        player_wp=resources["wp"],
        player_initiative=resources["initiative"],
        terrain_effect_id=46,
        terrain_instance_id=-300,
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
    fight, _ = prepare_server_initialization(
        character,
        monsters,
        fight,
        character["account_id"],
        deck,
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
    case.fixture_premise = dict(
        playerLevel=200,
        playerBreed=8,
        aptitudes=aptitude_validation,
        nativeResources=resources,
        naturalMaximumHP=hp,
        noCombatStatAssignments=True,
        inventoryAcquisitionQualified=False,
    )
    case.runtime.turn_started(arm_deadline=False)
    return case


def states(actor):
    return {entry.reference for entry in actor.state_ledger.entries}


def run(*, reference, endpoint="tcp://ai-jondo:8091"):
    """Select the producer over real TCP, then drive paid native player actions."""
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_ai.transport.framed import FramedClient
    from wakfu_ai.transport.endpoint import tcp_address
    from wakfu_server.combat_morph_spellbook import native_morph_profiles

    receipt = dict(
        reference=reference,
        endpoint=endpoint,
        passed=False,
        scope="Native mechanism component on generic map1134; not an official encounter or victory",
        gifts=False,
        actions=[],
        stages=[],
    )
    case = None
    try:
        if "4252" not in native_morph_profiles():
            raise AssertionError(
                "Actual source-qualified native profile4252 is required"
            )
        case = build_fixture(reference)
        receipt["fixturePremise"] = case.fixture_premise
        receipt["stages"].append("genuine_ready")
        _exercise(
            case,
            reference,
            endpoint,
            receipt,
            NativeOracle,
            NativeStats,
            run_prepared_turn,
            FramedClient,
            tcp_address,
        )
        receipt["passed"] = True
    except Exception as error:
        import traceback

        receipt["error"] = dict(
            type=type(error).__name__, message=str(error), trace=traceback.format_exc()
        )
    finally:
        if case is not None:
            receipt["payments"] = deepcopy(case.payments)
            receipt["finalTurn"] = dict(
                phase=case.fight.phase,
                currentId=None if case.fight.current is None else case.fight.current.id,
                turnId=case.fight.turn_id,
            )
            receipt["nativeEvents"] = [
                {
                    key: value
                    for key, value in event.items()
                    if value is None or isinstance(value, (str, int, float, bool))
                }
                for event in case.fight.events
            ]
            receipt["finalActors"] = {
                str(identity): dict(
                    hp=actor.hp,
                    position=list(actor.position),
                    states=sorted(states(actor)),
                )
                for identity, actor in case.fight.actors.items()
            }
    return receipt


def _exercise(
    case, reference, endpoint, receipt, Oracle, Stats, driver, Client, address
):
    from wakfu_server.combat_effective_control import effective_server_controlled
    from wakfu_server.combat_effect_area_geometry import contains_area_cell

    boss, player = -7, 7
    for _ in range(4):
        if case.fight.current.id == boss:
            break
        case.advance()
    assert case.fight.current.id == boss, "Real timeline did not reach the boss"
    assert effective_server_controlled(case.fight, case.fight.current)
    assert 4710 in states(
        case.fight.actors[boss]
    ), "Native Ready did not create protection4710"
    oracle = Oracle(
        case.runtime,
        characters=case.characters,
        monsters=case.monsters,
        decks=case.decks,
        excluded_decks={player: frozenset()},
        viewer_id=player,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    stats = Stats(
        characters=case.characters,
        monsters=case.monsters,
        fight_id=case.fight.id,
        map_id=1134,
    )
    import time
    from wakfu_ai.bridge.jondo_snapshot import build_snapshot

    before_snapshot = build_snapshot(oracle)
    receipt["initialSnapshot"] = before_snapshot
    receipt["carryingProjection"] = {
        str(row["id"]): row.get("isCarrying")
        for row in before_snapshot["board"]["actors"]
    }
    assert all(type(value) is bool for value in receipt["carryingProjection"].values())
    channel = Client(*address(endpoint), timeout=20)
    try:
        # One selected producer is the measured AI component, not a full fight.
        for packets, diagnostic in driver(
            case.runtime,
            oracle,
            stats,
            channel,
            deadline=time.monotonic() + 20,
            max_actions=1,
        ):
            receipt["actions"].append(
                dict(
                    action=diagnostic["action"],
                    strategyId=diagnostic.get("strategyId"),
                    strategyMode=diagnostic.get("strategyMode"),
                    rejected=diagnostic.get("rejectedActions", []),
                    packets=len(packets),
                )
            )
            if diagnostic["action"].get("spellId") in (6011, 6085):
                after_snapshot = build_snapshot(oracle)
                receipt["projectedMechanicAreas"] = after_snapshot["board"][
                    "mechanicAreas"
                ]
                assert any(
                    row["reference"] == 1173 and row["ownerId"] == boss
                    for row in receipt["projectedMechanicAreas"]
                )
    finally:
        channel.close()
    expected = 6011 if reference == 4251 else 6085
    assert any(
        row["action"].get("spellId") == expected for row in receipt["actions"]
    ), receipt["actions"]
    areas = [
        row
        for row in case.fight.native_effect_areas.values()
        if row.get("reference") == 1173 and row.get("owner_id") == boss
    ]
    assert areas, "Selected native producer did not register its owned1173 area"
    receipt["areaUids"] = [row["uid"] for row in areas]
    receipt["stages"].append("selected_boss_producer_committed_owned1173")
    _drain(case)
    for _ in range(4):
        if case.fight.current.id == player:
            break
        case.advance()
    assert case.fight.current.id == player
    # A glyph created under its recipient already satisfies occupancy. Do not
    # force an extra step toward the boss before the original form is earned.
    current = case.fight.actors[player]
    already_inside = any(contains_area_cell(row, current.position) for row in areas)
    receipt["glyphCreatedUnderPlayer"] = already_inside
    if not already_inside:
        path = case.path_to(
            player, lambda cell: any(contains_area_cell(row, cell) for row in areas)
        )
        assert path and len(path) <= current.mp
        assert case.player_move_prefix(player, path)
    assert any(
        contains_area_cell(row, case.fight.actors[player].position) for row in areas
    )
    case.advance()
    assert 4713 in states(
        case.fight.actors[player]
    ), "Native player turn-end10016 did not apply4713"
    receipt["stages"].append("actual1173_occupancy_and_player_turn_end_10016_4713")
    for _ in range(8):
        if (
            getattr(case.fight, "native_morph_spellbooks", {})
            .get(player, {})
            .get("profile_id")
            == 4252
        ):
            break
        case.advance()
    book = case.fight.native_morph_spellbooks[player]
    assert book["profile_id"] == 4252 and 6007 in book["levels"]
    assert case.fight.current.id == player
    assert 4712 in states(case.fight.actors[player])
    receipt["stages"].append("real1001_4712_profile4252")
    _cast_and_restore(case, receipt)


def _drain(case):
    for _ in range(32):
        pending = case.runtime.awaiting_ack
        if pending is None:
            return
        case.runtime.acknowledge_turn(struct.pack(">i", pending))
    raise AssertionError("Native ACK chain exceeded32")


def _cast_and_restore(case, receipt):
    from wakfu_server.combat_server_spell import prepare_server_spell
    from wakfu_server.combat_spell_commit import commit_spell_transaction
    from wakfu_server.combat_los import authoritative_visible
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_cast import resolve_owned_spell_action

    player, boss = 7, -7
    character = case.characters[player]
    actor = case.fight.actors[player]
    before = deepcopy(case.fight)
    receipt["approachActors"] = [
        {
            "id": other.id,
            "hp": other.hp,
            "position": list(other.position),
            "physicalRadius": other.physical_radius,
            "states": sorted(states(other)),
            "registration": {
                key: value
                for key, value in getattr(case.fight, "native_summon_registrations", {})
                .get(other.id, {})
                .items()
                if value is None or isinstance(value, (str, int, float, bool))
            },
            "authority": {
                key: value
                for key, value in getattr(case.fight, "native_summon_registrations", {})
                .get(other.id, {})
                .get("authority", {})
                .items()
                if value is None or isinstance(value, (str, int, float, bool))
            },
        }
        for other in case.fight.actors.values()
    ]
    bad = dict(actor_id=player, spell_uid=(player << 32) | 6007)
    try:
        resolve_owned_spell_action(
            bad, character, case.fight, actor.owner_id, case.decks[player]
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Temporary book incorrectly accepted a normal composite UID"
        )
    assert case.fight.actors[player].ap == before.actors[player].ap
    receipt["stages"].append("foreign_composite_uid_rejected_without_payment")
    receipt["cleanupBranch"] = _cleanup_from_earned(case)
    path = case.cast_path(player, boss, 1, 1, visible_footprint=True)
    assert path is not None
    if path:
        assert case.player_move_prefix(player, path)
    actor = case.fight.actors[player]
    target = case.fight.actors[boss]
    from native_visible_target_fixture import visible_target_cells
    from wakfu_server.combat_server_spell import server_runtime

    _, adapter = server_runtime(
        character,
        case.monsters,
        case.decks[player],
        action_id=case.runtime.action_id + 1,
        critical=False,
        **case.common
    )
    aims = visible_target_cells(
        case.fight,
        adapter.actor_authority,
        case.map_id,
        actor,
        target,
        minimum=1,
        maximum=1,
    )
    assert aims, "No actual adjacent target-footprint endpoint"
    target_cell = aims[0]
    before_resources = dict(ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4])
    transaction = prepare_server_spell(
        struct.pack(">qqiih", player, 6007, *target_cell),
        character,
        case.monsters,
        case.fight,
        actor.owner_id,
        case.decks[player],
        action_id=case.runtime.action_id + 1,
        critical=None,
        line_of_sight=lambda source, destination, candidate: authoritative_visible(
            case.map_id,
            source,
            destination,
            candidate,
            blocking_footprints={
                other.id: footprint(other.position, other.physical_radius)
                for other in candidate.actors.values()
                if other.hp > 0
            },
        ),
        **case.common
    )
    commit_spell_transaction(case.runtime, transaction, stats_serializer=case.stats)
    assert 4710 not in states(case.fight.actors[boss])
    assert 4711 in states(case.fight.actors[boss])
    receipt["playerCast"] = dict(
        rawUid=6007,
        costs=transaction.plan["costs"],
        before=before_resources,
        after=dict(
            ap=case.fight.actors[player].ap,
            mp=case.fight.actors[player].mp,
            wp=case.fight.actors[player].effect_stats[4],
        ),
    )
    receipt["stages"].append("paid6007_removes4710_applies4711")
    from wakfu_server.combat_geometry_snapshot import source_snapshot

    paid_state = source_snapshot(case.fight)
    try:
        commit_spell_transaction(case.runtime, transaction, stats_serializer=case.stats)
    except ValueError:
        pass
    else:
        raise AssertionError("A stale paid transaction was committed twice")
    assert (
        source_snapshot(case.fight) == paid_state
    ), "Rejected retry changed native state"
    receipt["stages"].append("stale_transaction_retry_rejected_without_payment")
    assert receipt["cleanupBranch"]["passed"], receipt["cleanupBranch"]
    receipt["stages"].append("separate_earned_morph_branch_restores_base_book")


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_JONDO_BRIZLON") == "1",
    "Opt-in actual TCP/native mechanism qualification",
)
class JondoBrizlonNativeTests(unittest.TestCase):
    def test_reina_selected_prisoner_chain(self):
        result = run(reference=4251)
        self.assertTrue(result["passed"], result)

    def test_brizgalan_selected_prisoner_chain(self):
        result = run(reference=4280)
        self.assertTrue(result["passed"], result)


def snapshot_probe(*, reference):
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.bridge.jondo_snapshot import build_snapshot

    case = build_fixture(reference)
    for _ in range(4):
        if case.fight.current.id == -7:
            break
        case.advance()
    oracle = NativeOracle(
        case.runtime,
        characters=case.characters,
        monsters=case.monsters,
        decks=case.decks,
        excluded_decks={7: frozenset()},
        viewer_id=7,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    return build_snapshot(oracle)


def native_los_probe(*, reference):
    """Compare advisory and authoritative cast LOS on the same genuine source."""
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.combat_los import authoritative_visible
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_native_los_ray import cast_rays
    from wakfu_server.combat_casting_los import native_casting_los

    case = build_fixture(reference)
    for _ in range(4):
        if case.fight.current.id == -7:
            break
        case.advance()
    fight = case.fight
    boss, player = fight.actors[-7], fight.actors[7]
    oracle = NativeOracle(
        case.runtime,
        characters=case.characters,
        monsters=case.monsters,
        decks=case.decks,
        excluded_decks={7: frozenset()},
        viewer_id=7,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    before = oracle.state_identity(case.runtime)
    footprints = {
        actor.id: footprint(actor.position, actor.physical_radius)
        for actor in fight.actors.values()
        if actor.hp > 0
    }
    rows = []
    for visible, probes in cast_rays(
        1134,
        boss.position,
        player.position,
        source_height=boss.native_los_height,
        target_height=player.native_los_height,
    ):
        rows.append(
            dict(
                staticClear=visible,
                probes=[list(p) for p in sorted(probes)],
                casterIntersections=[
                    list(p) for p in sorted(probes & set(footprints[boss.id]))
                ],
            )
        )
    _, adapter = oracle.factory(fight, case.runtime.action_id + 1, Random(17))
    diagnostic = {}
    native = native_casting_los(
        fight,
        adapter.actor_authority,
        boss.id,
        player.position,
        player,
        diagnostic=diagnostic,
    )
    advisory = authoritative_visible(
        1134, boss.position, player.position, fight, blocking_footprints=footprints
    )
    ignored = dict(footprints)
    ignored[boss.id] = set()
    without_self = authoritative_visible(
        1134, boss.position, player.position, fight, blocking_footprints=ignored
    )
    action = dict(
        type="cast",
        spellId=6011 if reference == 4251 else 6085,
        level=98,
        target=list(player.position),
        targetId=player.id,
    )
    try:
        private, packets, transaction = oracle.preview(
            case.runtime, action, forecast=False
        )
        preview = dict(
            supported=True,
            packets=len(packets),
            areas=[
                row.get("reference")
                for row in private.fight.native_effect_areas.values()
            ],
        )
    except Exception as error:
        preview = dict(supported=False, type=type(error).__name__, message=str(error))
    assert oracle.state_identity(case.runtime) == before
    return dict(
        reference=reference,
        source=list(boss.position),
        target=list(player.position),
        sourceHeight=boss.native_los_height,
        targetHeight=player.native_los_height,
        casterRadius=boss.physical_radius,
        casterSlot=boss.native_obstacle_id,
        advisory=advisory,
        advisoryWithoutSourceBody=without_self,
        nativeCastingLos=native,
        nativeDiagnostic=diagnostic,
        rays=rows,
        nativePreview=preview,
        sourceUnchanged=True,
    )


def _cleanup_from_earned(case):
    """Choose natural expiry on a fork of the exact legitimately earned form."""
    from native_supreme_paid_component_runtime import PaidComponentRuntime
    from wakfu_server.combat_geometry_snapshot import source_snapshot
    from wakfu_server.combat_cast import resolve_owned_spell_action
    from wakfu_server.spells import validate_deck

    original = source_snapshot(case.fight)
    original_rng = case.rng.getstate()
    cloned_runtime = deepcopy(case.runtime)
    branch = PaidComponentRuntime(
        cloned_runtime.fight,
        deepcopy(case.characters),
        deepcopy(case.monsters),
        deepcopy(case.decks),
        map_id=case.map_id,
        seed=17,
    )
    branch.rng.setstate(original_rng)
    for name in (
        "runtime_stats_serializer",
        "stats_serializer",
        "turn_start_provider",
        "turn_end_provider",
        "expiration_runtime_factory",
    ):
        setattr(cloned_runtime, name, getattr(branch.runtime, name))
    branch.runtime = cloned_runtime
    result = dict(
        passed=False,
        scope="Separate natural-expiry branch before paid approach; not post-kiss survival",
    )
    try:
        for count in range(128):
            actor = branch.fight.current
            assert actor is not None and branch.fight.actors[7].hp > 0
            if (
                7 not in getattr(branch.fight, "native_morph_spellbooks", {})
                and actor.id == 7
            ):
                break
            branch.advance()
        else:
            raise AssertionError("Natural form expiry exceeded the owned roster bound")
        character = branch.characters[7]
        active = validate_deck(
            branch.decks[7], character["breed"], character["level"], character=character
        )["active"]
        restored = resolve_owned_spell_action(
            dict(actor_id=7, spell_uid=(7 << 32) | active[0]),
            character,
            branch.fight,
            branch.fight.actors[7].owner_id,
            branch.decks[7],
        )
        assert restored[1] == active[0]
        try:
            resolve_owned_spell_action(
                dict(actor_id=7, spell_uid=6007),
                character,
                branch.fight,
                branch.fight.actors[7].owner_id,
                branch.decks[7],
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expired raw6007 authority remained")
        result.update(
            passed=True,
            boundaries=count,
            restoredBaseSpell=restored[1],
            finalHp=branch.fight.actors[7].hp,
            raw6007Revoked=True,
        )
    except Exception as error:
        result["error"] = dict(type=type(error).__name__, message=str(error))
    assert (
        source_snapshot(case.fight) == original and case.rng.getstate() == original_rng
    )
    result["originalSourceUnchanged"] = True
    return result
