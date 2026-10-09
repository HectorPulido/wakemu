#!/usr/bin/env python3
"""Actual owned7349 grant -> form -> ordinary turn/ACK -> native revert."""
import argparse
import json
from pathlib import Path
import random
import struct
from audit_owned_captured324_transaction import run as captured_run
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot


def dragon_branch(runtime, character, monster, deck, stats, los, created_actor_id):
    proof = dict(
        spell=7349,
        passive_not_cast=7337,
        stages=[],
        turns=[],
        full_client_verified=False,
    )
    try:
        for stage in ("normal_to_dragon", "dragon_to_normal"):
            for _ in range(len(runtime.fight.actors) * 4):
                current = runtime.fight.current
                if current.id == character["id"]:
                    grant = grant_record(runtime.fight, character["id"], 7349)
                    if grant is None:
                        raise ValueError(
                            "Actual Ready did not install native7349 grant"
                        )
                    _, adapter = server_runtime(
                        character,
                        {monster["id"]: monster},
                        deck,
                        action_id=runtime.action_id + 1,
                        critical=False,
                        rng=random.Random(17),
                    )
                    search = eligible_cast_targets(
                        runtime.fight,
                        character,
                        deck,
                        grant["uid"],
                        adapter=adapter,
                        line_of_sight=los,
                        maximum_eligible=1,
                    )
                    if search["eligible"]:
                        break
                    proof["turns"].append(
                        dict(actor_id=current.id, casting_search=search)
                    )
                packets = (
                    runtime.end_turn(current.owner_id, current.id, current.turn_count)
                    if current.controlled
                    else runtime.end_server_turn(current.id, runtime.fight.turn_id)
                )
                ack = runtime.awaiting_ack
                if ack is not None:
                    packets += runtime.acknowledge_turn(struct.pack(">i", ack))
                proof["turns"].append(
                    dict(actor_id=current.id, ack=ack, packet_count=len(packets))
                )
            else:
                raise ValueError(
                    "No legal native7349 context after bounded actual turn cycles"
                )
            cell = search["eligible"][0]["target"]
            before = snapshot(runtime.fight)
            states_before = [
                dict(reference=s.reference, level=s.level)
                for s in runtime.fight.actors[character["id"]].state_ledger.entries
            ]
            trace = []
            with combat_diagnostic_scope(
                lambda **event: trace.append(event), limit=8192
            ):
                transaction = prepare_server_spell(
                    struct.pack(">qqiih", character["id"], grant["uid"], *cell),
                    character,
                    {monster["id"]: monster},
                    runtime.fight,
                    character["account_id"],
                    deck,
                    action_id=runtime.action_id + 1,
                    line_of_sight=los,
                    critical=False,
                    rng=random.Random(17),
                )
            assert snapshot(runtime.fight) == before
            packets = commit_spell_transaction(
                runtime, transaction, stats_serializer=stats
            )
            json.dumps(snapshot(runtime.fight), allow_nan=False)
            states_after = [
                dict(reference=s.reference, level=s.level)
                for s in runtime.fight.actors[character["id"]].state_ledger.entries
            ]
            proof["stages"].append(
                dict(
                    stage=stage,
                    grant=grant,
                    target=list(cell),
                    costs=transaction.plan["costs"],
                    states_before=states_before,
                    states_after=states_after,
                    packet_count=len(packets),
                    trace=trace,
                    source_preserved_during_prepare=True,
                )
            )
        proof["status"] = "both_native_grant_transactions_committed"
    except Exception as error:
        proof.update(
            status="pending", reason=str(error), exception=type(error).__name__
        )
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    report = captured_run(
        parser.parse_args().output,
        commit_lifecycle=True,
        captured_commit_callback=dragon_branch,
    )
    print(
        json.dumps(
            report["owned_captured_transaction"].get("captured_commit_callback"),
            default=str,
        )
    )
