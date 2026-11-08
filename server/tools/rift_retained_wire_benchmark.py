"""Compare full retained-view wire parsing on one fixed native payload population.

Run after candidate application, outside a live endurance run:
PYTHONPATH=server python3 server/tools/rift_retained_wire_benchmark.py --count 4283
This creates no accounts, sockets, database rows or gameplay actions.
"""
import argparse
from dataclasses import asdict
import json
import time
from types import SimpleNamespace


def fixture(count):
    from wakfu_server.combat_state import Actor
    from wakfu_server.combat_retained_effects import RetainedEffect
    from wakfu_server.combat_retained_runtime import group_payload

    actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
    groups, records, entries = {}, {}, []
    timing = bytes.fromhex(
        "080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800"
    )
    for uid in range(1, count + 1):
        payload = group_payload(
            uid=uid,
            base_uid=uid,
            generic_effect=350552,
            caster_id=7,
            target_id=None,
            cell=(4, 5, 0),
            container_type=None,
            container_id=None,
            timing_payload=timing,
        ).hex()
        entry = RetainedEffect(
            uid, None, 949, 350552, manager_id=7, container_present=False
        )
        groups[uid] = dict(
            target_id=None, effect_class=949, state_uid=None, payload=payload
        )
        records[uid] = asdict(entry)
        entries.append(entry)
    fight = SimpleNamespace(
        id=12,
        actors={7: actor},
        owned_stat_effects={},
        state_wire_payloads={},
        native_owned_group_effects=groups,
        native_retained_records=records,
        native_retained_order=list(records),
        native_retained_tracking=True,
    )
    return fight, entries


def benchmark(count, passes, mode):
    from wakfu_server import combat_effect_removal as codec
    from wakfu_server import combat_retained_effects as retained

    fight, entries = fixture(count)
    codec._cached_hex_identity_fields.cache_clear()
    codec._cached_identity_fields.cache_clear()
    previous, rows = {}, []
    for iteration in range(passes):
        wire = retained._RetainedWirePass(previous) if mode == "candidate" else None
        before = codec._cached_identity_fields.cache_info().misses
        started = time.perf_counter()
        options = {"_wire_pass": wire} if wire is not None else {}
        view = retained.NativeRetainedEffectView(
            fight, entries, population_verified_complete=True, **options
        )
        elapsed = time.perf_counter() - started
        if wire is not None:
            previous = wire.current
        rows.append(
            dict(
                pass_index=iteration,
                seconds=elapsed,
                parser_misses=codec._cached_identity_fields.cache_info().misses
                - before,
                validated_entries=len(view.entries),
            )
        )
    return dict(mode=mode, count=count, passes=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=4283)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument(
        "--mode", choices=("baseline", "candidate", "both"), default="both"
    )
    args = parser.parse_args()
    if args.count < 1 or args.passes < 2:
        parser.error("positive count and at least two passes are required")
    modes = ("baseline", "candidate") if args.mode == "both" else (args.mode,)
    print(
        json.dumps(
            [benchmark(args.count, args.passes, mode) for mode in modes], indent=2
        )
    )


if __name__ == "__main__":
    main()
