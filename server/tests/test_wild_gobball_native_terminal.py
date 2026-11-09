"""Opt-in Gran Jalató final-room fight with paid PCs and actual Jondo turns.

Two declared, persisted level245 native Iop builds are a pre-fight QA premise.
The five level50..65 NPCs, constructors, costs and combat resources are native.
Recorded instance publication is an offline prerequisite, not a live entrance.
"""
from collections import deque
import json
import os
from pathlib import Path
from random import Random
import struct
import time
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase


ROSTER = (
    (2768, 65, (21, -72, -16)),
    (2765, 50, (21, -74, -16)),
    (2766, 52, (20, -75, -16)),
    (2764, 55, (24, -73, -17)),
    (2764, 55, (24, -72, -16)),
)
BOSS = -7


def build_fixture(store):
    """Extend the existing map712 Ready fixture with persisted owned builds."""
    from native_paid_party_fixture import (
        native_endgame_iop_build,
        persisted_party_character,
    )
    from native_supreme_paid_component_runtime import PaidComponentRuntime
    from wakfu_server.combat_actor_snapshot import (
        initialize_fight_snapshots,
        build_player_snapshot,
    )
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_cosmetic_conditions import (
        initialize_fresh_player_cosmetics,
    )
    from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
    from wakfu_server.combat_join_registration import register_joined_fighter
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_state import Actor
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.dungeon_combat_scaling import _prepare_constructor
    from wakfu_server.monsters import owned_instance

    first, _, deck, resources, gear = persisted_party_character(
        store,
        native_endgame_iop_build(),
        name="granfirst",
        map_id=712,
        position=(21, -70, -16),
    )
    monsters = {
        -7
        - index: owned_instance(
            reference,
            level,
            -7 - index,
            map_id=712,
            instance_id=0,
            x=cell[0],
            y=cell[1],
            z=cell[2],
            team=1,
        )
        for index, (reference, level, cell) in enumerate(ROSTER)
    }
    arena = local_arena(
        712,
        first["id"],
        (first["x"], first["y"], first["z"]),
        [cell for _, _, cell in ROSTER],
        relocate_monsters=False,
        variation_seed=17,
    )
    arena = prepare_encounter_scene(first, list(monsters.values()), arena)
    fight, _ = create_placement(
        first,
        list(monsters.values()),
        arena,
        fight_id=81,
        player_ap=resources["ap"],
        player_mp=resources["mp"],
        player_wp=resources["wp"],
        player_initiative=resources["initiative"],
        terrain_effect_id=46,
        terrain_instance_id=-300,
    )
    characters, decks = {first["id"]: first}, {first["id"]: deck}
    initialize_fight_snapshots(
        fight,
        characters=characters,
        monsters=monsters,
        wp_resources={
            first["id"]: (resources["wp"], resources["wp"]),
            **{identity: (m["wp"], m["wp"]) for identity, m in monsters.items()},
        },
        running_effects={identity: () for identity in fight.actors},
        initial_effect_uid=1,
    )
    occupied = {actor.position for actor in fight.actors.values()}
    position = min(
        fight.placement[0] - occupied,
        key=lambda cell: (abs(cell[0] - 21) + abs(cell[1] + 72), cell),
    )
    second, _, second_deck, values, second_gear = persisted_party_character(
        store,
        native_endgame_iop_build(),
        name="gransecond",
        map_id=712,
        position=position,
    )
    actor = Actor(
        second["id"],
        0,
        position,
        second["hp"],
        values["ap"],
        values["mp"],
        values["initiative"],
        second["level"],
        second["account_id"],
        True,
        max_hp=second["max_hp"],
    )
    initialize_fresh_player_cosmetics(actor, second)
    build_player_snapshot(
        second,
        actor,
        wp_current=values["wp"],
        wp_maximum=values["wp"],
        running_effects=(),
    ).install(actor)
    register_joined_fighter(fight, actor, position)
    characters[second["id"]], decks[second["id"]] = second, second_deck
    for identity, monster in monsters.items():
        _prepare_constructor(fight.actors[identity], monster["ref"])
    for character in characters.values():
        fight.ready(character["account_id"])
    for index, (identity, character) in enumerate(characters.items(), 1):
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            decks[identity],
            action_id=index,
            rng=Random(17),
            fight_start=index == len(characters),
            player_characters=characters,
            deck_blobs=decks,
        )
    case = PaidComponentRuntime(fight, characters, monsters, decks, map_id=712, seed=17)
    case.runtime.turn_started(arm_deadline=False)
    return case, dict(
        build="native_endgame_iop_build",
        level=245,
        gear={first["id"]: gear, second["id"]: second_gear},
        roster=ROSTER,
    )


