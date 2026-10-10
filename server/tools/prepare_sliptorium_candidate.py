"""Prepare Sliptorium offline with literal backward native final-exit evidence."""
import json, sys
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parent),
    str(Path(__file__).resolve().parents[1]),
]
from build_native_teleport_configuration import build
from wakfu_server.dungeon_runtime_config import canonical_hash
from prepare_native_physical_candidates import normalized_roster

load = lambda p: json.load(open(p))
base = next(
    b
    for b in load(
        ".runtime/local/methodwakfu-dungeons/local-policy-configs-all87/configurations.json"
    )["configurations"]
    if b["route"]["key"] == "native_dungeon_48"
)
native = next(
    r
    for r in load("docs/reports/dungeons/inventory.json")["records"]
    if r["key"] == "native:48"
)
row = next(
    r
    for r in load("docs/reports/dungeons/AUTOMATIC-TELEPORT-COMPOSITION-COVERAGE.json")[
        "records"
    ]
    if r["key"] == "native:48"
)
topology = load(
    ".runtime/local/native-teleport-topology-candidates/native_dungeon_48.json"
)
transports = load(
    ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
)
config = build(
    base,
    topology,
    normalized_roster(row["roster_candidate"], native),
    transports,
    version=base["version"] + 1,
)
path = Path(".runtime/local/native-teleport-complete-candidates/native_dungeon_48.json")
path.write_text(json.dumps(config, indent=2) + "\n")
report = dict(
    key="native:48",
    name="Sliptorium",
    path=str(path),
    configuration_sha256=canonical_hash(config),
    status="offline_configuration_prepared",
    rooms=3,
    completed_exit_witness=config["topology"]["completed_exit_witness"],
    activation_readiness="requires_postgres_lifecycle",
    boss_mechanics="not_proved",
    official=False,
)
Path("docs/reports/dungeons/SLIPTORIUM-BACKWARD-EXIT-CANDIDATE.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(json.dumps(report))
