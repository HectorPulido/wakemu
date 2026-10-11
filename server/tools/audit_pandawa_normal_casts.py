"""Bounded Pandawa active/passive matrix through ordinary Ready and owned casts.

The process pins one complete PostgreSQL release without publishing it. Each
active deck chunk is initialized independently with each single legal optional
class passive. All actions use actual resources, target validation and commits.
"""
import argparse
from collections import Counter
import gc
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch


REVISION = "c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46"


def run(output, *, revision=REVISION, candidate_limit=64):
    gc.disable()
    from wakfu_server import native_catalog

    with patch.object(native_catalog, "release", return_value=revision):
        import audit_ready_start as ready
        from audit_class_normal_casts import NormalCastAudit
        from wakfu_server.spells import available_spells

        inventory_path = Path(
            "docs/reports/combat-inventory/pandawa-catalog-inventory-20261010.json"
        )
        inventory = json.loads(inventory_path.read_text())
        # Native class IDs are derived from the pinned inventory, not guessed
        # common spell IDs. available_spells supplies actual deck legality.
        own = {row["id"] for row in inventory["spells"] if row["breed"] == 12}
        legal = [row for row in available_spells(12, 200) if row["id"] in own]
        active = sorted(row["id"] for row in legal if row["kind"] == "active")
        passives = sorted(row["id"] for row in legal if row["kind"] == "passive")
        chunks = [active[index : index + 12] for index in range(0, len(active), 12)]
        variants = [None, *passives]
        cases = [(12, 200, passive) for passive in variants for _ in chunks]
        pending = {passive: iter(chunks) for passive in variants}
        inspector = NormalCastAudit(
            candidate_limit=candidate_limit,
            maximum_eligible=1,
            commit_each_prepared=True,
        )
        report = ready.run(
            output,
            cases_override=cases,
            active_deck_provider=lambda breed, level, passive: next(pending[passive]),
            on_runtime=inspector,
            turn_cycle=True,
            turn_steps=0,
            monster_reference=5574,
            monster_level=133,
        )
        matrix, grants = [], []
        for source in report["rows"]:
            for action in source.get("runtime_access", {}).get("actions", []):
                matrix.append(
                    dict(
                        passive=source["passive"],
                        reference=action["reference"],
                        origin=action["origin"],
                        status=action["status"],
                    )
                )
                for attempt in action.get("attempts", []):
                    commit = attempt.get("commit", {})
                    observed = sorted(
                        set(commit.get("owned_grants_after", ()))
                        & {4718, 6847, 6848, 8591, 8592}
                    )
                    if observed:
                        grants.append(
                            dict(
                                passive=source["passive"],
                                parent_spell=action["reference"],
                                actual_owned_grants=observed,
                                state_ledgers_after=commit.get("state_ledgers_after"),
                            )
                        )
        report.update(
            pandawa_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            pandawa_scope=dict(
                catalog_revision=revision,
                active=active,
                passives=passives,
                expected_decks=len(cases),
                expected_normal_action_rows=len(active) * len(variants),
                candidate_limit=candidate_limit,
                full_conditional_gameplay_verified=False,
            ),
            pandawa_action_matrix=matrix,
            pandawa_temporary_grants=grants,
            pandawa_action_status_counts=dict(Counter(row["status"] for row in matrix)),
        )
        Path(output).write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalog-release", default=REVISION)
    parser.add_argument("--candidate-limit", type=int, default=64)
    args = parser.parse_args()
    result = run(
        args.output, revision=args.catalog_release, candidate_limit=args.candidate_limit
    )
    print(
        json.dumps(
            dict(
                decks=len(result["rows"]), counts=result["pandawa_action_status_counts"]
            )
        ),
        flush=True,
    )
    os._exit(0)
