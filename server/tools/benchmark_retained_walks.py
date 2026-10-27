"""Bounded original400 population/removal benchmark on a real owned factory.

This is an offline component, not a class Ready or a World throughput claim.
Original null400 runners create all measured rows through their unchanged
handlers. Measurements never mutate the Fight, packets or transaction RNG.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time
from unittest.mock import patch


def run(manifest, *, sizes=(16, 64, 256), repeats=7):
    from tools.sublimation_semantic_fixture import build_fixture
    from wakfu_server.combat_effect_dispatch import EffectInvocation
    from wakfu_server.combat_execution_context import constructed_execution_context
    from wakfu_server.fight_checkpoint_store import snapshot, checkpoint_digest
    from wakfu_server import combat_server_spell

    fixture = build_fixture(27159, manifest)
    fight = fixture.fight
    dispatcher, packets = fixture.dispatcher_for(fight)
    retention = dispatcher.native_retention
    initial_uids = set(retention.view().by_uid)
    resources = {
        uid: (actor.hp, actor.ap, actor.mp, actor.max_hp)
        for uid, actor in fight.actors.items()
    }
    context = constructed_execution_context().payload().hex()
    created, rows = [], []
    owner_uid = next(
        state.uid
        for state in fight.actors[7].state_ledger.entries
        if state.reference == 6034
    )

    def measure(function):
        wall, cpu, result = [], [], None
        for _ in range(repeats):
            started, cpu_started = time.perf_counter(), time.thread_time()
            result = function()
            wall.append(time.perf_counter() - started)
            cpu.append(time.thread_time() - cpu_started)
        return (
            dict(
                median_wall_seconds=statistics.median(wall),
                median_cpu_seconds=statistics.median(cpu),
                samples=len(wall),
            ),
            result,
        )

    with patch.object(
        combat_server_spell, "compiled_runtime_catalog", return_value=fixture.compiled
    ):
        for size in sizes:
            while len(created) < size:
                before = set(fight.owned_stat_effects)
                dispatcher.execute(
                    EffectInvocation(
                        283517,
                        1,
                        7,
                        7,
                        fight.actors[7].position,
                        native_explicit_target=True,
                        native_context_hex=context,
                        native_retained_container={"present": False},
                    )
                )
                new = set(fight.owned_stat_effects) - before
                if len(new) != 1:
                    raise ValueError(
                        "Original400 did not retain exactly one actual runner"
                    )
                created.append(new.pop())
            if resources != {
                uid: (actor.hp, actor.ap, actor.mp, actor.max_hp)
                for uid, actor in fight.actors.items()
            }:
                raise ValueError(
                    "Original null400 unexpectedly changed actor resources"
                )
            view = retention.view()  # Warm/prune before the pure measurement.
            removal = retention.removal(view)
            actual = removal.plan(tuple(created))
            if tuple(entry.uid for entry in actual) != tuple(created):
                raise ValueError("Native removal plan changed original root order")
            before = checkpoint_digest(snapshot(fight))
            random_before = fixture.factory.transaction_rng.getstate()
            packet_count = len(packets)
            view_timing, final_view = measure(retention.view)
            plan_timing, final_plan = measure(lambda: removal.plan(tuple(created)))

            def first_plan():
                return retention.removal(retention.view()).plan(tuple(created))

            first_plan_timing, first_result = measure(first_plan)
            owner_plan = removal.plan((owner_uid,))
            if not owner_plan or owner_plan[-1].uid != owner_uid:
                raise ValueError(
                    "Native owner plan must remove its children before the carrier"
                )
            if tuple(entry.uid for entry in first_result) != tuple(created):
                raise ValueError(
                    "Fresh native removal plan changed original root order"
                )
            if (
                checkpoint_digest(snapshot(fight)) != before
                or fixture.factory.transaction_rng.getstate() != random_before
                or len(packets) != packet_count
            ):
                raise ValueError("Pure retained benchmark changed Fight/outbox/RNG")
            rows.append(
                dict(
                    requested=size,
                    actual_retained=len(view.entries),
                    view=view_timing,
                    removal_plan=plan_timing,
                    fresh_view_and_first_plan=first_plan_timing,
                    owner_plan_uids=[entry.uid for entry in owner_plan],
                    view_uid_digest=hashlib.sha256(
                        json.dumps([entry.uid for entry in final_view.entries]).encode()
                    ).hexdigest(),
                    plan_uid_digest=hashlib.sha256(
                        json.dumps([entry.uid for entry in final_plan]).encode()
                    ).hexdigest(),
                    fight_digest=before,
                    measurement_state_unchanged=True,
                )
            )
        # The same actual removal handlers settle the private component. This
        # is outside the timing sample and verifies source ownership/lifetimes.
        retention.removal(retention.view()).remove(tuple(created))
        retention.synchronize()
        if set(retention.view().by_uid) != initial_uids:
            raise ValueError("Original400 removal changed unrelated retained sources")
        if resources != {
            uid: (actor.hp, actor.ap, actor.mp, actor.max_hp)
            for uid, actor in fight.actors.items()
        }:
            raise ValueError("Original400 removal changed actor resources")
        owner_view = retention.view()
        owner_removal = retention.removal(owner_view)
        owner_plan = owner_removal.plan((owner_uid,))
        # Duplicate requested children retain native once-only planning/order.
        requested = (owner_uid, *(entry.uid for entry in owner_plan[:-1]))
        if owner_removal.plan(requested) != owner_plan:
            raise ValueError("Native owner/child duplicate input changed removal order")
        removed = owner_removal.remove(requested)
        if removed != owner_plan:
            raise ValueError("Actual native owner removal changed its validated plan")
        retention.synchronize()
        if set(retention.view().by_uid) != initial_uids - {
            entry.uid for entry in owner_plan
        }:
            raise ValueError("Native owner removal changed independently owned sources")
    return dict(
        schema=1,
        status="PASS",
        method="actual_owned_factory_original400_retained_walks",
        manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        original_effect_reference=283517,
        full_class_ready_qualified=False,
        world_throughput_qualified=False,
        rows=rows,
        actual_removal_preserved_unrelated_sources=True,
        owner_children_removed_in_native_order_once=True,
        timing_interpretation=(
            "removal_plan is warm repeated planning on one immutable view; "
            "fresh_view_and_first_plan includes full view validation and first-use index cost"
        ),
        source_sha256={
            name: hashlib.sha256(
                (Path(__file__).parents[1] / "wakfu_server/combat" / name).read_bytes()
            ).hexdigest()
            for name in (
                "combat_retained_effects.py",
                "combat_retained_runtime.py",
                "combat_event_replay.py",
            )
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sizes", default="16,64,256")
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    sizes = tuple(int(value) for value in args.sizes.split(","))
    if (
        not sizes
        or tuple(sorted(set(sizes))) != sizes
        or sizes[0] < 1
        or sizes[-1] > 1024
        or not 1 <= args.repeats <= 31
    ):
        raise ValueError("Bounded increasing population sizes/repeats required")
    result = run(args.manifest, sizes=sizes, repeats=args.repeats)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
