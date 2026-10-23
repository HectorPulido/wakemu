"""Complete the native integer-80-percent handoff from a retained fight."""
import json
from pathlib import Path
import struct


def continue_handoff(
    checkpoint, output, *, maximum_boundaries=16, within_admitted_component=False
):
    from test_ombrage_native_paid_clock import back_path
    from wakfu_server.combat_characteristic_percentage import characteristic_percentage
    from wakfu_server.combat_ordinary_authority import native_facing
    from wakfu_server.combat_los import authoritative_visible
    from wakfu_server.combat_obstacle_condition import footprint

    runtime = checkpoint["runtime"]
    root = Path(__file__).resolve().parents[2]
    if within_admitted_component:
        assert checkpoint.get("admission_component_active") is True
    else:
        verifier = checkpoint.get("loaded_implementation_verifier")
        assert callable(
            verifier
        ), "Continuation requires the original pre-admission loaded-code attestation"
        checkpoint["receipt"]["loaded_implementation_attestation"] = verifier()
    assert type(maximum_boundaries) is int and 1 <= maximum_boundaries <= 16
    characters, monsters, decks = (
        checkpoint[key] for key in ("characters", "monsters", "decks")
    )
    common, stats = checkpoint["common"], checkpoint["stats"]
    first = next(iter(characters))
    source = json.loads(
        (
            root
            / ".runtime/parallel-readiness-20261021/ombrage-first-grade-four-directions-exact-source.json"
        ).read_text()
    )
    native_leaves = {
        int(key): int(row["parameters"][0])
        for key, row in source["effects"].items()
        if row["effect_class"] == 315
    }
    # The exact source receipt uses its own record representation. Preserve it
    # alongside actual area rows; qualify each direction without changing PK.
    result = dict(
        status="pending",
        boundaries=[],
        casts=[],
        movements=[],
        source=source,
        original_runtime_pins_preserved=True,
        verification_scope="same_admitted_component"
        if within_admitted_component
        else "original_loaded_implementation_token",
    )

    def facts(fight):
        boss = fight.actors[-200]
        return dict(
            turn=fight.turn_id,
            table=fight.native_table_turn,
            current=None if fight.current is None else fight.current.id,
            hp=boss.hp,
            maximum=boss.max_hp,
            native_percentage=characteristic_percentage(boss.hp, boss.max_hp),
            states=[(row.reference, row.level) for row in boss.state_ledger.entries],
            direction=boss.direction,
            gate_present=any(
                row.get("target_id") == -200 and row.get("generic_effect") == 266503
                for row in fight.native_retained_records.values()
            ),
            areas=[
                dict(row)
                for row in fight.native_effect_areas.values()
                if row.get("owner_id") == -200
            ],
        )

    def move(identity, path):
        if not path:
            return
        actor = runtime.fight.actors[identity]
        before = dict(position=actor.position, ap=actor.ap, mp=actor.mp)
        checkpoint["apply_client"](
            runtime,
            actor.owner_id,
            struct.pack(">q", identity)
            + b"".join(struct.pack(">iih", *cell) for cell in path),
            lambda value: stats(value, runtime.fight),
            runtime_stats_serializer=stats,
            area_provider=lambda candidate, **kw: checkpoint["prepare_area_movement"](
                characters[first], monsters, candidate, decks[first], **common, **kw
            ),
        )
        actor = runtime.fight.actors[identity]
        result["movements"].append(
            dict(
                actor=identity,
                before=before,
                after=dict(position=actor.position, ap=actor.ap, mp=actor.mp),
            )
        )

    def prepare(identity, reference):
        fight = runtime.fight
        return checkpoint["prepare_server_spell"](
            struct.pack(
                ">qqiih",
                identity,
                (identity << 32) | reference,
                *fight.actors[-200].position
            ),
            characters[identity],
            monsters,
            fight,
            characters[identity]["account_id"],
            decks[identity],
            action_id=runtime.action_id + 1,
            critical=None,
            **common,
            line_of_sight=lambda origin, target, phase: authoritative_visible(
                1229,
                origin,
                target,
                phase,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in phase.actors.values()
                    if actor.hp > 0
                },
            )
        )

    try:
        assert (
            characteristic_percentage(
                runtime.fight.actors[-200].hp, runtime.fight.actors[-200].max_hp
            )
            == 80
        )
        for _ in range(maximum_boundaries):
            for _ in range(32):
                if runtime.awaiting_ack is None:
                    break
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            else:
                raise AssertionError("Native ACK chain exhausted")
            fight = runtime.fight
            row = facts(fight)
            result["boundaries"].append(row)
            states = dict(row["states"])
            if {5654, 5663} <= states.keys() and not {5650, 5657} & states.keys():
                result["phase_transition_observed"] = True
                if {1349, 1357} <= {area["reference"] for area in row["areas"]}:
                    assert all(
                        native_leaves.get(area["effect_reference"]) == area["reference"]
                        for area in row["areas"]
                        if area["reference"] in (1349, 1357)
                    )
                    result[
                        "status"
                    ] = "native_integer_eighty_back_handoff_and_owned_sun_shadow_observed"
                    return result
            if fight.phase != "active" or fight.current is None:
                raise AssertionError("Native fight ended before the phase handoff")
            identity = fight.current.id
            if row["gate_present"] and identity in characters and not result["casts"]:
                authority = checkpoint["planning_authority"]
                already_stabilized = 11 in authority.properties(
                    fight, fight.actors[-200]
                )
                blocked_stabilization = 3495 in states and not already_stabilized
                if blocked_stabilization or fight.actors[identity].ap < (
                    4 if already_stabilized else 6
                ):
                    result.setdefault("deferred_owners", []).append(
                        dict(
                            actor=identity,
                            reason="native3495_blocks_stabilization"
                            if blocked_stabilization
                            else "insufficient_native_AP",
                        )
                    )
                    checkpoint["advance_actual_turn"](runtime)
                    continue

                def can_reach_back(cell, approach):
                    return (
                        back_path(
                            fight,
                            identity,
                            require_back=True,
                            maximum_range=3,
                            require_linear=True,
                            origin=cell,
                            movement_prefix=approach,
                        )
                        is not None
                    )

                path = (
                    back_path(
                        fight,
                        identity,
                        require_back=True,
                        maximum_range=3,
                        require_linear=True,
                    )
                    if already_stabilized
                    else back_path(
                        fight,
                        identity,
                        require_back=False,
                        maximum_range=3,
                        require_linear=True,
                        require_los=True,
                        actor_authority=authority,
                        goal_predicate=can_reach_back,
                    )
                )
                if path is not None:
                    move(identity, path)
                    if not already_stabilized:
                        transaction = prepare(identity, 4790)
                        before = facts(runtime.fight)
                        checkpoint["commit_spell_transaction"](
                            runtime, transaction, stats_serializer=stats
                        )
                        assert 11 in authority.properties(
                            runtime.fight, runtime.fight.actors[-200]
                        )
                        result["casts"].append(
                            dict(
                                actor=identity,
                                reference=4790,
                                costs=transaction.plan["costs"],
                                before=before,
                                after=facts(runtime.fight),
                            )
                        )
                    path = back_path(
                        runtime.fight,
                        identity,
                        require_back=True,
                        maximum_range=3,
                        require_linear=True,
                    )
                    assert path is not None
                    move(identity, path)
                    assert (
                        native_facing(
                            runtime.fight.actors[identity], runtime.fight.actors[-200]
                        )
                        == "BACK"
                    )
                    transaction = prepare(identity, 4781)
                    before = facts(runtime.fight)
                    checkpoint["commit_spell_transaction"](
                        runtime, transaction, stats_serializer=stats
                    )
                    after = facts(runtime.fight)
                    result["casts"].append(
                        dict(
                            actor=identity,
                            reference=4781,
                            costs=transaction.plan["costs"],
                            before=before,
                            after=after,
                        )
                    )
                    assert not after[
                        "gate_present"
                    ], "Paid stabilized BACK did not remove original266503"
            checkpoint["advance_actual_turn"](runtime)
        raise AssertionError("Bounded native phase handoff did not finish")
    except Exception as error:
        result.update(
            status="failed", error_type=type(error).__name__, error=str(error)
        )
        raise
    finally:
        result["last"] = facts(runtime.fight)
        checkpoint["last_handoff_result"] = result
        Path(output).write_text(json.dumps(result, indent=2, default=str) + "\n")
