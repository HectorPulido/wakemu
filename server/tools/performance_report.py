"""Read private server performance exports without importing the game server."""
import argparse
import json
from pathlib import Path


def render(payload, *, order="total", top=20):
    summary = payload.get("features", {})
    if isinstance(summary, list):
        summary = payload
    keys = {"total": "total_ms", "cpu": "cpu_ms", "wait": "wait_ms", "max": "max_ms"}
    rows = sorted(
        summary.get("features", []), key=lambda row: row[keys[order]], reverse=True
    )[:top]
    lines = [
        "Feature | Calls | CPU measured calls | Wall ms | Thread CPU ms | Non-CPU ms~ | Max ms | p95 upper ms | Errors",
        "--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:",
    ]
    for row in rows:
        lines.append(
            f"{row['name']} | {row['count']} | {row.get('cpu_measured_calls', row['count'])} | {row['total_ms']:.2f} | "
            f"{row['cpu_ms']:.2f} | {row['wait_ms']:.2f} | {row['max_ms']:.2f} | "
            f"{row['p95_ms']:.2f} | {row['errors']}"
        )
    lines.append(
        "\nInclusive spans overlap; do not add their totals. Non-CPU time uses only calls with measured thread CPU; unknown CPU does not count as waiting. It is not proof of a specific lock or I/O wait."
    )
    stacks = payload.get("stacks", [])[:top]
    if stacks:
        lines.append(
            "\nMost sampled Python stacks (includes idle/waiting threads; not CPU attribution):"
        )
        for stack in stacks:
            lines.append(f"{stack['samples']} samples: " + " -> ".join(stack["frames"]))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--sort", choices=("total", "cpu", "wait", "max"), default="total"
    )
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.top <= 128:
        parser.error("--top must be between 1 and 128")
    print(render(json.loads(args.path.read_text()), order=args.sort, top=args.top))


if __name__ == "__main__":
    main()
