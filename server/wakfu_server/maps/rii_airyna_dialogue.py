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

# Native node 5787 also carries one "already done" entry per lesson. The
# installed client offers them exactly when the lesson objective is complete,
# which is the reviewed way to run an exercise again.
LESSON_BY_OPTION = {
    ORIENTATION: 10574,
    ELEMENT: 10575,
    DISTANCE: 10576,
    LINE_OF_SIGHT: 10608,
    AREA: 10609,
    MOVEMENT: 10610,
    STATES: 10611,
}
REPEAT_BY_OBJECTIVE = {
    10574: 13330,
    10575: 13331,
    10576: 13332,
    10608: 13333,
    10609: 13334,
    10610: 13335,
    10611: 13336,
}
LESSON_BY_REPEAT = {value: key for key, value in REPEAT_BY_OBJECTIVE.items()}
REPEAT_OPTIONS = set(LESSON_BY_REPEAT)


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
    if ROOT not in nodes or not (
        {EXIT, ORIENTATION, ELEMENT, DISTANCE, LINE_OF_SIGHT, AREA, MOVEMENT, STATES}
        | REPEAT_OPTIONS
    ) <= {choice["id"] for choice in nodes[ROOT]["choices"]}:
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
        if choice["id"] in REPEAT_OPTIONS:
            return bool(facts_provider().get(LESSON_BY_REPEAT[choice["id"]], False))
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
            (ROOT, option): 0
            for option in set(LESSON_BY_OPTION) | REPEAT_OPTIONS | {EXIT}
        },
        authorize_node=lambda node: node["id"] == ROOT,
        authorize_choice=choice_allowed,
    )
    return session, session.open(ROOT, speaker, authorize, speaker_type=kind)
