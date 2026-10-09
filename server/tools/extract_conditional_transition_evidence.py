"""Stream transition cases while discarding traces and state snapshots."""
import argparse
import json
from pathlib import Path
from summarize_normal_cast_rejections import stream_report_rows


def run(report, output):
    rows = []
    observations = []

    def observe(row):
        access = row.get("runtime_access", {})
        case = access.get("case", {})
        controls = []
        for parent in access.get("attempts", []):
            for attempt in parent.get("conditional_attempts", []):
                commit = attempt.get("commit")
                if isinstance(commit, dict) and isinstance(
                    commit.get("selected"), dict
                ):
                    observations.append(
                        dict(
                            reference=case["spell"],
                            origin="actual_state_transition",
                            commit_status="committed",
                            source_preserved=access.get("source_preserved"),
                            native_casting_selection=commit["selected"],
                            native_casting_flags=commit.get("flags"),
                            costs=commit.get("costs"),
                            breed=case.get("breed"),
                            level=case.get("level"),
                        )
                    )
                control = attempt.get("removal_control")
                if isinstance(control, dict):
                    controls.append(
                        dict(
                            status=control.get("status"),
                            removal_mechanism=control.get("removal_mechanism"),
                        )
                    )
        rows.append(
            dict(
                case={
                    k: case.get(k)
                    for k in ("spell", "branch", "breed", "level", "state", "selector")
                },
                conditional_branch_verified=access.get("conditional_branch_verified"),
                removal_control_verified=access.get("removal_control_verified"),
                source_preserved=access.get("source_preserved"),
                status=access.get("status"),
                removal_control_status=access.get("removal_control_status"),
                controls=controls,
            )
        )

    source = stream_report_rows(report, observe)
    for row in observations:
        row["report_sha256"] = source["report_sha256"]
    result = dict(
        schema="class-conditional-transition-evidence-v1",
        report=str(report),
        **source,
        rows=rows,
        observations=observations,
    )
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"Extracted {len(rows)} cases, {len(observations)} actual committed selections"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("report", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.report, a.output)
