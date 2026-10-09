"""Stream completed normal report into small source-bound conditional observations."""
import argparse
import json
from pathlib import Path
from summarize_normal_cast_rejections import stream_report_rows


def run(report, output):
    observations = []

    def observe(row):
        for action in row.get("runtime_access", {}).get("actions", []):
            for attempt in action.get("attempts", []):
                commit = attempt.get("commit", attempt.get("representative_commit", {}))
                selection = attempt.get("native_casting_selection")
                if commit.get("status") != "committed" or not isinstance(
                    selection, dict
                ):
                    continue
                observations.append(
                    dict(
                        breed=row["breed"],
                        level=row["level"],
                        reference=action["reference"],
                        origin=action["origin"],
                        commit_status=commit["status"],
                        source_preserved=attempt.get("source_preserved"),
                        native_casting_selection=selection,
                        native_casting_flags=attempt.get("native_casting_flags"),
                        native_casting_diagnostic=attempt.get(
                            "native_casting_diagnostic"
                        ),
                        costs=attempt.get("costs"),
                    )
                )

    source = stream_report_rows(report, observe)
    if source["metadata"].get("finished") is not True:
        raise ValueError("Unfinished casting evidence")
    for row in observations:
        row["report_sha256"] = source["report_sha256"]
    result = dict(
        schema="class-conditional-committed-observations-v1",
        report=str(report),
        **source,
        observations=observations,
    )
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Extracted {len(observations)} source-bound committed observations")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.report, a.output)
