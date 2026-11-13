"""Safe returning Airyna dialogue after the reconstructed first lesson.

The elemental choice is exposed only after orientation and before completion;
other choices remain hidden until their corresponding encounters are available.
"""
from wakfu_server import npc_world, npc_protectors
from wakfu_server.npc_dialogue import DialogueSession, catalog


ACTOR = -1706442046308339
ACTION = 1389
ROOT = 5787
EXIT = 13329
ORIENTATION = 13322
ELEMENT = 13323
DISTANCE = 13324
LINE_OF_SIGHT = 13325
AREA = 13326
MOVEMENT = 13327
STATES = 13328


def begin(character_provider, rows_provider, facts_provider, actor_id, action_id):
    if actor_id != ACTOR or action_id != ACTION:
        return None
    character = character_provider()
    owner = (character["id"], character["account_id"])
    rows = npc_world.validate_placements(rows_provider())
    row = next((value for value in rows if value["actor_id"] == ACTOR), None)
    if (
        row is None
        or row["reference_id"] != 5460
        or row["map_id"] != 1388
        or not npc_world.nearby(character, row)
        or not facts_provider().get(10606, False)
    ):
        raise ValueError("Airyna is unavailable or out of range")
    nodes = catalog()["node_index"]
    if ROOT not in nodes or not {
        EXIT,
        ORIENTATION,
        ELEMENT,
        DISTANCE,
        LINE_OF_SIGHT,
        AREA,
        MOVEMENT,
        STATES,
    } <= {choice["id"] for choice in nodes[ROOT]["choices"]}:
        raise ValueError("Airyna returning dialogue differs from native data")
    kind, speaker = npc_protectors.speaker(row)

    def authorize(speaker_id, node_id):
        current = character_provider()
        latest = next(
            (value for value in rows_provider() if value["actor_id"] == ACTOR), None
        )
        return (
            speaker_id == speaker
            and node_id == ROOT
            and latest == row
            and (current.get("id"), current.get("account_id")) == owner
            and npc_world.nearby(current, row)
            and facts_provider().get(10606, False)
        )

    def choice_allowed(choice):
        if choice["id"] == EXIT:
            return True
        if choice["id"] == ORIENTATION:
            return not facts_provider().get(10574, False)
        if choice["id"] == ELEMENT:
            facts = facts_provider()
            return facts.get(10574, False) and not facts.get(10575, False)
        if choice["id"] == DISTANCE:
            facts = facts_provider()
            return facts.get(10575, False) and not facts.get(10576, False)
        if choice["id"] == LINE_OF_SIGHT:
            facts = facts_provider()
            return facts.get(10576, False) and not facts.get(10608, False)
        if choice["id"] == AREA:
            facts = facts_provider()
            return facts.get(10608, False) and not facts.get(10609, False)
        if choice["id"] == MOVEMENT:
            facts = facts_provider()
            return facts.get(10609, False) and not facts.get(10610, False)
        if choice["id"] == STATES:
            facts = facts_provider()
            return facts.get(10610, False) and not facts.get(10611, False)
        return False

    session = DialogueSession(
        nodes,
        {
            (ROOT, EXIT): 0,
            (ROOT, ORIENTATION): 0,
            (ROOT, ELEMENT): 0,
            (ROOT, DISTANCE): 0,
            (ROOT, LINE_OF_SIGHT): 0,
            (ROOT, AREA): 0,
            (ROOT, MOVEMENT): 0,
            (ROOT, STATES): 0,
        },
        authorize_node=lambda node: node["id"] == ROOT,
        authorize_choice=choice_allowed,
    )
    return session, session.open(ROOT, speaker, authorize, speaker_type=kind)
