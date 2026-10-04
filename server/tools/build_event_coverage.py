"""Capture metadata only: never copy authentication or packet bodies into the audit."""
import collections, json, re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
catalog = json.loads((root / "server/protocol/catalog.json").read_text())
messages = collections.defaultdict(list)
for m in catalog["messages"]:
    if m.get("opcode") is not None:
        messages[(m.get("direction"), m["opcode"])].append(m)
actions = {}
for p in [
    root / "server/protocol/actions.json",
    *root.glob(
        ".runtime/official-creation/captures/*/snapshot-final/decoded/actions.json"
    ),
]:
    data = json.loads(p.read_text())
    for a in data if isinstance(data, list) else data.get("actions", []):
        actions[(a["direction"], a["opcode"])] = a
bindings = {
    (a["direction"], a["opcode"]): a
    for a in json.loads(
        (root / "server/protocol/action-registry-map.json").read_text()
    )["observed_direct_bindings"]
}
callers = collections.defaultdict(list)
for line in (root / ".runtime/local/message-consumers.tsv").read_text().splitlines():
    owner, caller, method, called = line.split("\t")
    callers[owner].append(dict(class_name=caller, method=method, codec_call=called))
sources = sorted(
    [
        *root.glob(".runtime/captures/*/decoded/frames.jsonl"),
        *root.glob(
            ".runtime/official-creation/captures/*/snapshot-*/decoded/frames.jsonl"
        ),
    ]
)
seen = set()
counts = collections.Counter()
for p in sources:
    session = (
        p.parent.parent.name
        if p.parent.parent.name.startswith("2026-")
        else p.parent.parent.parent.name
    )
    for line in p.read_text().splitlines():
        f = json.loads(line)
        key = (
            session,
            f.get("channel"),
            f.get("capture_seq"),
            f.get("time"),
            f["direction"],
            f.get("opcode"),
        )
        if key in seen:
            continue
        seen.add(key)
        counts[(f["direction"], f.get("opcode"))] += 1
