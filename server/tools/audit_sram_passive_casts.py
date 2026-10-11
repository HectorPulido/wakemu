"""Actual legal Sram optional-passive decks and normal spell transactions.

Each passive is equipped through the ordinary deck/Ready path. Transactions
use isolated branches: this qualifies runtime routes, not every passive trigger.
"""
import argparse
from pathlib import Path

import audit_ready_start as ready
from audit_class_normal_casts import NormalCastAudit
from wakfu_server.spells import available_spells


def run(output):
    spells = available_spells(4, 200)
    passives = sorted(row["id"] for row in spells if row["kind"] == "passive")
    active = sorted(row["id"] for row in spells if row["kind"] == "active")
    chunks = [active[index : index + 12] for index in range(0, len(active), 12)]
    cases = [(4, 200, passive) for passive in passives for _ in chunks]
    pending = {passive: iter(chunks) for passive in passives}
    inspector = NormalCastAudit(
        candidate_limit=128,
        maximum_eligible=1,
        commit_each_prepared=True,
    )
    return ready.run(
        output,
        cases_override=cases,
        active_deck_provider=lambda breed, level, passive: next(pending[passive]),
        on_runtime=inspector,
        turn_cycle=True,
        turn_steps=0,
        monster_reference=5574,
        monster_level=133,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
