"""Qualified native conversation facts; no inferred dialogue graph or NPC spawn.

Only a server-installed binding can connect a native quest objective to an
accredited conversation edge. No binding is synthesized from an objective's
compass marker, choice ordering, translated text, or proximity to a portal.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def placement_signature(row):
    return _digest(
        {
            key: row[key]
            for key in (
                "actor_id",
                "reference_id",
                "map_id",
                "instance_id",
                "x",
                "y",
                "z",
                "direction",
                "dialogue_root",
                "action_ids",
                "interaction_range",
            )
        }
    )


@dataclass(frozen=True)
class QualifiedConversation:
    quest_id: int
    objective_id: int
    reference_id: int
    action_id: int
    node_id: int
    choice_id: int
    placement_sha256: str
    native_definition_sha256: str

    def __post_init__(self):
        if any(
            type(getattr(self, key)) is not int or getattr(self, key) <= 0
            for key in (
                "quest_id",
                "objective_id",
                "reference_id",
                "action_id",
                "node_id",
                "choice_id",
            )
        ):
            raise ValueError("Invalid qualified native conversation identity")
        for key in ("placement_sha256", "native_definition_sha256"):
            value = getattr(self, key)
            if (
                type(value) is not str
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError("Missing qualified native conversation provenance")


def authorize_fact(character, row, session, binding, definition, *, node_id, choice_id):
    """Inspect the actually offered conversation; never advances the session.

    The caller reloads the authenticated character and locked NPC placement.
    The existing dialogue handler still owns its normal choose/graph operation.
    """
    from wakfu_server.npc_world import nearby

    if type(binding) is not QualifiedConversation:
        raise ValueError("Missing server-qualified conversation binding")
    if (
        definition.get("d") != binding.quest_id
        or _digest(definition) != binding.native_definition_sha256
        or placement_signature(row) != binding.placement_sha256
        or row["reference_id"] != binding.reference_id
        or binding.action_id not in row["action_ids"]
        or not nearby(character, row)
        or not row.get("enabled", False)
        or session.speaker_id != row["actor_id"]
        or session.node_id != binding.node_id
        or (node_id, choice_id) != (binding.node_id, binding.choice_id)
        or (node_id, choice_id) not in session.graph
        or not session.authorize_speaker(row["actor_id"], node_id)
    ):
        raise ValueError("Unqualified or stale native quest conversation")
    node = session._node(node_id)
    choice = next((c for c in node["choices"] if c["id"] == choice_id), None)
    if choice is None or not session.authorize_choice(choice):
        raise ValueError("Quest conversation choice was not offered")
    if binding.objective_id not in {o["d"] for o in definition["cjJ"]}:
        raise ValueError("Conversation objective is not native to its quest")
    return {
        "kind": "qualified_native_quest_conversation_v1",
        "character_id": character["id"],
        "account_id": character["account_id"],
        "quest_id": binding.quest_id,
        "objective_id": binding.objective_id,
        "speaker_id": row["actor_id"],
        "reference_id": binding.reference_id,
        "action_id": binding.action_id,
        "node_id": node_id,
        "choice_id": choice_id,
        "placement_sha256": binding.placement_sha256,
        "native_definition_sha256": binding.native_definition_sha256,
    }


def advance(state, fact, definition, *, character, store, now_ms):
    """Plan only the one authenticated quest transition and earned rewards.

    The native quest must already be running. This adapter does not invent an
    activation producer. Other quests, objectives and rewards remain untouched.
    Native availability and objective criteria are never bypassed.
    """
    from wakfu_server.dungeon_achievement_authority import queries_from_snapshot
    from wakfu_server import dungeon_criteria

    if (
        fact.get("kind") != "qualified_native_quest_conversation_v1"
        or fact.get("character_id") != character["id"]
        or fact.get("account_id") != character["account_id"]
        or _digest(definition) != fact.get("native_definition_sha256")
        or definition.get("d") != fact.get("quest_id")
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not False
        or type(now_ms) is not int
        or now_ms < 0
    ):
        raise ValueError("Invalid native conversation progress fact")
    identity = definition["d"]
    objectives = {r["d"]: r for r in definition["cjJ"]}
    if (
        len(objectives) != len(definition["cjJ"])
        or fact["objective_id"] not in objectives
    ):
        raise ValueError("Missing or duplicate native quest objective")
    candidate = deepcopy(state)
    if (
        identity in candidate["completed"]
        or fact["objective_id"] in candidate["objectives"]
    ):
        return candidate, [], [], []
    if identity not in candidate["running"]:
        raise ValueError("Native quest conversation prerequisite: quest is not running")
    queries = queries_from_snapshot(
        {k: candidate[k] for k in ("running", "completed", "objectives")}
    )
    objective = objectives[fact["objective_id"]]
    for criterion in (definition["cjI"], objective["ckc"], objective["cke"]):
        if not dungeon_criteria.evaluate(
            store, criterion, character=character, queries=queries
        ):
            raise ValueError("Native quest conversation prerequisite is not met")
    candidate["objectives"] = sorted(
        set(candidate["objectives"]) | {fact["objective_id"]}
    )
    completed, intents = [], []
    if set(objectives) <= set(candidate["objectives"]):
        candidate["running"].remove(identity)
        candidate["completed"] = sorted(set(candidate["completed"]) | {identity})
        candidate["completion_dates"][str(identity)] = now_ms
        candidate["recent"] = (
            candidate["recent"] + [{"id": identity, "date_ms": now_ms}]
        )[-255:]
        candidate["tracking"] = [i for i in candidate["tracking"] if i != identity]
        completed = [identity]
        intents = [(identity, deepcopy(r)) for r in definition["cjK"]]
    return candidate, intents, [fact["objective_id"]], completed


def settle(db, store, character, session, binding, definition, *, node_id, choice_id):
    """Settle an offered edge inside the existing authenticated action boundary.

    Caller owns the account/session action barrier, current position projection,
    normal session.choose call, transaction commit and packet delivery. This
    function is not a client-facing objective or quest-completion API.
    """
    from . import storage, wire
    from .service import _owner, drain_rewards

    _owner(db, character)
    row = db.execute(
        "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s AND enabled FOR SHARE",
        (session.speaker_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Quest NPC is not currently published")
    fact = authorize_fact(
        character,
        row,
        session,
        binding,
        definition,
        node_id=node_id,
        choice_id=choice_id,
    )
    before = storage.load_locked(db, character["id"])
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = advance(
        before,
        fact,
        definition,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if not objectives:
        return dict(applied=False, packets=[], completed=[], new_objectives=[])
    event_key = f"native-quest-conversation:{binding.quest_id}:{binding.objective_id}"
    if not storage.record_event(db, character["id"], event_key, fact):
        raise ValueError("Quest conversation receipt is missing its progress")
    for identity, reward in intents:
        storage.claim_reward(db, character["id"], identity, "once", reward["d"], reward)
    storage.store(db, character["id"], after)
    packets = wire.changes(
        character["id"], before, after, objectives, completed, now_ms
    )
    packets.extend(drain_rewards(db, store, character))
    return dict(
        applied=True, packets=packets, completed=completed, new_objectives=objectives
    )


def load_rules(db):
    """Read explicitly published native data and qualified edges; no fallback.

    Empty bindings are valid: recovered quest data does not authorize unknown
    NPC positions or conversation edges. Those edges stay unavailable.
    """
    row = db.execute(
        "SELECT value FROM settings WHERE name='native_quest_conversation_contracts'"
    ).fetchone()
    if row is None:
        raise ValueError("Missing published quest conversation contracts")
    return validate_rules(row["value"])


def validate_rules(document):
    """Validate a publication before installation or use."""
    if (
        type(document) is not dict
        or document.get("schema") != "native-quest-conversation-contracts-v1"
        or document.get("admission_policy") != "reconstructed_wakemu_qualified_talk_v1"
        or type(document.get("native_source_sha256")) is not dict
        or not document["native_source_sha256"]
        or type(document.get("definitions")) is not list
        or type(document.get("bindings")) is not list
    ):
        raise ValueError("Invalid published quest conversation contracts")
    for digest in document["native_source_sha256"].values():
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Invalid native quest data provenance")
    definitions = {}
    for definition in document["definitions"]:
        if (
            type(definition) is not dict
            or type(definition.get("cjJ")) is not list
            or type(definition.get("cjK")) is not list
            or not definition["cjJ"]
            or any(
                type(o) is not dict or type(o.get("d")) is not int or o["d"] <= 0
                for o in definition["cjJ"]
            )
        ):
            raise ValueError("Malformed published native quest definition")
        identity = definition.get("d")
        if (
            type(identity) is not int
            or identity <= 0
            or identity in definitions
            or definition.get("native_class") != "aJM"
        ):
            raise ValueError("Invalid or duplicate published native quest")
        definitions[identity] = definition
    bindings = {}
    for value in document["bindings"]:
        if type(value) is not dict:
            raise ValueError("Malformed published native conversation binding")
        try:
            binding = QualifiedConversation(**value)
        except TypeError as error:
            raise ValueError(
                "Malformed published native conversation binding"
            ) from error
        definition = definitions.get(binding.quest_id)
        if (
            definition is None
            or _digest(definition) != binding.native_definition_sha256
            or binding.objective_id not in {o["d"] for o in definition["cjJ"]}
        ):
            raise ValueError("Published conversation differs from native quest data")
        key = (
            binding.reference_id,
            binding.action_id,
            binding.node_id,
            binding.choice_id,
        )
        if key in bindings:
            raise ValueError("Duplicate published native quest conversation edge")
        bindings[key] = binding
    return definitions, bindings