# Deliberately explicit: source matches alone are not proof of implemented semantics.
reviewed = {
    13713: (
        "character_update",
        "i64 actorID + character blob",
        "chK.a(cwY) -> fkK.suH.sY -> biB.as; UI gaO refresh; sends cpP12851(actorID)",
        "Own-identity/minimal character adaptation",
        "character blob sections beyond current minimal subset",
    ),
    13778: (
        "market_cache_keys",
        "bool reset + u8 count + count*i64",
        "chK.a(cwX): reset bGE.removeAll then bGE.ln(eachID)",
        "Fixture replay only",
        "Authoritative local market cache and cache invalidation",
    ),
    13735: (
        "actor_cosmetic_toggle",
        "i64 actorID + i32 graphicID + bool remove",
        "cFV.a(cBk): bio.jv(actorID); missing actor ignored; beS.t(graphicID,!remove)",
        "Fixture replay only",
        "Owned cosmetic eligibility/lifecycle",
    ),
    13753: (
        "external_fight_creation",
        "i32 fightID + complex external-fight description",
        "ckM.a(cuY): fcz.Tv(kind), reject unknown model; construct buG and teams/terrain",
        "Explicitly excluded from bootstrap fixture",
        "Owned external combat visibility and spectator/join lifecycle",
    ),
    13726: (
        "effect_area_despawn",
        "i32 fightID/actionID/sequence + i64 areaUID",
        "cjp -> queued aTW; Qs.dn(areaUID), ignore missing; aTW.cbj removes Qs area",
        "Not implemented for owned effect areas",
        "Area creation/trigger/destruction; this is not state removal",
    ),
    13130: (
        "attack_monster_group",
        "i64 targetID + i32 targetX,targetY + i16 targetZ + bool keyboardFlag",
        "cWi.run -> bxQ/eVt -> ala.c(own,target)<=25 -> biB.as -> coP; no pending mutation in send path",
        "Owned combat entry with validated arena; runtime tested subset",
        "Native arena generation across maps; no dedicated rejection ACK demonstrated",
    ),
    12477: (
        "generic_error",
        "4*i32 errorCode,x,y,type",
        "cFK.a(cAy): bQX.a(code); bto.FO only10/35/36 -> bsM; dev.Nm inherited cYt -> graphical path retry eXi for other codes",
        "Native codec audited; runtime rejection integration pending",
        "No dedicated combat pending reset proved; handler ignores x,y,type",
    ),
}
implemented = {
    12588: "combat_spells.animation",
    12678: "combat_spells.notification",
    12613: "combat_effects/combat_states: direct damage, audited MP loss, Iop state subset only",
    13509: "combat_melee.animation (native unarmed2145 only)",
    13260: "owned spell cast subset Ougi/Iop/Xelor; see combat modules",
    12889: "combat_melee.execute_unarmed",
    12847: "combat_bootstrap/combat_actor owned actor initialisation",
}
entries = []
for (direction, opcode), count in sorted(
    counts.items(), key=lambda x: (x[0][0], x[0][1] or -1)
):
    ms = messages.get((direction, opcode), [])
    a = actions.get((direction, opcode), {})
    b = bindings.get((direction, opcode), {})
    entry = dict(
        opcode=opcode,
        direction=direction,
        count=count,
        client_classes=[m["class"] for m in ms],
        schema=a.get(
            "schema", "Native codec calls below; semantic field interpretation pending"
        ),
        native_codec=[
            dict(
                class_name=m["class"],
                fields=m.get("fields", []),
                inherited_fields=m.get("inherited_fields", []),
                calls=m.get("codec_calls", []),
            )
            for m in ms
        ],
        mapped=bool(ms),
        action=b.get("literal_action", a.get("action")),
        implemented=False,
        implementation_status="Not individually verified by this coverage audit",
        untested=True,
        unknown_conditions=[
            "Handler semantics and authoritative server lifecycle not yet individually audited"
        ],
        client_consumers=[e for m in ms for e in callers[m["class"]]],
        source_evidence=[a.get("evidence", "catalog codec extraction")],
    )
    if opcode in reviewed:
        name, schema, flow, status, unknown = reviewed[opcode]
        entry.update(
            action=name,
            schema=schema,
            client_flow=flow,
            implementation_status=status,
            unknown_conditions=[unknown],
        )
        entry["source_evidence"] += [
            ".runtime/local/coverage-attack-*.txt"
            if opcode in (13130, 12477)
            else ".runtime/local/coverage-{chK,cFV,ckM,cjp,aTW}.txt"
        ]
    if opcode in implemented:
        entry.update(
            implemented=True,
            implementation_status=implemented[opcode],
            untested=False,
            unknown_conditions=[
                "Coverage is a supported subset; native states/conditions beyond audited profiles fail closed"
            ],
        )
    if opcode == 13130:
        entry.update(implemented=True, untested=False)
    entries.append(entry)
artifact = dict(
    jar_sha256=catalog["jar_sha256"],
    source_count=len(sources),
    unique_frame_count=len(seen),
    opcode_direction_pair_count=len(entries),
    deduplication="session/channel/capture_seq/time/direction/opcode",
    scope="All decoded official frames from both capture sessions and cumulative snapshots. Counts and schemas only; no authentication payloads. Client-consumer edges are source pointers, not proof of interpretation. Unknown implementation status means not individually audited, not necessarily absent.",
    sources=[str(p.relative_to(root)) for p in sources],
    events=entries,
    priority_backlog=[
        {
            "opcode": 13726,
            "task": "Implement owned effect-area spawn/trigger/despawn after tracing Qs/Qq and native action sequencing.",
        },
        {
            "opcode": 13753,
            "task": "Construct own external fight visibility instead of excluding captured external-fight packets.",
        },
        {
            "opcode": 13497,
            "task": "Trace cvY -> cjL effect-class/serialized payload application and rollback.",
        },
        {
            "opcode": 13560,
            "task": "Trace cvZ -> cjM: distinguish effect instance identity and application/removal semantics.",
        },
        {
            "opcode": 13130,
            "task": "Instrument cWi gates on client if request is not sent; do not invent pending ACK.",
        },
    ],
)
(root / "server/protocol/event-coverage.json").write_text(
    json.dumps(artifact, indent=2) + "\n"
)
print(
    f"{len(sources)} sources; {len(seen)} unique frames; {len(entries)} opcode/direction pairs"
)
