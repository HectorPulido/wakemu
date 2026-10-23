"""Inspect a finite set of native jump rays at the retained PC4 endpoint."""
import json
from pathlib import Path


def diagnose(checkpoint, output):
    from wakfu_server.combat_server_spell import server_runtime
    from wakfu_server.combat_casting_los import native_casting_los
    from wakfu_server.combat_geometry_snapshot import source_snapshot

    runtime = checkpoint["runtime"]
    fight = runtime.fight
    actor = fight.actors[4]
    assert (
        fight.native_table_turn,
        fight.turn_id,
        fight.current.id,
        tuple(actor.position),
    ) == (14, 85, 4, (-47, 7, -4))
    verify = checkpoint["authorized_service_transition_verifier"]
    before = source_snapshot(fight)
    rng_before = checkpoint["rng"].getstate()
    verification_before = verify()
    _, adapter = server_runtime(
        checkpoint["characters"][4],
        checkpoint["monsters"],
        checkpoint["decks"][4],
        action_id=runtime.action_id + 1,
        critical=False,
        **checkpoint["common"]
    )
    candidates = [
        ((-44, 5, -4), [(-43, 5, -4), (-43, 4, -4), (-43, 3, -4), (-43, 2, -4)]),
        (
            (-46, 4, -4),
            [(-45, 4, -4), (-44, 4, -4), (-43, 4, -4), (-43, 3, -4), (-43, 2, -4)],
        ),
        (
            (-47, 4, -4),
            [
                (-46, 4, -4),
                (-45, 4, -4),
                (-44, 4, -4),
                (-43, 4, -4),
                (-43, 3, -4),
                (-43, 2, -4),
            ],
        ),
        (
            (-47, 3, -4),
            [(-47, 2, -4), (-46, 2, -4), (-45, 2, -4), (-44, 2, -4), (-43, 2, -4)],
        ),
    ]
    occupied = {tuple(a.position) for a in fight.actors.values() if a.id != 4}
    edges = {(tuple(a), tuple(b)) for a, b in fight.edges}
    walkable = {tuple(c) for c in fight.walkable}
    rows = []
    for landing, path in candidates:
        diagnostic = {}
        clear = native_casting_los(
            fight, adapter.actor_authority, 4, landing, None, diagnostic=diagnostic
        )
        rows.append(
            dict(
                landing=landing,
                native_los=clear,
                diagnostic=diagnostic,
                range_l1=sum(
                    abs(a - b) for a, b in zip(actor.position[:2], landing[:2])
                ),
                post_walk=path,
                walk_steps=len(path),
                invalid_edges=[
                    (a, b)
                    for a, b in zip([landing] + path, path)
                    if (a, b) not in edges
                ],
                invalid_cells=[c for c in [landing] + path if c not in walkable],
                actor_contacts=[c for c in [landing] + path if c in occupied],
            )
        )
    facts = dict(
        scope="READ_ONLY_NATIVE_LOS_AND_STATIC_PATH_NO_PREPARE_NO_PAYMENT",
        table=fight.native_table_turn,
        turn=fight.turn_id,
        identity=4,
        position=actor.position,
        resources=dict(ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4]),
        candidates=rows,
        verification_before=verification_before,
        verification_after=verify(),
        snapshot_equal=source_snapshot(fight) == before,
        rng_equal=checkpoint["rng"].getstate() == rng_before,
    )
    assert facts["snapshot_equal"] and facts["rng_equal"]
    Path(output).write_text(json.dumps(facts, indent=2, default=str) + "\n")
    return facts
