"""Source-qualified encounter callbacks excluded only from deliberate AI advice.

The actual owned book, native costs and native426 queued execution stay intact.
Scene authoring declares the distinction; original source paths qualify it.
"""
from functools import lru_cache
import hashlib
import json


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _source_node(node, compiled):
    kind, reference = node
    if kind == "state":
        row = compiled.source_states["states"].get(str(reference))
        if row is None:
            raise ValueError("Missing callback source state")
        return {
            "effects": list(row["effect_ids"]),
            "maximum_level": row["maximum_level"],
        }
    if kind == "area":
        from .combat_effect_area import native_effect_areas

        row = native_effect_areas().get(str(reference))
        if row is None or row.get("reference") != reference:
            raise ValueError("Missing callback source area")
        return {"effects": list(row["effect_ids"]), "definition": row}
    if kind == "spell":
        from .combat_native_spell_casting import native_casting_table

        row, index = native_casting_table(reference, 1)
        return {"effects": list(row["levels"][index][2])}
    if kind == "effect":
        row = compiled.effects.get(str(reference))
        if row is None:
            raise ValueError("Missing callback source effect")
        keys = (
            "effect_class",
            "children",
            "parameters",
            "parameter_count",
            "criteria",
            "target_masks",
            "native_target_selector",
            "native_timing_definition",
            "native_execution_mode",
            "application_flag",
            "removal_flag",
        )
        return {key: row.get(key) for key in keys}
    raise ValueError("Unknown callback source node")


