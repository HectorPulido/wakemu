"""Run existing legal common-entry cast audit after native start subscriptions.

Preserves real exported innates, criteria, UID allocation and normal event
replay. No synthetic state setup or spell/breed execution branch is used.
The external1003 producer remains the documented server-side inference.
"""
import json
from pathlib import Path
import audit_active_spells as audit
from wakfu_server.combat_start_events import deliver_fight_start


def run(*, cases, output, critical=False):
    original = audit.initialize_transaction

    def initialize_with_start(fight, initial, factory, states, *, owner_id):
        preview, packets = original(fight, initial, factory, states, owner_id=owner_id)
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        with preview.effect_resolution():
            deliver_fight_start(dispatcher, initialized_actor_ids=tuple(preview.actors))
        return preview, tuple(packets) + tuple(outbox)

    audit.initialize_transaction = initialize_with_start
    try:
        report = audit.run(cases=cases, output_name=output, critical=critical)
    finally:
        audit.initialize_transaction = original
    report[
        "initialization_policy"
    ] = "All real native roots installed, then inferred external1003 delivery through normal replay before cast; no synthetic states/predicate bypass."
    report["limitations"].append(
        "Native ordinary turn-event producers after the starting boundary remain unaudited; passing an NPC FSM turn does not synthesize those events."
    )
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("spell_id", type=int, nargs="?")
    parser.add_argument("levels", nargs="*", type=int)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Audit every class active spell after native combat initialization",
    )
    parser.add_argument("--variant", default="enemy")
    parser.add_argument(
        "--critical",
        action="store_true",
        help="Audit the native critical branch explicitly",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.all:
        if args.spell_id is not None or args.levels:
            parser.error("--all cannot be combined with a spell or levels")
        cases = None
    else:
        if args.spell_id is None or not args.levels:
            parser.error("provide a spell and levels, or --all")
        cases = [
            dict(spell_id=args.spell_id, level=level, variant=args.variant)
            for level in args.levels
        ]
    report = run(cases=cases, output=args.output, critical=args.critical)
    for row in report["rows"]:
        print(json.dumps(row, ensure_ascii=False), flush=True)
