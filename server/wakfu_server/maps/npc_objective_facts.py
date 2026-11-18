"""Known native objective facts for NPC criteria, without quest progression.

Native bdO initializes every defined objective as incomplete. Unknown IDs are
not incomplete: native bdM.Bd raises, and our evaluator rejects them too.
GetInstanceId reads the POSITION world identity, represented by map_id here.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from functools import lru_cache
import re
import ast


class ObjectiveFacts(dict):
    """Objective values with independently validated owned quest authority."""

    def __init__(self, values=(), *, achievement_queries=None):
        super().__init__(values)
        self.achievement_queries = achievement_queries or {}


@lru_cache(maxsize=1)
def definitions():
    from .npc_catalog import document

    return frozenset(map(int, document("npc_objective_definitions")["objectives"]))


def load(db, account_id, character_id):
    """Load owned legacy facts and completed objectives from quest authority."""
    owner = db.execute(
        "SELECT id FROM characters WHERE account_id=%s AND id=%s",
        (account_id, character_id),
    ).fetchone()
    if owner is None:
        raise ValueError("NPC objective facts require an owned character")
    rows = db.execute(
        "SELECT objective_id,completed FROM npc_objective_facts "
        "WHERE account_id=%s AND character_id=%s",
        (account_id, character_id),
    ).fetchall()
    facts = ObjectiveFacts((row["objective_id"], row["completed"]) for row in rows)
    authority = db.execute(
        "SELECT snapshot FROM character_achievement_authority WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    if authority is not None:
        from wakfu_server.dungeon_achievement_authority import queries_from_snapshot

        snapshot = authority["snapshot"]
        # Validate the entire projection before trusting any of its facts.
        facts.achievement_queries = queries_from_snapshot(snapshot)
        for objective_id in snapshot["objectives"]:
            facts[objective_id] = True
    return facts


def supported(criteria, known=None):
    known = definitions() if known is None else known
    if not criteria:
        return True
    from wakfu_server.combat_local_criteria import parse_local_criterion

    try:
        tree = parse_local_criterion(criteria)
    except (ValueError, SyntaxError):
        return False

    def call(node, names):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in names
            and not node.keywords
        )

    def predicate(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            return all(predicate(value) for value in node.values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return predicate(node.operand)
        if call(
            node,
            {
                "IsAchievementObjectiveComplete",
                "IsAchievementComplete",
                "IsAchievementRunning",
                "IsAchievementActive",
            },
        ):
            if (
                len(node.args) != 1
                or not isinstance(node.args[0], ast.Constant)
                or type(node.args[0].value) is not int
                or node.args[0].value <= 0
            ):
                return False
            return (
                node.func.id != "IsAchievementObjectiveComplete"
                or node.args[0].value in known
            )
        if (
            not isinstance(node, ast.Compare)
            or len(node.ops) != 1
            or len(node.comparators) != 1
        ):
            return False
        right = node.comparators[0]
        if (
            not isinstance(right, ast.Constant)
            or type(right.value) is not int
            or right.value < 0
        ):
            return False
        if call(node.left, {"GetInstanceId"}):
            return not node.left.args and isinstance(node.ops[0], ast.Eq)
        if call(node.left, {"GetRealLevel"}) and isinstance(
            node.ops[0], (ast.GtE, ast.LtE)
        ):
            return not node.left.args or (
                len(node.left.args) == 1
                and isinstance(node.left.args[0], ast.Constant)
                and node.left.args[0].value == "caster"
            )
        return False

    return predicate(tree)


def evaluate(criteria, character, facts, known=None):
    """Reuse the native boolean evaluator with explicit owned fact authorities."""
    if not criteria:
        return True
    known = definitions() if known is None else known
    if not supported(criteria, known):
        return False
    normalized = criteria
    if "GetInstanceId" in criteria:
        identity = character.get("map_id")
        if type(identity) is not int or identity < 0:
            return False
        normalized = re.sub(r"\bGetInstanceId\(\)", str(identity), normalized)
    if "GetRealLevel" in criteria:
        level = character.get("level")
        if type(level) is not int or not 1 <= level <= MAX_CHARACTER_LEVEL:
            return False
        # NPC criteria name the owned actor explicitly; the shared dungeon
        # evaluator reads that same character through its no-argument form.
        normalized = re.sub(
            r"""\bGetRealLevel\(\s*(?:"caster"|'caster')\s*\)""",
            "GetRealLevel()",
            normalized,
        )

    def objective_complete(identity):
        value = facts.get(identity, False)
        if identity not in known or type(value) is not bool:
            raise ValueError("Unknown or malformed NPC objective fact")
        return value

    from wakfu_server import dungeon_criteria

    queries = dict(getattr(facts, "achievement_queries", {}))
    queries["IsAchievementObjectiveComplete"] = objective_complete
    try:
        return dungeon_criteria.evaluate(
            None, normalized, character=character, queries=queries
        )
    except ValueError:
        return False
