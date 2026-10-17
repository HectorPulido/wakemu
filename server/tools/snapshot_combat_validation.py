"""Create a verified offline source/data copy while implementation continues."""
import argparse
import ast
import datetime
import hashlib
import json
from pathlib import Path
import shutil


def files(root, *, full_server=False):
    result = set()
    # Domain modules also import top-level codecs and protocol helpers.
    # Capture Python sources, without copying runtime/service configuration.
    for path in (root / "server").glob("*.py"):
        if path.is_file():
            result.add(path.relative_to(root))
    for directory in ("server/wakfu_server", "server/tools", "server/tests"):
        for path in (root / directory).rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix in (".py", ".json", ".gz", ".bin", ".csv")
            ):
                result.add(path.relative_to(root))
    # Movement fixtures import these standalone modules through test_ai_service.
    # Capture their source only; no service configuration or process is needed.
    if (root / "server/tests/test_ai_service.py").is_file():
        for name in ("planner.py", "server.py"):
            path = root / "server/ai-service" / name
            if path.is_file() and not path.is_symlink():
                result.add(path.relative_to(root))
        # The compatibility entries now delegate into the actual source package.
        for path in (root / "server/ai-service/wakfu_ai").rglob("*.py"):
            if (
                path.is_file()
                and not path.is_symlink()
                and "__pycache__" not in path.parts
            ):
                result.add(path.relative_to(root))
        # Server regressions import native oracle/session fixtures from this
        # directory without running the separate AI suite. Those fixtures are
        # required inputs of the server validation snapshot too.
        for path in (root / "server/ai-service/tests").rglob("*"):
            if (
                path.is_file()
                and not path.is_symlink()
                and "__pycache__" not in path.parts
                and path.suffix in (".py", ".json", ".gz", ".bin", ".csv")
            ):
                result.add(path.relative_to(root))
    for path in (root / "server/protocol").rglob("*"):
        if path.is_file() and path.suffix in (".json", ".gz", ".csv", ".tsv", ".txt"):
            result.add(path.relative_to(root))
    for path in (root / "server/migrations").glob("*.sql"):
        if path.is_file():
            result.add(path.relative_to(root))
    for path in (root / "server/test-fixtures").rglob("*"):
        if path.is_file() and path.suffix in (".json", ".gz", ".bin", ".csv", ".tsv"):
            result.add(path.relative_to(root))
    # Optional, version-assessed guide input used by impact observation. Freeze
    # this one declared input without copying unrelated internal reports.
    scenario_input = (
        root / "agents_docs/reports/combat-resilience-phase1-2/source-scenarios.json"
    )
    if scenario_input.is_file():
        result.add(scenario_input.relative_to(root))
    if full_server:
        # Complete server validation also inspects service assets, native probe
        # sources, launcher scripts and repository documentation. These are
        # source inputs only; no client binaries or runtime configuration.
        allowed = {
            ".py",
            ".json",
            ".gz",
            ".bin",
            ".csv",
            ".tsv",
            ".txt",
            ".sql",
            ".sh",
            ".html",
            ".css",
            ".js",
            ".svg",
            ".png",
            ".java",
            ".md",
            ".yaml",
            ".yml",
        }
        for directory in ("server", "sniffer", "client-tools", "tools", "docs"):
            for path in (root / directory).rglob("*"):
                if path.is_file() and (
                    path.suffix in allowed or path.name == "Dockerfile"
                ):
                    result.add(path.relative_to(root))
        for path in root.iterdir():
            if path.is_file() and (
                path.name in ("README.md", "AGENTS.md")
                or path.name.startswith(("compose", "docker-compose"))
                and path.suffix in (".yaml", ".yml")
            ):
                result.add(path.relative_to(root))
    # Some regressions consume published audit evidence as input fixtures.
    # Capture only explicitly named files in the combat report directory.
    reports = root / "docs/reports/combat-inventory"
    for test in (root / "server/tests").rglob("test_*.py"):
        try:
            tree = ast.parse(test.read_text())
        except SyntaxError:
            continue  # Invalid source remains captured for the test runner.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            name = node.value
            reference = Path(name)
            if reference.name != name:
                if reference.parent != Path("docs/reports/combat-inventory"):
                    continue
                name = reference.name
            if Path(name).suffix not in (".json", ".gz", ".csv", ".tsv", ".txt"):
                continue
            candidate = reports / name
            if candidate.is_file() and not candidate.is_symlink():
                result.add(candidate.relative_to(root))

    def safe(relative):
        path = root / relative
        return (
            not any(
                part.startswith(".")
                or part in {"__pycache__", "node_modules", "secrets", "credentials"}
                for part in relative.parts
            )
            and not any(
                parent.is_symlink()
                for parent in (path, *path.parents)
                if parent != root.parent
            )
            and path.resolve().is_relative_to(root.resolve())
        )

    return sorted(relative for relative in result if safe(relative))


def snapshot(root, destination, *, attempts=5, full_server=False):
    root, destination = root.resolve(), destination.resolve()
    if (
        destination.exists()
        or root == destination
        or root in destination.parents
        and ".runtime" not in destination.parts
    ):
        raise ValueError("Use a new private offline snapshot destination")
    destination.mkdir(parents=True)
    copied = {}
    try:
        for attempt in range(attempts):
            current = files(root, full_server=full_server)
            for relative in current:
                raw = (root / relative).read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                if copied.get(str(relative)) == digest:
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                copied[str(relative)] = digest
            for relative in set(copied) - {str(path) for path in current}:
                (destination / relative).unlink()
                del copied[relative]
            after = {
                str(relative): hashlib.sha256(
                    (root / relative).read_bytes()
                ).hexdigest()
                for relative in files(root, full_server=full_server)
            }
            if after == copied:
                manifest = dict(
                    scope="Offline unit/audit source and data copy; no service configuration or live database",
                    full_server=full_server,
                    source_root=str(root),
                    snapshot_root=str(destination),
                    created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    verified_attempt=attempt + 1,
                    files=copied,
                )
                (destination / "validation-snapshot.json").write_text(
                    json.dumps(manifest, indent=2) + "\n"
                )
                return dict(
                    snapshot_root=str(destination),
                    files=len(copied),
                    verified_attempt=attempt + 1,
                )
        raise ValueError("Source changed during every snapshot attempt; retry capture")
    except BaseException:
        shutil.rmtree(destination)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--full-server",
        action="store_true",
        help="Include server services/assets and repository source inputs used by the complete suite",
    )
    args = parser.parse_args()
    print(
        json.dumps(snapshot(args.root, args.destination, full_server=args.full_server))
    )
