"""Native croupier predicates backed by existing owned player components."""
import ast
import re

from wakfu_server.combat_local_criteria import parse_local_criterion
from wakfu_server.maps.dungeon_criteria import evaluate as evaluate_base


_OWNED_PREDICATES = frozenset(("HasCosmeticId", "HasGuildBonus", "GetNationId"))
_MISSING_PREDICATES = frozenset(("GetCrimeScore", "GetCompanyRank", "HasPvpRank"))


def _positive_argument(node):
    if (
        len(node.args) != 1
        or node.keywords
        or not isinstance(node.args[0], ast.Constant)
    ):
        raise ValueError("Invalid native exchange predicate arguments")
    value = node.args[0].value
    if type(value) is not int or not 0 < value < 2**31:
        raise ValueError("Invalid native exchange predicate identity")
    return value


def _cosmetic_owned(db, character, reference):
    from wakfu_server.characters.cosmetic_store import load

    owned = load(db, character["account_id"])
    if owned is None:
        raise ValueError("Missing native exchange cosmetic ownership authority")
    # eMf checks account eST ownership across eSP.rdE, excluding ACCESSORY16.
    # Current croupier references are ordinary owned cosmetics; no unverified
    # default haven-bag skin is granted by this predicate.
    return any(
        category != 16 and identity == reference
        for category, identity, _, _ in owned.items
    )


def _guild_bonus(db, character, reference, now_ms):
    from wakfu_server.characters.guild_economy import bonus_snapshot

    guild = db.execute(
        "SELECT g.id FROM guild_members m JOIN guilds g ON g.id=m.guild_id "
        "WHERE m.character_id=%s AND g.dissolved_at IS NULL",
        (character["id"],),
    ).fetchone()
    if guild is None:
        return False
    record = bonus_snapshot(db, guild["id"]).get(str(reference))
    if record is None:
        return False
    if not isinstance(record, dict) or type(record.get("active")) is not bool:
        raise ValueError("Malformed native exchange guild bonus authority")
    if not record["active"]:
        return False
    activated = record.get("activated_at_ms")
    if type(activated) is not int or activated <= 0:
        raise ValueError("Missing native exchange guild bonus activation date")
    # eMq -> bkZ -> fhU.s includes only a defined activation date <= now.
    return activated <= now_ms


def evaluate(db, store, character, expression):
    """Extend the unchanged base evaluator without fabricating missing systems."""
    if not isinstance(expression, str) or len(expression) > 32768:
        raise ValueError("Malformed native exchange criterion")
    queries = None
    if "IsAchievement" in expression:
        from wakfu_server.maps.dungeon_achievement_authority import (
            queries_from_snapshot,
        )

        row = db.execute(
            "SELECT snapshot FROM character_achievement_authority WHERE character_id=%s",
            (character["id"],),
        ).fetchone()
        queries = queries_from_snapshot(None if row is None else row["snapshot"])
    now_ms = int(store.clock() * 1000)
    if any(name in expression for name in _OWNED_PREDICATES | _MISSING_PREDICATES):
        source = re.sub(
            r'@\("[^"\n]+"\)\s*([^@]+)@', lambda match: "(" + match[1] + ")", expression
        )
        source = re.sub(r"#([^#]+)#", lambda match: "(" + match[1] + ")", source)
        if "@" in source or "#" in source:
            raise ValueError("Malformed native exchange criterion annotation")
        tree = parse_local_criterion(source)

        class OwnedPredicates(ast.NodeTransformer):
            def visit_Call(self, node):
                if not isinstance(node.func, ast.Name):
                    return self.generic_visit(node)
                name = node.func.id
                if name in _MISSING_PREDICATES:
                    raise ValueError(
                        "Missing native exchange predicate authority: " + name
                    )
                if name == "HasCosmeticId":
                    value = _cosmetic_owned(db, character, _positive_argument(node))
                elif name == "HasGuildBonus":
                    value = _guild_bonus(
                        db, character, _positive_argument(node), now_ms
                    )
                elif name == "GetNationId":
                    from wakfu_server.characters.nation_state import nation_id

                    if node.args or node.keywords or "nation_id" not in character:
                        raise ValueError("Missing native exchange nation authority")
                    value = nation_id(character)
                else:
                    return self.generic_visit(node)
                return ast.copy_location(ast.Constant(value=value), node)

        expression = ast.unparse(
            ast.fix_missing_locations(OwnedPredicates().visit(tree))
        )
    return evaluate_base(
        store, expression, character=character, queries=queries, now_ms=now_ms
    )