def source_closure(record):
    """Validate typed native links and return the compact immutable witness."""
    from .combat_npc_attack import npc_runtime_catalog, npc_spell_catalog
    from .combat_definitions import effect_profile

    reference, initial = record.get("actor_reference"), record.get("initial_state")
    if type(reference) is not int or type(initial) is not int:
        raise ValueError("Missing callback constructor source")
    policy = npc_spell_catalog()["activation_policy"]["enabled_monsters"].get(
        str(reference)
    )
    if policy is None:
        raise ValueError("Missing callback actor admission")
    triples = policy.get("initial_state_triples", ())
    if initial not in triples[::3]:
        raise ValueError("Callback state is not owned by the native constructor")
    paths = record.get("paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 16:
        raise ValueError("Invalid callback source paths")
    compiled = npc_runtime_catalog(imported=True)
    nodes, callbacks = {}, set()
    for path in paths:
        if not isinstance(path, list) or not 3 <= len(path) <= 32:
            raise ValueError("Invalid callback source path length")
        converted = []
        for node in path:
            if (
                not isinstance(node, list)
                or len(node) != 2
                or node[0] not in ("state", "effect", "area", "spell")
                or type(node[1]) is not int
                or node[1] <= 0
            ):
                raise ValueError("Malformed callback source node")
            converted.append(tuple(node))
        if converted[0] != ("state", initial) or len(set(converted)) != len(converted):
            raise ValueError(
                "Callback source must start in its constructor without cycles"
            )
        if converted[-1][0] != "spell" or converted[-2][0] != "effect":
            raise ValueError("Callback source must end at a native queued spell")
        for node in converted:
            nodes[node] = _source_node(node, compiled)
        for before, after in zip(converted, converted[1:]):
            source = nodes[before]
            if before[0] in ("state", "area", "spell"):
                valid = after[0] == "effect" and after[1] in source["effects"]
            elif after[0] == "effect":
                valid = after[1] in source["children"]
            else:
                effect = compiled.effects[str(before[1])]
                parameters = effect_profile(effect, 1)["parameters"]
                expected = {"state": 304, "area": 315, "spell": 426}[after[0]]
                valid = (
                    effect["effect_class"] == expected
                    and parameters
                    and parameters[0] == after[1]
                )
            if not valid:
                raise ValueError("Callback source path is not a native link")
        if nodes[converted[-2]]["effect_class"] != 426:
            raise ValueError("Callback spell lacks its own native426 producer")
        callbacks.add(converted[-1][1])
    witness = {
        "actor_reference": reference,
        "initial_state": initial,
        "initial_state_triples": list(triples),
        "nodes": [[list(node), nodes[node]] for node in sorted(nodes)],
    }
    return witness, frozenset(callbacks)


@lru_cache(maxsize=128)
def _qualified(serialized, revision):
    record = json.loads(serialized)
    if record.get("native_revision") != revision:
        raise ValueError("Callback source native revision changed")
    witness, spells = source_closure(record)
    digest = hashlib.sha256(_canonical(witness).encode()).hexdigest()
    if digest != record.get("source_closure_sha256"):
        raise ValueError("Callback source closure changed")
    return spells


@lru_cache(maxsize=1)
def _layout_declarations():
    from wakfu_server import native_catalog

    with native_catalog._database().connection() as db:
        return tuple(
            dict(row)
            for row in db.execute(
                "SELECT p.*, COALESCE(jsonb_agg(jsonb_build_array("
                "n.node_order,n.node_kind,n.node_reference) ORDER BY n.node_order) "
                "FILTER (WHERE n.node_order IS NOT NULL), '[]'::jsonb) AS source_nodes "
                "FROM encounter_scripted_phase_spells p LEFT JOIN "
                "encounter_scripted_phase_spell_nodes n USING(policy,spell_reference) "
                "GROUP BY p.policy,p.spell_reference ORDER BY p.policy,p.spell_reference"
            ).fetchall()
        )


def _layout_source_path(row):
    """Decode one normalized representation without changing legacy witnesses."""
    nodes = row.get("source_nodes", [])
    legacy = row.get("source_effect_path")
    if not isinstance(nodes, list):
        raise ValueError("Malformed callback source node representation")
    if not nodes:
        if not isinstance(legacy, (list, tuple)) or not legacy:
            raise ValueError("Missing callback source path representation")
        return [
            ["state", row["initial_state"]],
            *[["effect", reference] for reference in legacy],
            ["spell", row["spell_reference"]],
        ]
    if legacy is not None:
        raise ValueError("Ambiguous callback source path representations")
    if (
        not isinstance(nodes, list)
        or not 3 <= len(nodes) <= 32
        or any(
            not isinstance(node, list)
            or len(node) != 3
            or type(node[0]) is not int
            or node[0] != order
            for order, node in enumerate(nodes, 1)
        )
    ):
        raise ValueError("Malformed ordered callback source nodes")
    path = [[kind, reference] for _, kind, reference in nodes]
    if path[0] != ["state", row["initial_state"]] or path[-1] != [
        "spell",
        row["spell_reference"],
    ]:
        raise ValueError("Callback source endpoints disagree with declaration")
    return path


def _layout_deliberate_spells(fight, owned, monsters):
    """Match normalized phase declarations to the actual original constructor.

    Reconstructed supreme layouts use a separate durable placement record from
    dungeon scenes. Exact layout and original initialization receipts bind the
    policy; transformed, summoned and historical profiles do not inherit it.
    """
    layout = getattr(fight, "native_encounter_scene_layout", None)
    actor = fight.current
    if not isinstance(layout, dict) or actor is None or actor.controlled:
        return owned
    monster = monsters.get(actor.id)
    if monster is None or getattr(actor, "native_summon_source", None) is not None:
        return owned
    excluded = set()
    for row in _layout_declarations():
        if (
            layout.get("policy") != row["layout_policy"]
            or layout.get("map_id") != row["map_id"]
            or row["actor_reference"] != monster.get("ref")
        ):
            continue
        from .combat_npc_attack import npc_spell_catalog
        from wakfu_server import native_catalog

        receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor.id)
        original = npc_spell_catalog()["activation_policy"]["enabled_monsters"].get(
            str(row["actor_reference"])
        )
        if (
            row["authority"] != "authorized_wakemu_native_content_reconstruction"
            or layout.get("authority") != row["layout_authority"]
            or layout.get("original_world_coordinates") is not False
            or monster.get("id") != actor.id
            or not isinstance(receipt, dict)
            or receipt.get("initialized") is not True
            or receipt.get("ref") != row["actor_reference"]
            or receipt.get("descriptor_level") != actor.effective_level
            or original is None
            or receipt.get("raw_triples") != original.get("initial_state_triples")
        ):
            raise ValueError(
                "Callback policy lacks its actual original scene constructor"
            )
        record = dict(
            actor_reference=row["actor_reference"],
            initial_state=row["initial_state"],
            native_revision=row["native_revision"],
            source_closure_sha256=row["source_closure_sha256"],
            paths=[_layout_source_path(row)],
        )
        excluded.update(_qualified(_canonical(record), native_catalog.release()))
    if not excluded <= owned.keys():
        raise ValueError("Callback spell missing from actual owned book")
    return {spell: level for spell, level in owned.items() if spell not in excluded}


def deliberate_spells(fight, owned, monsters):
    """Return advisory candidates; never change authoritative ownership."""
    from .combat_encounter_scene_policy import frozen_scene, scene_actor_binding

    owned = _layout_deliberate_spells(fight, owned, monsters)
    scene = frozen_scene(fight)
    if not isinstance(scene, dict) or "callback_owned_spells" not in scene:
        return owned
    if scene.get("authority") != "authorized_wakemu_native_content_reconstruction":
        raise ValueError("Missing reviewed encounter callback authority")
    records = scene["callback_owned_spells"]
    if not isinstance(records, list) or len(records) > 32:
        raise ValueError("Malformed encounter callback authoring")
    actor = fight.current
    if actor is None:
        return owned
    binding = scene_actor_binding(fight, actor, monsters)
    if binding is None:
        return owned
    monster = monsters[actor.id]
    from wakfu_server import native_catalog

    excluded = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Malformed encounter callback record")
        if record.get("actor_reference") != monster.get("ref"):
            continue
        if monster.get("id") != actor.id:
            raise ValueError("Callback actor constructor identity mismatch")
        excluded.update(_qualified(_canonical(record), native_catalog.release()))
    if not excluded <= owned.keys():
        raise ValueError("Callback spell missing from actual owned book")
    return {spell: level for spell, level in owned.items() if spell not in excluded}
