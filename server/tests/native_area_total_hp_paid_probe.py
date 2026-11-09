"""Fresh native Ready/paid actions, not a historical SQL-checkpoint replay."""
import os, sys, json, inspect, time, hashlib, traceback, argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--expected-generation", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
from pathlib import Path
from wakfu_server import native_catalog


class RO:
    def get(self, *a, **k):
        return None

    def mget(self, keys):
        return [None] * len(keys)

    def setex(self, *a, **k):
        return False

    def pipeline(self, *a, **k):
        return self

    def eval(self, *a, **k):
        return [None] * a[1]

    def execute(self):
        return []


native_catalog._redis = lambda: RO()
from wakfu_server.native_compiled_catalog import resolve_publication

publication = resolve_publication(source_revision=native_catalog.release())
assert publication["generation"] == args.expected_generation
import importlib

candidate_path = None
source_names = [
    "combat_runtime_adapter",
    "combat_conditions",
    "combat_range_conditions",
    "combat_area_total_hp_conditions",
]
actual_sources = {
    name: hashlib.sha256(
        Path(importlib.import_module("wakfu_server." + name).__file__).read_bytes()
    ).hexdigest()
    for name in source_names
}
from tests.jondo_native_support_probe import build_fixture, _oracle, _drain
from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
from wakfu_server.fight_checkpoint_store import snapshot

source = (
    inspect.getsource(build_fixture)
    .replace("maximum(8, 200)", "maximum(8, 48)")
    .replace("level=200", "level=48")
)
namespace = dict(build_fixture.__globals__)
exec(compile(source, "<normal-beforeReady-level48-fixture>", "exec"), namespace)
case = namespace["build_fixture"](
    1274,
    48,
    npc_position=(-5, -7, -1),
    player_position=(-8, -7, -1),
    allies=((1726, 58, (-4, -7, -1)),),
)
oracle = _oracle(case)
stats = NativeStats(
    characters=case.characters,
    monsters=case.monsters,
    fight_id=case.fight.id,
    map_id=1134,
)
report = dict(
    actual_source_hashes=actual_sources,
    status="RUNNING",
    generation=publication["generation"],
    private_overlays=bool(candidate_path),
    fixture_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
    initial=snapshot(case.fight, runtime=case.runtime),
    actions=[],
    phase="native_wall_producer",
    historical_fight_557_replayed=False,
)


def record():
    Path(args.output).write_text(json.dumps(report, default=str) + "\n")


def to_turn(identity):
    for _ in range(16):
        if case.fight.current.id == identity:
            return
        case.advance()
    raise RuntimeError("Native turn bound did not reach actual actor")


def cast(ref, identity, cell):
    before = oracle.state_identity(case.runtime)
    rng = case.rng.getstate()
    owned = oracle.owned_spells(case.fight)
    assert ref in owned
    action = dict(
        type="cast", spellId=ref, level=owned[ref], targetId=identity, target=list(cell)
    )
    actor = case.fight.current
    cost_before = (actor.ap, actor.mp, actor.effect_stats[4])
    source_id = actor.id
    try:
        packets = oracle.commit(action, stats_serializer=stats)
        _drain(case)
    except Exception:
        assert oracle.state_identity(case.runtime) == before
        assert case.rng.getstate() == rng
        raise
    report["actions"].append(
        dict(
            caster=source_id,
            action=action,
            cost_before=cost_before,
            cost_after=(
                case.fight.actors[source_id].ap,
                case.fight.actors[source_id].mp,
                case.fight.actors[source_id].effect_stats[4],
            ),
            packets=len(packets),
        )
    )
    print(
        "PAID",
        source_id,
        ref,
        "areas",
        [(i, r["reference"]) for i, r in case.fight.native_effect_areas.items()],
        flush=True,
    )
    record()


try:
    to_turn(-7)
    cast(1919, 7, case.fight.actors[7].position)
    walls = [
        (uid, row)
        for uid, row in case.fight.native_effect_areas.items()
        if row["reference"] == 196
    ]
    report["walls_after_native_1919"] = [
        dict(
            uid=i,
            cell=r["cell"],
            hp=r.get("native_wall_hp_current"),
            owner=r["owner_id"],
            effect_reference=r.get("effect_reference"),
        )
        for i, r in walls
    ]
    if not walls:
        raise RuntimeError(
            "Actual native1919 did not produce196; inspect declared next turn/initial producer before any alternate fixture"
        )
    to_turn(7)
    report["phase"] = "paid_Iop4778_against_actual_fbd"
    uid, row = min(
        walls,
        key=lambda x: sum(
            abs(a - b)
            for a, b in zip(x[1]["cell"][:2], case.fight.actors[7].position[:2])
        ),
    )
    report["selected_wall"] = dict(
        uid=uid, cell=row["cell"], hp=row.get("native_wall_hp_current")
    )
    cast(4778, None, row["cell"])
    report["status"] = "PASS_FRESH_PAID4778_WITH_NATIVE_FBD196"
except Exception as error:
    report.update(
        status="OBSERVED_FRESH_NATIVE_REJECTION",
        error=repr(error),
        traceback=traceback.format_exc(),
    )
finally:
    report["final"] = snapshot(case.fight, runtime=case.runtime)
    record()
print(
    json.dumps(
        dict(
            status=report["status"],
            error=report.get("error"),
            paid_actions=len(report["actions"]),
        )
    )
)
raise SystemExit(report["status"] != "PASS_FRESH_PAID4778_WITH_NATIVE_FBD196")