def path_for(case, identity, target, *, cross_glyph=False, avoid_glyph=False):
    """Plan inputs only; production admission pays movement and area callbacks."""
    from wakfu_server.combat_obstacle_condition import footprint

    fight, actor = case.fight, case.fight.actors[identity]
    glyphs = {
        tuple(cell)
        for area in fight.native_effect_areas.values()
        if area["reference"] == 1603
        for cell in area["native_cells_xy"]
    }
    blocked = set().union(
        *(
            footprint(other.position, other.physical_radius)
            for other in fight.actors.values()
            if other.hp > 0 and other.id != identity
        )
    )
    blocked.update(
        tuple(area["cell"][:2])
        for area in fight.native_effect_areas.values()
        if area["reference"] == 623
    )
    edges = {}
    for start, end in fight.edges:
        edges.setdefault(tuple(start), []).append(tuple(end))
    transformed = identity in getattr(fight, "native_morph_spellbooks", {})
    queue = deque([(actor.position, (), transformed)])
    seen = {(actor.position, transformed)}
    while queue:
        cell, path, touched = queue.popleft()
        if (
            (not cross_glyph or touched)
            and cell[2] == target.position[2]
            and abs(cell[0] - target.position[0]) + abs(cell[1] - target.position[1])
            == 1
        ):
            return path
        for end in sorted(edges.get(cell, ())):
            flag = touched or end[:2] in glyphs
            if (
                end[:2] in blocked
                or (avoid_glyph and end[:2] in glyphs)
                or (end, flag) in seen
            ):
                continue
            seen.add((end, flag))
            queue.append((end, (*path, end), flag))
    return None


def mordisco(case, identity, *, boss_id=BOSS):
    from wakfu_server.combat_los import authoritative_visible
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_server_spell import prepare_server_spell
    from wakfu_server.combat_spell_commit import commit_spell_transaction

    actor, boss = case.fight.actors[identity], case.fight.actors[boss_id]
    before = actor.ap
    book_uid = case.fight.native_morph_spellbooks[identity]["book_uid"]
    transaction = prepare_server_spell(
        struct.pack(">qqiih", identity, 4019, *boss.position),
        case.characters[identity],
        case.monsters,
        case.fight,
        actor.owner_id,
        case.decks[identity],
        action_id=case.runtime.action_id + 1,
        critical=None,
        line_of_sight=lambda source, destination, candidate: authoritative_visible(
            712,
            source,
            destination,
            candidate,
            blocking_footprints={
                other.id: footprint(other.position, other.physical_radius)
                for other in candidate.actors.values()
                if other.hp > 0
            },
        ),
        **case.common,
    )
    commit_spell_transaction(case.runtime, transaction, stats_serializer=case.stats)
    return dict(
        actor=identity,
        book_uid=book_uid,
        before_ap=before,
        after_ap=case.fight.actors[identity].ap,
        costs=transaction.plan["costs"],
    )


