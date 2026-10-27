"""Opt-in real Ready/TCP support components; no scripted support selection."""
from random import Random
from types import SimpleNamespace
from unittest.mock import patch
from copy import deepcopy
import struct
import uuid


def build_fixture(
    reference,
    level,
    *,
    allies=(),
    npc_position=(-4, -7, -1),
    player_position=(-8, -7, -1)
):
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.health import maximum
    from wakfu_server.monsters import owned_instance
    from wakfu_server.spells import default_deck
    from native_supreme_paid_component_runtime import PaidComponentRuntime

    hp = maximum(8, 200)
    character = effective_character(
        dict(
            id=7,
            account_id=3,
            map_id=1134,
            instance_id=0,
            breed=8,
            level=200,
            hp=hp,
            max_hp=hp,
            active_build_index=0,
            x=player_position[0],
            y=player_position[1],
            z=player_position[2],
            builds={},
            inventory_items=[],
        )
    )
    resources = combat_resources(character)
    roster = [(reference, level, npc_position), *allies]
    monsters = {
        -7
        - i: owned_instance(
            ref,
            lvl,
            -7 - i,
            map_id=1134,
            instance_id=0,
            x=pos[0],
            y=pos[1],
            z=pos[2],
            team=1,
        )
        for i, (ref, lvl, pos) in enumerate(roster)
    }
    characters = {7: character}
    decks = {7: default_deck(character)}
    positions = [(m["x"], m["y"], m["z"]) for m in monsters.values()]
    arena = local_arena(
        1134,
        1,
        player_position,
        positions if len(positions) > 1 else positions[0],
        relocate_monsters=False,
        variation_seed=17,
    )
    fight, _ = create_placement(
        character,
        list(monsters.values()),
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
            **{i: (m["wp"], m["wp"]) for i, m in monsters.items()},
        },
        running_effects={i: () for i in fight.actors},
        initial_effect_uid=1,
    )
    fight.ready(character["account_id"])
    fight, _ = prepare_server_initialization(
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
    return case


def _oracle(case):
    from wakfu_ai.native.native_oracle import NativeOracle

    return NativeOracle(
        case.runtime,
        characters=case.characters,
        monsters=case.monsters,
        decks=case.decks,
        excluded_decks={7: frozenset()},
        viewer_id=7,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )


def _drain(case):
    for _ in range(64):
        if case.runtime.awaiting_ack is None:
            return
        case.runtime.acknowledge_turn(struct.pack(">i", case.runtime.awaiting_ack))
    raise AssertionError("Native ACK chain exceeded its fixture bound")


def _facts(case):
    return {
        str(i): dict(
            hp=a.hp,
            maxHp=a.max_hp,
            ap=a.ap,
            mp=a.mp,
            stats=dict(a.effect_stats),
            position=list(a.position),
            team=a.team,
            summonSource=deepcopy(getattr(a, "native_summon_source", None)),
            states=[(e.reference, e.level) for e in a.state_ledger.entries],
        )
        for i, a in case.fight.actors.items()
    }


def _paid_wound(case, target_id, stats):
    """Find one owned real player hit; never assign HP or adopt a forecast."""
    for _ in range(64):
        if case.fight.current.id == 7:
            break
        case.advance()
    assert case.fight.current.id == 7
    oracle = _oracle(case)
    source = oracle.state_identity(case.runtime)
    failures = []
    for spell, level in list(oracle.owned_spells(case.fight).items())[:16]:
        action = dict(
            type="cast",
            spellId=spell,
            level=level,
            targetId=target_id,
            target=list(case.fight.actors[target_id].position),
        )
        try:
            preview, _, _ = oracle.preview(case.runtime, action)
            original = case.fight.actors[target_id].hp
            if not 0 < preview.fight.actors[target_id].hp < original:
                continue
            assert oracle.state_identity(case.runtime) == source
            packets = oracle.commit(action, stats_serializer=stats)
            _drain(case)
            actual = case.fight.actors[target_id].hp
            assert 0 < actual < original
            return dict(
                action=action,
                beforeHP=original,
                afterHP=actual,
                packets=len(packets),
                previewFailures=failures,
            )
        except (ValueError, KeyError) as error:
            assert oracle.state_identity(case.runtime) == source
            failures.append(dict(spell=spell, error=str(error)))
    raise AssertionError(
        "No owned paid player hit wounded the actual ally: " + repr(failures)
    )


def run_component(endpoint, *, kind):
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.native.native_stats import NativeStats
    from jondo_native_turn_probe import run

    recipes = {
        "summon": dict(reference=2819, level=5, allies=()),
        "heal": dict(reference=5022, level=83, allies=((5022, 83, (-5, -7, -1)),)),
        "buff": dict(reference=2766, level=52, allies=((2766, 52, (-6, -6, -1)),)),
    }
    recipe = recipes[kind]
    case = build_fixture(**recipe)
    stats = NativeStats(
        characters=case.characters,
        monsters=case.monsters,
        fight_id=case.fight.id,
        map_id=1134,
    )
    wound = _paid_wound(case, -8, stats) if kind == "heal" else None
    for _ in range(64):
        if case.fight.current.id == -7:
            break
        case.advance()
    assert case.fight.current.id == -7
    before = _facts(case)
    commits = []
    original = NativeOracle.commit

    def observe(oracle, action, **kwargs):
        entry = dict(action=deepcopy(action), before=_facts(case))
        try:
            result = original(oracle, action, **kwargs)
            entry["accepted"] = True
            return result
        except Exception as error:
            entry.update(accepted=False, error=repr(error))
            raise
        finally:
            entry["after"] = _facts(case)
            commits.append(entry)

    def factory(**unused):
        return (
            case.runtime,
            case.characters,
            case.monsters,
            case.decks,
            {7: frozenset()},
            SimpleNamespace(
                pc=case.fight.actors[7],
                character=case.characters[7],
                fixture_setup=dict(
                    kind="natural_ready_support",
                    recipe=recipe,
                    wound=wound,
                    noHpOrStateAssignments=True,
                ),
            ),
        )

    with patch.object(NativeOracle, "commit", observe):
        result = run(
            endpoint,
            reference=recipe["reference"],
            level=recipe["level"],
            max_actions=6,
            fixture_factory=factory,
        )
    after = _facts(case)
    selected = [
        c for c in commits if c.get("accepted") and c["action"].get("type") == "cast"
    ]
    expected = {"summon": 4625, "heal": 638, "buff": 4001}[kind]
    chosen = any(c["action"].get("spellId") == expected for c in selected)
    # Inspect the accepted paid spell boundary, before end-turn expirations.
    expected_commits = [c for c in selected if c["action"].get("spellId") == expected]

    def useful(commit):
        old, new = commit["before"], commit["after"]
        cost = {"summon": 3, "heal": 4, "buff": 3}[kind]
        if old["-7"]["ap"] - new["-7"]["ap"] != cost:
            return False
        if kind == "summon":
            return any(
                (new[i].get("summonSource") or {}).get("ref") == 735
                and new[i]["summonSource"].get("caster_id") == -7
                and new[i]["team"] == 1
                for i in set(new) - set(old)
            )
        if kind == "heal":
            return any(
                row["hp"] > old[i]["hp"]
                for i, row in new.items()
                if i in old and row["team"] == 1
            )
        # Native94 changes water resistance29; native120 changes damage20.
        # The real865 transfer determines the amount and actual recipients.
        target = str(commit["action"].get("targetId"))
        resistance_lost = (
            target in old
            and target in new
            and new[target]["stats"][29] < old[target]["stats"][29]
        )
        allied_damage_gained = any(
            row["stats"][20] > old[i]["stats"][20]
            for i, row in new.items()
            if i in old and row["team"] == 1
        )
        return resistance_lost and allied_damage_gained

    positive = any(useful(c) for c in expected_commits)
    result.update(
        kind="native_support_" + kind,
        componentPassed=chosen and positive and result["passed"],
        selectedExpectedSpell=chosen,
        nativeOutcomePositive=positive,
        nativeCommits=commits,
        before=before,
        after=after,
        paidWound=wound,
        scope="Chosen real TCP/native support component; generic map1134, not an official encounter or victory",
    )
    return result
