"""Source-only Iop producer review from already-streamed scoped native rows."""
import hashlib
import json
from pathlib import Path
from collections import Counter


def run():
    path = Path(".runtime/combat-review-20261008/iop-semantic-source-scope.json")
    source = json.loads(path.read_text())
    effects = {r["reference"]: r for r in source["effects"]}
    matrix = json.loads(
        Path(
            "docs/reports/combat-inventory/class-casting-precondition-matrix-20261008.json"
        ).read_text()
    )
    branches = [r for r in matrix["rows"] if 8 in r["breeds"]]
    files = [
        "combat_cast_events.py",
        "combat_native_events.py",
        "combat_event_replay.py",
        "combat_runtime_adapter.py",
        "combat_conditions.py",
        "combat_state_handler.py",
        "combat_state_decurse.py",
        "combat_effect_runtime.py",
        "combat_damage_events.py",
        "combat_session_adapter.py",
    ]
    findings = [
        dict(
            id="preparation500",
            state=3462,
            name="Preparation / Preparacion",
            effects=[151183, 151184, 151187],
            classification="absent current required event producer",
            event=500,
            detail="No explicit publisher and no mask6 producer in1422 scoped definitions;151183 cannot arm its damage/cast consumption children",
            limit="Original500 producer and ordering unknown; do not alias to damage2 or cast1024",
        ),
        dict(
            id="juicio1024",
            state=8912,
            name="Juicio / Judgment",
            effects=[397245, 397246, 397249],
            classification="firm current policy context gap",
            event=1024,
            detail="Global external1024 uses nullQe; triggering caster comparisonFalse blocks FIRE-activation conjunction",
            alternative="8402/8403 plus8916 remains executable",
            limit="Not an absent IsActivatedByElement evaluator or whole spell failure",
        ),
        dict(
            id="chargecombo1024",
            state=7553,
            name="Guerrero / Warrior; Carga / Charge4783",
            effects=[397553, 397554, 397555, 397556],
            classification="firm current policy context gap",
            event=1024,
            detail="Nullsource subscription_actor_ids preservesoriginalSELF target and original.cell; currentdistance=0 blocks4783 distance1/2/3 clauses",
            alternative="Other explicit spell-ID OR clauses can execute",
            limit="Actual cast-target context is missing for this policy; globaldistance provider exists",
        ),
        dict(
            id="portastandarte1005",
            state=8965,
            name="Portaestandarte state8965; Estandarte de Valentia / Standard of Bravery8405",
            effects=[398802],
            classification="partial missing notification alternative",
            event=1005,
            detail="Nativeexternal1005 has no current explicitpublisher or scopedmask6 producer",
            alternative="Implemented1010 KO branch remains available",
            limit="Original1005 producer/ordering unknown; no entirelistener broken claim",
        ),
        dict(
            id="sacudido2236",
            state=8913,
            name="Sacudido / Shaken; Sacudida4780",
            effects=[408737],
            classification="existing general notification route; scoped audit correction",
            event=2236,
            detail="Original ffw ARMOR97 assigns decrease event2236; eWR.bbx publishes ffw.fZu through ox. Existing source catalog family1011 eWR exports events[0,2236], consumed by current_stat_consumer",
            alternative="Ordinarydamage2 also activates this listener",
            limit="No missing2236 producer is proven; incoming cross-class armor decrease is outside the Iop-local mask census; actual listener delivery remains unverified",
        ),
    ]
    ownership = {
        "preparation500": [
            4775,
            4776,
            4777,
            4778,
            4779,
            4780,
            4781,
            4782,
            4783,
            4784,
            4785,
            4786,
            4787,
            4788,
            4789,
            4795,
            8415,
            8403,
        ],
        "juicio1024": [4776],
        "chargecombo1024": [4783],
        "portastandarte1005": [8405],
        "sacudido2236": [4780],
    }
    for r in findings:
        r["affected_class_references"] = ownership[r["id"]]
    for r in findings:
        r["native_definitions"] = [effects[i] for i in r["effects"]]
    output = dict(
        schema=1,
        scope="Independent read-only IOP nativebreed8 current producer audit",
        denominators=dict(
            class_id=8,
            book_actives=21,
            book_passives=20,
            class_granted_extras=4,
            effects=len(effects),
            states=len(source["states"]),
            families=len(Counter(r["family"] for r in effects.values())),
            conditional_branches=len(branches),
            conditional_references=len({r["spell"] for r in branches}),
        ),
        findings=findings,
        conditional_rows=branches,
        combo_reset_definitions=[
            effects[i] for i in [397916, 397920, 397918, 397924, 397922]
        ],
        source_hashes={
            str(Path("server/wakfu_server/combat") / f): hashlib.sha256(
                (Path("server/wakfu_server/combat") / f).read_bytes()
            ).hexdigest()
            for f in files
        },
        native_extraction_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        legacy_executor="combat_iop_cast.py has no production caller; unsupported3444/3467/6117 comments excluded as gaps",
        current_routes="Shared server-spell factory304/321;321 realrunnerphases+PKmask6,1024/1025 activebook scopes, state duration/expiry contracts",
        no_absent_textual_condition_route_proved=True,
        limits=[
            "1422 is transitive union including common4464 cosmetics, not1422 brokenclassspells",
            "NativeFalse producers cannot be madeTrue",
            "Current policy context defects do not recover original server emitter semantics",
            "No services/DB/gameplay execution or wholeclass gameplay certification",
        ],
    )
    p = Path(
        "docs/reports/combat-inventory/iop-semantic-producer-current-audit-20261008.json"
    )
    p.write_text(json.dumps(output, indent=2) + "\n")
    print(output["denominators"])


if __name__ == "__main__":
    run()