def play_native_final(
    assertions, case, receipt, *, boss_id=BOSS, started=None, after_action=None
):
    """Play the existing native witness on an already constructed owned fight.

    Callers supply real hydrated roster identities; no winner, health, native
    state or effect is assigned by this input strategy.
    """
    from tests.jondo_native_support_probe import _drain
    from jondo_native_turn_probe import run

    if started is None:
        started = time.monotonic()
    opener, attacker = tuple(case.characters)
    boss_turns, return_tables = 0, set()
    # Bound by useful progression, not only total wall time.
    last_progress, last_signature = 0, None
    for step in range(100):
        assertions.assertLess(
            time.monotonic() - started, 240, "Bounded full-fight budget exhausted"
        )
        fight = case.fight
        if fight.phase == "finished":
            break
        assertions.assertIsNotNone(
            fight.current, "Native active timeline lost current actor"
        )
        identity, turn = fight.current.id, fight.turn_id
        table = fight.native_timeline_round
        states = {
            state.reference for state in fight.actors[boss_id].state_ledger.entries
        }
        if table not in receipt["tables"] and fight.actors[boss_id].hp > 0:
            tokens = [
                {
                    "uid": area["uid"],
                    "reference": area["reference"],
                    "cell": area["cell"],
                }
                for area in fight.native_effect_areas.values()
                if area["reference"] in (623, 1603)
            ]
            for reference in (623, 1603):
                assertions.assertEqual(
                    sum(token["reference"] == reference for token in tokens), 2
                )
            receipt["tables"][table] = tokens
            if receipt["openings"] and 2324 in states:
                return_tables.add(table)
        receipt["events"].append(
            dict(
                step=step,
                table=table,
                turn=turn,
                current=identity,
                boss_hp=fight.actors[boss_id].hp,
                boss_states=sorted(states),
            )
        )
        signature = (
            tuple(
                (key, actor.hp, actor.position) for key, actor in fight.actors.items()
            ),
            len(receipt["openings"]),
            min(boss_turns, 2),
        )
        if signature != last_signature:
            last_progress, last_signature = step, signature
        assertions.assertLess(
            step - last_progress,
            18,
            "No useful combat progress across two full rosters",
        )
        if identity not in case.characters:
            from wakfu_server.wakia_bridge.wakfu_ai.native.native_actor_source import (
                registered_source,
            )
            from wakfu_server.combat_effective_control import (
                effective_server_controlled,
            )
            from wakfu_server.combat_summon_spellbook import actor_action_book

            assertions.assertTrue(effective_server_controlled(fight, fight.current))
            summon_book = None
            if identity in case.monsters:
                monster = case.monsters[identity]
            else:
                # A native4010 birth is already a registered bje, not
                # an extra ordinary roster entry. The production
                # oracle validates its source and owns its book.
                registration = fight.native_summon_registrations[identity]
                monster = registered_source(fight.current, registration)
                summon_book = actor_action_book(fight.current)
            player_hp_before = {
                key: case.fight.actors[key].hp for key in case.characters
            }

            def factory(**unused):
                viewer = case.fight.actors[opener]
                excluded = {identity: frozenset() for identity in case.characters}
                return (
                    case.runtime,
                    case.characters,
                    case.monsters,
                    case.decks,
                    excluded,
                    SimpleNamespace(pc=viewer, character=case.characters[opener]),
                )

            result = run(
                os.environ["WAKFU_JONDO_ENDPOINT"],
                reference=monster["ref"],
                level=monster["level"],
                max_actions=12,
                fixture_factory=factory,
            )
            receipt["npc_turns"].append(
                dict(
                    actor=identity,
                    table=table,
                    turn=turn,
                    player_hp_before=player_hp_before,
                    player_hp_after={
                        key: case.fight.actors[key].hp for key in case.characters
                    },
                    registered_source=monster if summon_book is not None else None,
                    registered_action_book=summon_book,
                    **result,
                )
            )
            assertions.assertIsNone(result["nativeError"], result)
            assertions.assertIsNone(result["ackError"], result)
            assertions.assertTrue(result["ackAccepted"], result)
            assertions.assertTrue(result["checks"]["snapshotsSourceGuarded"], result)
            assertions.assertTrue(
                case.fight.phase == "finished" or case.fight.turn_id != turn,
                "Actual Jondo driver did not finish its NPC turn; no forced pass",
            )
            boss_turns += identity == boss_id
            continue
        if identity == opener and receipt["openings"]:
            previous = receipt["openings"][-1]
            old_uid = previous["payment"]["book_uid"]
            if previous["turn"] < turn and not any(
                row["removed_book_uid"] == old_uid for row in receipt["restorations"]
            ):
                # State2336 has duration1 and tick_at_turn_end=False.
                # Its eWG child expires at the next owner's START.
                # A new actual glyph may install a different book.
                assertions.assertNotIn(old_uid, case.fight.owned_stat_effects)
                current_book = getattr(case.fight, "native_morph_spellbooks", {}).get(
                    identity
                )
                assertions.assertTrue(
                    current_book is None or current_book["book_uid"] != old_uid
                )
                if current_book is None:
                    assertions.assertNotIn(
                        2336,
                        {
                            s.reference
                            for s in case.fight.actors[identity].state_ledger.entries
                        },
                    )
                receipt["restorations"].append(
                    dict(
                        table=table,
                        turn=turn,
                        removed_book_uid=old_uid,
                        current_book=current_book,
                    )
                )
        if identity == opener and fight.actors[boss_id].hp > 0 and 2324 in states:
            path = path_for(case, identity, fight.actors[boss_id], cross_glyph=True)
            if path is None:
                receipt["events"].append(
                    dict(
                        kind="owned_tactical_wait",
                        actor=identity,
                        table=table,
                        reason="Live occupants block the glyph route; teammate must clear them",
                    )
                )
            if path:
                case.player_move_prefix(identity, path)
                _drain(case)
            actor, boss = case.fight.actors[identity], case.fight.actors[boss_id]
            book = getattr(case.fight, "native_morph_spellbooks", {}).get(identity)
            if (
                book is not None
                and actor.ap >= 4
                and actor.position[2] == boss.position[2]
                and abs(actor.position[0] - boss.position[0])
                + abs(actor.position[1] - boss.position[1])
                == 1
            ):
                assertions.assertEqual(book["profile_id"], 2778)
                assertions.assertIn(4019, book["levels"])
                payment = mordisco(case, identity, boss_id=boss_id)
                if after_action is not None:
                    after_action()
                _drain(case)
                assertions.assertEqual(payment["before_ap"] - payment["after_ap"], 4)
                assertions.assertNotIn(
                    2324,
                    {
                        s.reference
                        for s in case.fight.actors[boss_id].state_ledger.entries
                    },
                )
                receipt["openings"].append(
                    dict(table=table, turn=turn, payment=payment)
                )
        elif (
            (identity == attacker or fight.actors[boss_id].hp <= 0)
            and table >= 2
            and identity not in getattr(case.fight, "native_morph_spellbooks", {})
        ):
            # Preserve two actual boss turns before committing boss damage.
            # Native spell4780 has a four-cast turn limit.
            for _ in range(4):
                actor = case.fight.actors[identity]
                if actor.ap < 2 or case.fight.phase != "active":
                    break
                targets = [
                    a
                    for key, a in case.fight.actors.items()
                    if (
                        key in case.monsters
                        or key in getattr(case.fight, "native_summon_registrations", {})
                    )
                    and a.team != actor.team
                    and a.hp > 0
                    and key != boss_id
                ]
                boss = case.fight.actors[boss_id]
                if (
                    boss.hp > 0
                    and boss_turns >= 2
                    and len(receipt["openings"]) >= 2
                    and 2324 not in {s.reference for s in boss.state_ledger.entries}
                ):
                    # Kill the vulnerable summoner before chasing
                    # its continuously renewed distant entourage.
                    targets = [boss]
                forbidden = [
                    cell
                    for area in case.fight.native_effect_areas.values()
                    if area["reference"] == 1603
                    for cell in area["native_cells_xy"]
                ]
                forbidden.extend(
                    area["cell"]
                    for area in case.fight.native_effect_areas.values()
                    if area["reference"] == 623
                )
                # Native4780 has ordinary range1..3 and its normal
                # casting ray accepts valid differing floor heights.
                paths = [
                    (
                        case.cast_path(
                            identity, target.id, 1, 3, blocked_cells=forbidden
                        ),
                        target.id,
                    )
                    for target in targets
                ]
                paths = [(path, target) for path, target in paths if path is not None]
                if not paths:
                    break
                path, target = min(paths, key=lambda item: (len(item[0]), item[1]))
                if path:
                    case.player_move_prefix(identity, path)
                    _drain(case)
                remaining = case.cast_path(
                    identity, target, 1, 3, blocked_cells=forbidden
                )
                if remaining != ():
                    break
                payment = case.cast(identity, 4780, target)
                _drain(case)
                if target == boss_id:
                    assertions.assertLess(
                        payment["after"]["hp"],
                        payment["before"]["hp"],
                        "Paid ordinary attack did not exploit earned vulnerability",
                    )
        if case.fight.phase == "active" and case.fight.current.id == identity:
            case.advance()  # Only an independently owned player's ordinary end-turn.
    assertions.assertEqual(case.fight.phase, "finished", receipt["events"][-10:])
    assertions.assertEqual(case.fight.winner, case.fight.actors[opener].team)
    assertions.assertGreaterEqual(boss_turns, 2)
    assertions.assertGreaterEqual(len({row["table"] for row in receipt["openings"]}), 2)
    assertions.assertTrue(
        receipt["restorations"],
        "No previous native morph expired at its owned boundary",
    )
    assertions.assertTrue(
        any(
            row["kind"] == "player_cast"
            and row["target"] == boss_id
            and row["after"]["hp"] < row["before"]["hp"]
            for row in case.payments
        ),
        "No paid ordinary damage reached the vulnerable boss",
    )
    assertions.assertTrue(
        return_tables, "Native invulnerability never returned after a paid opening"
    )
    token_sets = [
        tuple(sorted(token["uid"] for token in tokens))
        for tokens in receipt["tables"].values()
    ]
    assertions.assertEqual(len(token_sets), len(set(token_sets)))
    assertions.assertTrue(
        any(
            row["player_hp_after"][key] < hp
            for row in receipt["npc_turns"]
            for key, hp in row["player_hp_before"].items()
        ),
        "No actual NPC offense damaged a normal owned player",
    )
    receipt.update(
        status="PASS_NATIVE_FINAL_FIGHT",
        winner=case.fight.winner,
        boss_turns=boss_turns,
        return_tables=sorted(return_tables),
    )


