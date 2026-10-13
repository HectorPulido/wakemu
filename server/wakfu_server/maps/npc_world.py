"""Server-configured conversational NPCs using native exploration appearance.

Positions and initial roots carry explicit SQL provenance. Captured identities
require an exact native contract and explicit local publication authorization.
Conversational actors are never registered as attackable monster groups.
"""
import struct

from .npc_dialogue import DialogueSession, catalog, interactions_enabled
from .npc_capture_contracts import authorized_identity
from . import npc_objective_facts, npc_protectors, npc_observed_dialogue

INTERACTION_REQUEST = 13222
MIN_ID = -4503599627370495
MAX_ID = -2251799813685248


def decode_interaction(body):
    if len(body) != 16:
        raise ValueError("NPC interaction must contain actor and action IDs")
    return struct.unpack(">qq", body)


def validate_placements(rows, native=None):
    native = catalog() if native is None else native
    speakers = {row["ref"]: row for row in native["speakers"]}
    nodes = {row["id"]: row for row in native["nodes"]}
    identities, positions = set(), set()
    for row in rows:
        identity = row["actor_id"]
        position = tuple(row[key] for key in ("map_id", "instance_id", "x", "y", "z"))
        if (
            type(identity) is not int
            or not (
                (MIN_ID <= identity <= MAX_ID and row.get("native_capture_id") is None)
                or authorized_identity(row)
            )
            or identity in identities
            or position in positions
        ):
            raise ValueError(
                "Invalid or duplicate conversational NPC identity/position"
            )
        if (
            any(type(value) is not int for value in position)
            or position[0] <= 0
            or position[1] < 0
            or not -(2**15) <= position[4] < 2**15
        ):
            raise ValueError("Invalid conversational NPC location")
        if not 0 <= row["direction"] <= 7 or not 1 <= row["interaction_range"] <= 12:
            raise ValueError("Invalid conversational NPC interaction policy")
        speaker = speakers.get(row["reference_id"])
        node = nodes.get(row["dialogue_root"])
        if (
            speaker is None
            or node is None
            or (
                node.get("criteria")
                and not (
                    authorized_identity(row)
                    and npc_objective_facts.supported(node["criteria"])
                )
            )
        ):
            raise ValueError("Unavailable native conversational NPC/root")
        # Explicit native portrait proves speaker compatibility when supplied.
        if node.get("native_cmT") not in ("", f"npc{row['reference_id']}"):
            raise ValueError("Native dialogue portrait differs from NPC reference")
        allowed = {action["id"] for action in speaker["actions"]}
        if (
            not row["action_ids"]
            or len(set(row["action_ids"])) != len(row["action_ids"])
            or not set(row["action_ids"]) <= allowed
        ):
            raise ValueError("NPC action is not a native dialogue action")
        npc_protectors.speaker(row)
        identities.add(identity)
        positions.add(position)
    return tuple(rows)


def load_scene(db, map_id, instance_id):
    rows = db.execute(
        "SELECT npc.*,row_to_json(contract) AS native_capture_contract, "
        "row_to_json(protector) AS native_protector_contract "
        "FROM world_dialogue_npcs npc LEFT JOIN native_captured_npc_contracts contract "
        "ON contract.actor_id=npc.native_capture_id "
        "LEFT JOIN native_captured_npc_protectors protector ON protector.actor_id=npc.native_capture_id "
        "WHERE npc.enabled AND npc.map_id=%s AND npc.instance_id=%s ORDER BY npc.actor_id",
        (map_id, instance_id),
    ).fetchall()
    return validate_placements(rows)


def nearby(character, row):
    return (
        (character["map_id"], character["instance_id"])
        == (row["map_id"], row["instance_id"])
        and abs(character["z"] - row["z"]) <= 1
        and abs(character["x"] - row["x"]) + abs(character["y"] - row["y"])
        <= row["interaction_range"]
    )


