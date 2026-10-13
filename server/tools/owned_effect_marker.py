"""Discover real owned casts that may establish a native retained Qf marker."""
import ast
from collections import ChainMap


def positive_markers(criterion):
    from wakfu_server.combat_local_criteria import parse_local_criterion

    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError, TypeError):
        return []
    if len(list(ast.walk(root))) > 256:
        return []

    def visit(node):
        if isinstance(node, ast.UnaryOp):
            return set()
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "HasEffectWithSpecificId"
            and not node.keywords
            and len(node.args) == 2
            and all(isinstance(a, ast.Constant) for a in node.args)
            and node.args[0].value == "caster"
            and type(node.args[1].value) is int
            and node.args[1].value > 0
        ):
            return {node.args[1].value}
        return set().union(*(visit(child) for child in ast.iter_child_nodes(node)))

    return sorted(visit(root))


def required_markers(criterion, document, spell=None, level=None):
    markers = set(positive_markers(criterion)) if criterion else set()
    if spell is None:
        return sorted(markers)
    record = document.get("spells", {}).get(str(spell))
    if not record or type(level) is not int or not 1 <= level <= len(record["levels"]):
        return []
    effects = ChainMap(
        document.get("effects", {}), document.get("baseline_effects", {})
    )
    todo = [(str(root), ()) for root in record["levels"][level - 1][2]]
    seen = set()
    while todo:
        key, path = todo.pop()
        if key in path:
            return []
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > 128:
            return []
        effect = effects.get(key)
        if not isinstance(effect, dict) or not isinstance(effect.get("criteria"), str):
            return []
        markers.update(positive_markers(effect["criteria"]))
        children = effect.get("children")
        if not isinstance(children, list):
            return []
        todo.extend((str(child), path + (key,)) for child in children)
    return sorted(markers)


def discover(
    abilities, criterion, document, *, limit=4, target_spell=None, target_level=None
):
    from wakfu_server.combat_effect_targets import native_selector_policy

    markers = set(required_markers(criterion, document, target_spell, target_level))
    recipes = []
    effects = ChainMap(
        document.get("effects", {}), document.get("baseline_effects", {})
    )
    for ability in abilities:
        spell, level = ability["spell_id"], ability["spell_level"]
        record = document.get("spells", {}).get(str(spell))
        if not record or not 1 <= level <= len(record["levels"]):
            continue
        minimum, maximum, roots = record["levels"][level - 1]
        if (minimum, maximum) != (0, 0):
            continue
        todo = [(str(root), ()) for root in roots]
        visited = 0
        found = []
        while todo and visited < 128:
            key, path = todo.pop()
            visited += 1
            if key in path:
                continue
            effect = effects.get(key)
            if effect is None:
                continue
            try:
                policy = native_selector_policy(effect)
            except ValueError:
                continue
            if "self" not in policy["relations"]:
                continue
            path = path + (key,)
            if effect.get("effect_class") == 330:
                todo.extend((str(child), path) for child in effect.get("children", []))
            elif (
                int(key) in markers
                and effect.get("effect_class") == 400
                and not effect.get("children")
            ):
                timing = effect.get("native_timing_definition", {})
                if (
                    timing.get("ryE", 0) < 0
                    and timing.get("ryF") == 0
                    and effect.get("criteria") == ""
                ):
                    found.append(
                        dict(effect_id=int(key), effect_path=list(map(int, path)))
                    )
        if todo:
            continue
        for marker in found:
            recipes.append(
                dict(
                    kind="owned_spell_sequence",
                    discovery="owned_retained_effect_marker_v1",
                    actions=[dict(spell_id=spell, target="caster", next_turn=True)],
                    native_producer_spell_level=level,
                    required_effect_id=marker["effect_id"],
                    native_producer_path=marker["effect_path"],
                )
            )
            if len(recipes) >= limit:
                return recipes
    return recipes


def recipes(reference, level, spell, criterion):
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_npc_attack import npc_spell_catalog

    abilities = native_abilities(reference, level)
    target = next((a for a in abilities if a["spell_id"] == spell), None)
    if target is None:
        return []
    return discover(
        [a for a in abilities if a["spell_id"] != spell],
        criterion,
        npc_spell_catalog(),
        target_spell=spell,
        target_level=target["spell_level"],
    )


def guard_provider(base, recipe, caster_id):
    from wakfu_server.combat_retained_runtime import native_retained_condition_effects

    class MarkerProvider(base):
        def preview(self, fight, action, action_id, *, forecast):
            if (
                action.get("spellId") != recipe["actions"][0]["spell_id"]
                or action.get("level") != recipe["native_producer_spell_level"]
                or action.get("targetId") != caster_id
            ):
                raise ValueError("Actual marker producer ownership/action changed")
            before = {
                row[2] for row in native_retained_condition_effects(fight, caster_id)
            }
            result = super().preview(fight, action, action_id, forecast=forecast)
            rows = native_retained_condition_effects(result.fight, caster_id)
            matched = [
                row
                for row in rows
                if row[0] == recipe["required_effect_id"]
                and row[1] == 400
                and row[2] not in before
            ]
            if not matched:
                raise ValueError(
                    "Actual owned cast supplied no new retained native effect marker"
                )
            self.native_marker_preparation_proof = matched
            return result

    return MarkerProvider


def verify_committed(fight, proof, caster_id):
    from wakfu_server.combat_retained_runtime import native_retained_condition_effects

    rows = native_retained_condition_effects(fight, caster_id)
    if not proof or any(tuple(row) not in rows for row in proof):
        raise ValueError("Committed native marker Qf identity differs")
    return [list(row) for row in proof]