@unittest.skipUnless(
    os.environ.get("WAKFU_GRAN_NATIVE_TERMINAL") == "1",
    "Explicit actual Jondo/isolated database opt-in required",
)
class WildGobballNativeTerminalTests(PostgresCase):
    def test_paid_repeated_totems_mordisco_real_ai_and_natural_victory(self):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from tests.jondo_native_support_probe import _drain
        from jondo_native_turn_probe import run

        receipt = dict(
            status="RUNNING",
            events=[],
            tables={},
            npc_turns=[],
            openings=[],
            restorations=[],
        )
        case = None
        started = time.monotonic()
        try:
            with original_bootstrap_publication():
                case, receipt["setup"] = build_fixture(self.store)
                play_native_final(self, case, receipt, started=started)
        except Exception as error:
            receipt.update(
                status="FAIL", error=dict(type=type(error).__name__, detail=str(error))
            )
            raise
        finally:
            receipt["seconds"] = time.monotonic() - started
            if case is not None:
                receipt["payments"] = case.payments
                receipt["final"] = dict(
                    phase=case.fight.phase,
                    table=case.fight.native_timeline_round,
                    current=None
                    if case.fight.current is None
                    else case.fight.current.id,
                    committed_start=case.runtime.area_started_turn,
                    phase_deliveries=getattr(
                        case.fight, "native_npc_phase_deliveries", {}
                    ),
                    post_start_deliveries=getattr(
                        case.fight, "native_encounter_post_start_deliveries", {}
                    ),
                    actors=[
                        dict(
                            id=key,
                            hp=a.hp,
                            position=a.position,
                            states=[s.reference for s in a.state_ledger.entries],
                            summon_source=getattr(a, "native_summon_source", None),
                            morph_book=getattr(
                                case.fight, "native_morph_spellbooks", {}
                            ).get(key),
                        )
                        for key, a in case.fight.actors.items()
                    ],
                )
            destination = os.environ.get("WAKFU_GRAN_TERMINAL_RECEIPT")
            if destination:
                destination = Path(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(
                    json.dumps(receipt, indent=2, default=list) + "\n"
                )


if __name__ == "__main__":
    unittest.main()