def spawn(row, native=None, language="es"):
    """Native eHj format11 carried by ctE12608, no player appearance patches.

    Uses the same verified exploration sections as combat_monster_world.world_actor;
    no combat stats or owned_instance are needed for a noncombat NPC.
    """
    native = catalog() if native is None else native
    validate_placements((row,), native)
    speaker = next(
        value for value in native["speakers"] if value["ref"] == row["reference_id"]
    )
    name = native["translations"][language][f"content.7.{row['reference_id']}"]
    name = name.encode("utf-8")
    if not name or len(name) > 65535:
        raise ValueError("Invalid native NPC name")
    level = max(1, speaker["min_level"])
    out = (
        b"\x0b"
        + struct.pack(">qBqH", row["actor_id"], 1, -1, len(name))
        + name
        + struct.pack(">h", row["reference_id"])
    )
    out += struct.pack(
        ">iihqBB", row["x"], row["y"], row["z"], row["map_id"], row["direction"], 0
    )
    out += b"\x01" + struct.pack(">hH", level, 0)
    out += b"\x00" + struct.pack(">iBBBBbB", -1, 0, 0, 0, 0, -1, 0)
    out += b"\x00"  # no world property overrides
    out += struct.pack(">qHhh", -row["actor_id"], 1, row["reference_id"], level)
    disabled_actions = (
        ()
        if interactions_enabled()
        else tuple(action["id"] for action in speaker["actions"])
    )
    out += struct.pack(">hhH", -1, -1, len(disabled_actions)) + b"".join(
        struct.pack(">i", action_id) for action_id in disabled_actions
    )
    out += bytes(2) + bytes(16) + bytes(3)  # movement, controller, scale, hero
    return 12608, b"\x00\x01" + struct.pack(">BqH", 1, row["actor_id"], len(out)) + out


def begin(
    character_provider,
    rows_provider,
    actor_id,
    action_id,
    native=None,
    facts_provider=None,
):
    """Bind a native initial conversation to current authoritative scene state.

    Exact observed display transitions are imported without quest/reward writes.
    Unobserved unconditional initial choices retain the local close behavior.
    This is explicit local behavior, not an inferred official quest transition.
    """
    native = catalog() if native is None else native
    rows = validate_placements(rows_provider(), native)
    row = next((value for value in rows if value["actor_id"] == actor_id), None)
    if (
        row is None
        or action_id not in row["action_ids"]
        or not nearby(character_provider(), row)
    ):
        raise ValueError("Unavailable nearby NPC dialogue action")
    nodes = {value["id"]: value for value in native["nodes"]}
    root = row["dialogue_root"]
    speaker = next(
        value for value in native["speakers"] if value["ref"] == row["reference_id"]
    )
    action = next(value for value in speaker["actions"] if value["id"] == action_id)

    def available(criteria):
        if not criteria:
            return True
        return (
            facts_provider is not None
            and authorized_identity(row)
            and npc_objective_facts.evaluate(
                criteria, character_provider(), facts_provider()
            )
        )

    if not available(action.get("criteria")):
        raise ValueError("Unavailable native NPC action criteria")
    graph = {
        (root, choice["id"]): None
        for choice in nodes[root]["choices"]
        if not choice.get("criteria")
    }
    graph.update(npc_observed_dialogue.graph(row, nodes))
    allowed_nodes = {root} | {
        target for target in graph.values() if target is not None and target != 0
    }
    session = DialogueSession(
        nodes,
        graph,
        authorize_node=lambda node: available(node.get("criteria")),
        authorize_choice=lambda choice: available(choice.get("criteria")),
    )

    speaker_type, speaker_identity = npc_protectors.speaker(row)

    def authorize(speaker_id, node_id):
        current = next(
            (value for value in rows_provider() if value["actor_id"] == actor_id), None
        )
        return (
            current is not None
            and current == row
            and speaker_id == speaker_identity
            and node_id in allowed_nodes
            and nearby(character_provider(), current)
            and available(action.get("criteria"))
            and available(nodes[root].get("criteria"))
        )

    return session, session.open(
        root, speaker_identity, authorize, speaker_type=speaker_type
    )


def protector_records(db, map_id, instance_id):
    """Publish only protectors from the same validated authoritative NPC scene."""
    return npc_protectors.records(load_scene(db, map_id, instance_id))


def matches_open_request(row, request):
    """Resolve either native speaker kind without equating protector and actor IDs."""
    kind, identity = npc_protectors.speaker(row)
    return (request["speaker_type"], request["speaker_id"], request["node_id"]) == (
        kind,
        identity,
        row["dialogue_root"],
    )
