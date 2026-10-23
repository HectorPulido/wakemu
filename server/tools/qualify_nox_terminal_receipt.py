"""Qualify actual terminal executions independently of stale runner assertions."""
import json
from pathlib import Path


def qualify_terminal_receipt(receipt):
    """Require late effective native children, not an earlier subscription birth."""
    rows = receipt.get("selected_executions", ())
    boundaries = receipt.get("boundaries", ())
    if receipt.get("reference") != 5664 or not boundaries:
        raise ValueError("Missing actual Nox lifecycle receipt")
    final = boundaries[-1]
    states = dict(final.get("states", ()))
    expected_table = 11 + states.get(8988, 0)
    if states.get(8979, 0) < 1:
        raise ValueError("Native final phase8979 was not observed")
    for parent in rows:
        if (
            parent.get("reference") != 401563
            or parent.get("result") is not True
            or parent.get("table_turn") != expected_table
        ):
            continue
        siblings = [
            row
            for row in rows
            if row.get("turn_id") == parent.get("turn_id")
            and row.get("table_turn") == expected_table
            and row.get("result") is True
        ]
        references = {row.get("reference") for row in siblings}
        if not {402278, 402279} <= references:
            continue
        # Effective score publication plus target selection and an executed
        # terminal leaf cannot be explained by group330 subscription recording.
        leaves = [row for row in siblings if row.get("reference") in (402280, 402283)]
        if not leaves:
            continue
        return dict(
            schema="nox-native-terminal-execution-qualification-v1",
            status="native_terminal_producer_and_children_observed",
            table_turn=expected_table,
            turn_id=parent["turn_id"],
            phase=final["phase"],
            score_effect=402278,
            selector_effect=402279,
            terminal_leaves=[
                dict(reference=row["reference"], target_id=row.get("target_id"))
                for row in leaves
            ],
            original_runner_status=receipt.get("status"),
            scope="real_native_phase_and_terminal_execution_not_player_victory_or_rewards",
        )
    raise ValueError(
        "No late terminal activation with effective native score/selector/leaf children"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = qualify_terminal_receipt(json.loads(args.receipt.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
