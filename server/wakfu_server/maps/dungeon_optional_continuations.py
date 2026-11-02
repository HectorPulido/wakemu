"""Reviewed native traversal after an independently committed optional victory.

Projection leaves the pinned configuration, encounter rooms and activation
receipt unchanged. The existing optional encounter result is its durable
publication outbox; packets never award loot, consume a source or move actors.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import struct


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def rules():
    return tuple(
        json.loads(
            Path(__file__)
            .with_name("dungeon_optional_continuation_rules.json")
            .read_text()
        )["rules"]
    )


def scene_enabled(map_id):
    return any(r["map_id"] == map_id for r in rules())


@lru_cache(maxsize=8)
def _native_binding(key, rule_hash, release):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    matches = [r for r in rules() if r["key"] == key and digest(r) == rule_hash]
    if len(matches) != 1 or release != matches[0]["qualified_native_release"]:
        raise ValueError("Optional continuation native source changed")
    rule = matches[0]
    door = rule["door"]
    source = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(door["source_id"])
    )
    state = native_catalog.record(
        DATA_ROOT / "native-interactive-states.json", "objects", str(door["source_id"])
    )
    if (
        source is None
        or state is None
        or source["type"] != "Door"
        or source["map_id"] != rule["map_id"]
        or state["type"] != "Door"
        or state["map_id"] != rule["map_id"]
        or [source[k] for k in ("x", "y", "z")] != door["position"]
        or source["payload_hex"] != door["payload_hex"]
        or state["payload_hex"] != door["state_payload_hex"]
    ):
        raise ValueError(
            "Optional continuation door differs from original native source"
        )
    return rule


def _rule(key, rule_hash):
    from wakfu_server import native_catalog

    return _native_binding(key, rule_hash, native_catalog.release())


def _views(topology):
    for view in topology.get("_optional_continuations", ()):
        rule = _rule(view["rule_key"], view["rule_sha256"])
        if (
            type(view.get("opened")) is not bool
            or type(view.get("instance_id")) is not int
            or view["instance_id"] <= 0
            or type(view.get("revision")) is not int
            or view["revision"] < 0
            or topology["asset_map_id"] != rule["map_id"]
        ):
            raise ValueError("Optional continuation view is not authoritative")
        yield rule, view


def project_configuration(db, run, config):
    """Derive traversal from durable victory, including an already pinned v5 run."""
    matches = [
        r
        for r in rules()
        if r["route_key"] == config["route"]["key"]
        and config["compiled_plan"]["document_sha256"] in r["plan_hashes"]
    ]
    if not matches:
        return config
    topology = config["topology"]
    geometry = topology["exploration_geometry"]
    source = topology.get("native_unadmitted_side_content", {})
    views = []
    cells = set(map(tuple, geometry["cells"]))
    edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
    for raw in matches:
        rule = _rule(raw["key"], digest(raw))
        metadata = source.get("source_geometry", {})
        if (
            config["route"]["definition_id"] != rule["definition_id"]
            or topology["asset_map_id"] != rule["map_id"]
            or metadata.get("complete_native_source_file_sha256")
            != rule["source_geometry_sha256"]
            or metadata.get("native_topology_sha256") != rule["native_topology_sha256"]
            or digest(sorted(source.get("not_admitted_cells", ())))
            != rule["archived_cells_sha256"]
            or digest(
                dict(cells=sorted(geometry["cells"]), edges=sorted(geometry["edges"]))
            )
            != rule["baseline_geometry_sha256"]
        ):
            raise ValueError(
                "Optional continuation lacks its frozen native side-floor proof"
            )
        progress = db.execute(
            "SELECT status,catalog_hash FROM dungeon_room_runs WHERE instance_id=%s",
            (run["instance_id"],),
        ).fetchone()
        receipt = db.execute(
            "SELECT * FROM dungeon_optional_access WHERE instance_id=%s",
            (run["instance_id"],),
        ).fetchone()
        if (
            progress is None
            or progress["catalog_hash"] != config["compiled_plan"]["document_sha256"]
        ):
            raise ValueError("Optional continuation lost its pinned mandatory run")
        if receipt is not None and (
            receipt["catalog_hash"] != progress["catalog_hash"]
            or receipt["asset_map_id"] != rule["map_id"]
            or receipt["room_order"] != rule["room_order"]
            or receipt["source_order"] != rule["source_order"]
            or receipt["status"] not in ("available", "active", "victory")
        ):
            raise ValueError("Optional continuation has a conflicting victory receipt")
        opened = receipt is not None and receipt["status"] == "victory"
        if opened and progress["status"] != "completed":
            raise ValueError(
                "Optional continuation cannot precede mandatory completion"
            )
        view = dict(
            rule_key=rule["key"],
            rule_sha256=digest(rule),
            instance_id=run["instance_id"],
            opened=opened,
            revision=0 if receipt is None else receipt["revision"],
        )
        views.append(view)
        if opened:
            cells.update(map(tuple, rule["cells"]))
            edges.update((tuple(a), tuple(b)) for a, b in rule["edges"])
    effective = dict(
        topology,
        _optional_continuations=tuple(views),
        exploration_geometry=dict(geometry, cells=sorted(cells), edges=sorted(edges)),
    )
    return dict(config, topology=effective)


def extra_cells(topology):
    return frozenset(
        tuple(c)
        for rule, view in _views(topology)
        if view["opened"]
        for c in rule["cells"]
    )


def extra_cell_rooms(topology):
    return {
        tuple(c): rule["owner_room"]
        for rule, view in _views(topology)
        if view["opened"]
        for c in rule["cells"]
    }


def object_room(topology, source):
    for rule, view in _views(topology):
        if (
            view["opened"]
            and source.get("map_id") == rule["map_id"]
            and source.get("id")
            in (rule["door"]["source_id"], rule["chest"]["source_id"])
        ):
            return rule["owner_room"]
    return None


def packets(topology):
    """Append after ordinary bootstrap: restore original chest==1 presentation."""
    from wakfu_server.dungeon_object_states import state_payload

    result = []
    for rule, view in _views(topology):
        payload = state_payload(
            visible=not view["opened"],
            usable=False,
            state_id=0 if view["opened"] else 1,
        )
        result.append(
            (
                12344,
                struct.pack(">qH", rule["door"]["source_id"], len(payload)) + payload,
            )
        )
        if view["opened"]:
            native = rule["presentation"]
            result.append(
                (
                    13411,
                    struct.pack(
                        ">BiiB", 0, native["victory_event_id"], native["scenario_id"], 0
                    ),
                )
            )
    return tuple(result)


def publish_pending(store, *, instance_id, publish):
    """Retry the committed optional-victory result; acknowledge only delivery."""
    from wakfu_server import dungeon_runtime

    with store.connection() as db:
        row = db.execute(
            "SELECT e.fight_id,e.result,e.result_revision,a.revision AS optional_revision "
            "FROM dungeon_room_encounters e JOIN dungeon_optional_access a USING(instance_id) "
            "JOIN dungeon_instances i USING(instance_id) WHERE e.instance_id=%s AND i.status='active' "
            "AND e.encounter_scope='optional' AND e.status='victory' AND a.status='victory' "
            "AND e.result_revision=a.revision "
            "AND NOT EXISTS(SELECT 1 FROM dungeon_room_encounters busy JOIN combat_fights f ON f.id=busy.fight_id "
            "WHERE busy.instance_id=e.instance_id AND busy.status='active' AND f.status IN ('placement','active')) "
            "ORDER BY e.fight_id DESC LIMIT 1",
            (instance_id,),
        ).fetchone()
        if row is None:
            return False
        _, config = dungeon_runtime.configuration_for_instance(db, instance_id)
        views = [view for _, view in _views(config["topology"]) if view["opened"]]
        if not views:
            return False
        token = digest(views)
        if row["result"].get("optional_continuation_publication") == token:
            return False
        outgoing = packets(config["topology"])
    if not outgoing or any(
        publish(config["topology"]["asset_map_id"], instance_id, opcode, payload)
        is not True
        for opcode, payload in outgoing
    ):
        return False
    with store.connection() as db:
        db.execute(
            "UPDATE dungeon_room_encounters SET result=result || jsonb_build_object('optional_continuation_publication',%s::text) "
            "WHERE fight_id=%s AND instance_id=%s AND encounter_scope='optional' AND status='victory' "
            "AND result_revision=%s",
            (token, row["fight_id"], instance_id, row["optional_revision"]),
        )
    return True
