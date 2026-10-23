"""Native fnE.EQUIP conditions, with explicit current sheet/unit ownership.

HasAnotherSameEquipment is eQb204/eLZ: same reference, DIFFERENT UID in
fpj/fpd or actual equipped fnZ. Inventory-bag duplicates are irrelevant.
"""
from wakfu_server import native_catalog as protocol_catalog
import ast
import json
import operator
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_local_criteria import parse_local_criterion


@lru_cache(maxsize=1)
def catalog():
    return protocol_catalog.load(DATA_ROOT / "item-equipment-conditions.json")["items"]


def evaluate(
    criteria,
    *,
    item,
    selected,
    owned,
    current_equipped=(),
    criterion_context=None,
    current_characteristics=None,
    maximum_characteristics=None
):
    """Evaluate EQUIP against an explicitly supplied current actor snapshot.

    GetCharac never derives bonuses here: the caller owns request-time versus
    post-application reconciliation. Native fnM supplies the same actor as
    caster and target, so those two selectors share this effective-current map.
    """
    root = parse_local_criterion(criteria)

    if criterion_context is not None:
        if (
            not isinstance(criterion_context, dict)
            or criterion_context.get("actor_kind")
            not in ("native_companion_npc", "player")
            or type(criterion_context.get("level")) is not int
            or not 0 <= criterion_context["level"] <= 32767
        ):
            raise ValueError(
                "Invalid explicit native companion or player equipment context"
            )

    player_context = (
        criterion_context is not None and criterion_context["actor_kind"] == "player"
    )
    if player_context:
        for field, expected in (
            ("real_level", int),
            ("breed_id", int),
            ("is_admin", bool),
        ):
            if (
                field in criterion_context
                and type(criterion_context[field]) is not expected
            ):
                raise ValueError("Invalid explicit native player equipment " + field)
        if (
            "real_level" in criterion_context
            and not 0 < criterion_context["real_level"] <= 32767
        ):
            raise ValueError("Invalid explicit native player equipment real_level")

    def player_value(name, expected):
        if not player_context or type(criterion_context.get(name)) is not expected:
            raise ValueError("Missing explicit native player equipment " + name)
        return criterion_context[name]

    def profession_values():
        levels = player_value("profession_levels", dict)
        if any(
            type(identity) is not int
            or not 0 < identity < (1 << 31)
            or type(level) is not int
            or not 0 <= level <= 32767
            for identity, level in levels.items()
        ):
            raise ValueError("Invalid explicit native equipment profession levels")
        return levels

    def completed_achievements():
        values = player_value("completed_achievements", tuple)
        if any(
            type(identity) is not int or not 0 < identity < (1 << 31)
            for identity in values
        ):
            raise ValueError("Invalid owned equipment achievement authority")
        return frozenset(values)

    def actor_value(name, expected):
        if (
            criterion_context is None
            or type(criterion_context.get(name)) is not expected
        ):
            raise ValueError("Missing explicit native equipment actor " + name)
        return criterion_context[name]

    def company_rank():
        if criterion_context is None or "company_snapshot" not in criterion_context:
            raise ValueError("Missing actual native equipment company authority")
        from wakfu_server.company_authority import CompanySnapshot, rank_for_snapshot

        record = criterion_context["company_snapshot"]
        if record is None:
            return rank_for_snapshot(None)
        snapshot = CompanySnapshot.from_record(record)
        snapshot.require_owner(actor_value("account_id", int))
        return rank_for_snapshot(snapshot)

    def equipped_reference(slot):
        # eKh reads the selected fpj sheet, returning reference or -1, never UID.
        # Proposed entries replace the current entry at the same native slot.
        for rows in (selected, current_equipped):
            for row in rows:
                if row["slot"] == slot:
                    other = owned.get(row["uid"])
                    if other is None:
                        raise ValueError(
                            "Equipment criterion references unavailable owned unit"
                        )
                    return other["reference"]
        return -1

    aliases = None
    if current_characteristics is not None or maximum_characteristics is not None:
        from wakfu_server.combat_characteristic_conditions import native_aliases

        aliases = native_aliases()
        native_ids = {row["id"] for row in aliases.values()}
        for values in (current_characteristics, maximum_characteristics):
            if values is not None and (
                not isinstance(values, dict)
                or not values
                or any(
                    type(identity) is not int
                    or identity <= 0
                    or identity not in native_ids
                    or type(value) is not int
                    or not -(2**31) <= value < 2**31
                    for identity, value in values.items()
                )
            ):
                raise ValueError("Invalid explicit native equipment characteristics")
        current_characteristics = (
            None if current_characteristics is None else dict(current_characteristics)
        )
        maximum_characteristics = (
            None if maximum_characteristics is None else dict(maximum_characteristics)
        )
    numeric_context = (
        criterion_context is not None
        or current_characteristics is not None
        or maximum_characteristics is not None
    )

    def characteristic(node):
        values = (
            current_characteristics
            if node.func.id == "GetCharac"
            else maximum_characteristics
        )
        if (
            values is None
            or node.keywords
            or not 1 <= len(node.args) <= 2
            or any(
                not isinstance(arg, ast.Constant) or type(arg.value) is not str
                for arg in node.args
            )
            or len(node.args) == 2
            and node.args[1].value.lower() not in ("caster", "target")
        ):
            raise ValueError(
                "Unsupported native equipment GetCharac context or selector"
            )
        row = aliases.get(node.args[0].value.upper())
        if row is None or type(row.get("id")) is not int:
            raise ValueError("Unknown native equipment characteristic")
        identity = row["id"]
        if identity not in values:
            raise ValueError("Missing native equipment characteristic authority")
        return values[identity]

    def check(node):
        if isinstance(node, ast.Constant) and (
            type(node.value) is bool or numeric_context and type(node.value) is int
        ):
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            check(node.operand)
            return
        if (
            numeric_context
            and isinstance(node, ast.UnaryOp)
            and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) is int
        ):
            return
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for value in node.values:
                check(value)
            return
        if isinstance(node, ast.IfExp):
            check(node.test)
            check(node.body)
            check(node.orelse)
            return
        if (
            numeric_context
            and isinstance(node, ast.Compare)
            and node.ops
            and all(
                type(op) in (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
                for op in node.ops
            )
        ):
            check(node.left)
            for value in node.comparators:
                check(value)
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("GetCharac", "GetCharacMax", "GetCharacteristicMax")
        ):
            characteristic(node)
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "HasAnotherSameEquipment"
            and not node.args
            and not node.keywords
        ):
            return
        if (
            criterion_context is not None
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and (
                node.func.id == "GetLevel"
                and not node.args
                or node.func.id == "GetRealLevel"
                and not node.args
            )
            and not node.keywords
        ):
            return
        if (
            criterion_context is not None
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "HasEquipmentId"
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is int
            and 0 < node.args[0].value < (1 << 31)
        ):
            return
        if (
            criterion_context is not None
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
            and node.func.id in ("GetCrimeScore", "GetNationId", "HasPvpRank")
        ):
            from wakfu_server.national_progression import (
                crime_score,
                nation_identity,
                has_pvp_rank,
            )

            args = node.args
            if any(
                not isinstance(arg, ast.Constant) or type(arg.value) is not int
                for arg in args
            ):
                raise ValueError("Invalid native national equipment arguments")
            if node.func.id == "GetNationId" and not args:
                nation_identity(criterion_context)
            elif node.func.id == "GetCrimeScore" and len(args) <= 1:
                crime_score(criterion_context, None if not args else args[0].value)
            elif node.func.id == "HasPvpRank" and len(args) == 1:
                has_pvp_rank(criterion_context, args[0].value)
            else:
                raise ValueError("Unsupported native national equipment predicate")
            return
        if (
            criterion_context is not None
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.args
            and not node.keywords
        ):
            if node.func.id == "GetCompanyRank":
                company_rank()
                return
            if node.func.id == "GetInstanceId":
                if not 0 <= actor_value("native_map_id", int) < (1 << 63):
                    raise ValueError("Invalid native equipment map definition")
                return
            if node.func.id == "IsDay":
                from wakfu_server.world_clock import daytime

                daytime(actor_value("world_time_ms", int))
                return
        if (
            criterion_context is not None
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "GetEquipment"
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is int
            and -(2**31) <= node.args[0].value < 2**31
        ):
            return
        if (
            player_context
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            name = node.func.id
            if name == "IsAchievementComplete" and len(node.args) == 1:
                arg = node.args[0]
                if (
                    not isinstance(arg, ast.Constant)
                    or type(arg.value) is not int
                    or not 0 < arg.value < (1 << 31)
                ):
                    raise ValueError("Invalid native equipment achievement identity")
                completed_achievements()
                return
            if name in ("GetCraftLevel", "HasCraft") and len(node.args) == 1:
                arg = node.args[0]
                if (
                    not isinstance(arg, ast.Constant)
                    or type(arg.value) is not int
                    or not -(1 << 31) <= arg.value < (1 << 31)
                ):
                    raise ValueError("Invalid native equipment profession argument")
                profession_values()
                return
            if name == "GetGuildLevel" and not node.args:
                if not 0 <= player_value("guild_level", int) <= 32767:
                    raise ValueError("Invalid native equipment guild level")
                return
            if name in ("GetWakfuGauge", "GetStasisGauge"):
                if len(node.args) > 1 or any(
                    not isinstance(arg, ast.Constant)
                    or type(arg.value) is not str
                    or arg.value.lower() not in ("caster", "target")
                    for arg in node.args
                ):
                    raise ValueError("Invalid native equipment gauge selector")
                field = "wakfu_gauge" if name == "GetWakfuGauge" else "stasis_gauge"
                if not -100 <= player_value(field, int) <= 100:
                    raise ValueError("Invalid native equipment gauge")
                return
            if name == "IsAdmin" and not node.args:
                player_value("is_admin", bool)
                return
            if (
                name == "IsBreed"
                and node.args
                and all(
                    isinstance(arg, ast.Constant) and type(arg.value) is str
                    for arg in node.args
                )
            ):
                player_value("breed_id", int)
                return
        raise ValueError(
            "Native equipment criteria evaluation is not implemented: " + criteria
        )

    def run(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return -run(node.operand)
            if isinstance(node.op, ast.UAdd):
                return run(node.operand)
            return not run(node.operand)
        if isinstance(node, ast.BoolOp):
            return (
                all(run(n) for n in node.values)
                if isinstance(node.op, ast.And)
                else any(run(n) for n in node.values)
            )
        if isinstance(node, ast.IfExp):
            return run(node.body if run(node.test) else node.orelse)
        if numeric_context and isinstance(node, ast.Compare):
            comparisons = {
                ast.Eq: operator.eq,
                ast.NotEq: operator.ne,
                ast.Lt: operator.lt,
                ast.LtE: operator.le,
                ast.Gt: operator.gt,
                ast.GtE: operator.ge,
            }
            left = run(node.left)
            result = True
            for operation, right_node in zip(node.ops, node.comparators):
                right = run(right_node)
                if type(left) is not int or type(right) is not int:
                    raise ValueError("Invalid native equipment numeric comparison")
                result = comparisons[type(operation)](left, right) and result
                left = right
            return result
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("GetCrimeScore", "GetNationId", "HasPvpRank"):
                from wakfu_server.national_progression import (
                    crime_score,
                    nation_identity,
                    has_pvp_rank,
                )

                if node.func.id == "GetNationId":
                    return nation_identity(criterion_context)
                if node.func.id == "GetCrimeScore":
                    return crime_score(
                        criterion_context, None if not node.args else node.args[0].value
                    )
                return has_pvp_rank(criterion_context, node.args[0].value)
            if node.func.id == "GetCompanyRank":
                return company_rank()
            if node.func.id == "IsAchievementComplete":
                return node.args[0].value in completed_achievements()
            if node.func.id == "GetInstanceId":
                return actor_value("native_map_id", int)
            if node.func.id == "IsDay":
                from wakfu_server.world_clock import daytime

                return daytime(actor_value("world_time_ms", int))
            if node.func.id == "GetCraftLevel":
                return profession_values().get(node.args[0].value, 0)
            if node.func.id == "HasCraft":
                identity = node.args[0].value
                return identity == 0 or identity in profession_values()
            if node.func.id == "GetGuildLevel":
                return player_value("guild_level", int)
            if node.func.id == "GetWakfuGauge":
                return player_value("wakfu_gauge", int)
            if node.func.id == "GetStasisGauge":
                return player_value("stasis_gauge", int)
            if node.func.id in ("GetCharac", "GetCharacMax", "GetCharacteristicMax"):
                return characteristic(node)
            if node.func.id == "IsAdmin":
                return player_value("is_admin", bool)
            if node.func.id == "IsBreed":
                from wakfu_server.combat_conditions import _NATIVE_BREED_NAMES

                # Original eNs ignores unknown names; caster and target are the
                # same actor for fnM equipment evaluation.
                breeds = {
                    _NATIVE_BREED_NAMES[arg.value.upper()]
                    for arg in node.args
                    if arg.value.upper() in _NATIVE_BREED_NAMES
                }
                return player_value("breed_id", int) in breeds
            if node.func.id == "GetEquipment":
                slot = ((node.args[0].value + 2**15) % 2**16) - 2**15
                return equipped_reference(slot)
            if node.func.id == "GetLevel" and not node.args:
                # eKH.GetLevel reads the native NPC actor level.
                return criterion_context["level"]
            if node.func.id == "GetRealLevel" and not node.args and not node.keywords:
                # A player's real progression level differs from modulation.
                return (
                    player_value("real_level", int)
                    if player_context
                    else criterion_context["level"]
                )
            if (
                node.func.id == "HasEquipmentId"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
            ):
                # eMl.a returns 0 for a match; amb.b interprets that as true.
                # Its default selector checks the selected actor's equipped slots.
                reference = node.args[0].value
                for row in (*selected, *current_equipped):
                    other = owned.get(row["uid"])
                    if other is None:
                        raise ValueError(
                            "Equipment criterion references unavailable owned unit"
                        )
                    if other["reference"] == reference:
                        return True
                return False
        for row in (*selected, *current_equipped):
            uid = row["uid"]
            other = owned.get(uid)
            if other is None:
                raise ValueError(
                    "Equipment criterion references unavailable owned unit"
                )
            if uid != item["uid"] and other["reference"] == item["reference"]:
                return True
        return False

    check(root)
    return run(root)
