"""Suggest native conditional producers; actual transactions alone prove states."""
from collections import ChainMap


def discover_conditional_owned_state_recipes(
    abilities,
    required_states,
    document,
    *,
    limit=4,
    casting=None,
    companion_recipes=None
):
    from wakfu_server.combat_effect_targets import native_selector_policy

    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("Invalid bounded state recipe limit")
    states = set(required_states)
    if not states or any(type(s) is not int or s <= 0 for s in states):
        return []
    effects = ChainMap(
        document.get("effects", {}), document.get("baseline_effects", {})
    )
    recipes = []
    for ability in abilities:
        spell, level = ability["spell_id"], ability["spell_level"]
        record = document.get("spells", {}).get(str(spell))
        if (
            record is None
            or type(level) is not int
            or not 1 <= level <= len(record["levels"])
        ):
            continue
        minimum, maximum, roots = record["levels"][level - 1]
        ranged = (minimum, maximum) != (0, 0)
        companion_options = []
        if ranged:
            if companion_recipes is None or casting is None:
                continue
            companion_options = companion_recipes(
                casting.get(str(spell), {}).get("cast_criterion_raw", "")
            )
            if not companion_options:
                continue
        paths = []
        todo = [(str(r), (), ()) for r in roots]
        visited = 0
        while todo and visited < 128:
            key, path, criteria = todo.pop()
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
            if ranged and (
                policy["relations"] != frozenset({"self"}) or policy["in_area"]
            ):
                continue
            # These producer paths preserve literal point/self selection.
            if (effect.get("area_class"), effect.get("area_native")) != (
                "anD",
                "point",
            ):
                continue
            path = path + (key,)
            criterion = effect.get("criteria")
            if not isinstance(criterion, str) or len(criterion) > 2048:
                continue
            if criterion:
                criteria = criteria + ((key, criterion),)
            family = effect.get("effect_class")
            if family == 330:
                todo.extend(
                    (str(child), path, criteria) for child in effect.get("children", ())
                )
                continue
            raw = effect.get("parameters", [])
            if (
                family != 304
                or effect.get("variant") != 0
                or len(raw) < 2
                or raw[1] != 0
                or type(raw[0]) not in (int, float)
                or not float(raw[0]).is_integer()
            ):
                continue
            state = int(raw[0])
            if state in states:
                paths.append(
                    {
                        "state": state,
                        "effect_ids": list(map(int, path)),
                        "criteria": [
                            {"effect_id": int(k), "criterion": v} for k, v in criteria
                        ],
                        "native_selector": effect["native_target_selector"],
                    }
                )
        if todo:
            continue  # Incomplete bounded traversal supplies no recipe.
        if not states <= {p["state"] for p in paths}:
            continue
        if not any(
            p["criteria"] or p["native_selector"].get("mask") != 1 for p in paths
        ):
            continue
        contexts = companion_options if ranged else [None]
        for companion in contexts:
            for next_turn in (False, True):
                recipe = (
                    dict(companion)
                    if companion is not None
                    else {"kind": "owned_spell_sequence"}
                )
                recipe.update(
                    actions=[
                        {
                            "spell_id": spell,
                            "target": "native_opponent" if ranged else "caster",
                            "next_turn": next_turn,
                        }
                    ],
                    discovered_required_states=sorted(states),
                    discovery="owned_conditional_self_state_v1",
                    native_producer_spell_level=level,
                    native_producer_paths=paths,
                )
                if not ranged and casting is not None:
                    from owned_state_movement import requires_zero_mp_branch

                    if requires_zero_mp_branch(
                        casting.get(str(spell), {}).get("cast_criterion_raw", "")
                    ):
                        recipe["actions"][0]["prepare_zero_mp"] = True
                recipes.append(recipe)
                if len(recipes) >= limit:
                    return recipes
    return recipes


def verify_state_transaction(source_fight, preview, recipe, action, caster_id):
    """Guard the actual NativeProvider preview before its existing commit adopts it."""
    if (
        recipe.get("discovery") != "owned_conditional_self_state_v1"
        or action.get("type") != "cast"
        or action.get("targetId")
        != (
            -201
            if recipe["actions"][0].get("target") == "native_opponent"
            else caster_id
        )
        or action.get("spellId") != recipe["actions"][0]["spell_id"]
        or action.get("level") != recipe["native_producer_spell_level"]
    ):
        raise ValueError("Native state preparation ownership/action changed")
    transaction = getattr(preview, "spell", None)
    if transaction is None or not getattr(transaction, "outcomes", ()):
        raise ValueError("Native state preparation produced no actual root outcomes")
    actor = preview.fight.actors.get(caster_id)
    ledger = getattr(actor, "state_ledger", None)
    required = recipe["discovered_required_states"]
    events = transaction.events
    proof = []
    for state in required:
        matches = [
            e
            for e in events
            if e.get("kind") == "state_applied"
            and e.get("state_id") == state
            and e.get("actor_id") == caster_id
            and e.get("source_id") == caster_id
        ]
        entries = (
            []
            if ledger is None
            else [
                e
                for e in ledger.entries
                if e.reference == state
                and e.target_id == caster_id
                and e.caster_id == caster_id
            ]
        )
        matched = [e for e in entries if any(v.get("uid") == e.uid for v in matches)]
        if not matched:
            raise ValueError(
                "Actual conditional producer did not apply required caster state"
            )
        before = getattr(source_fight.actors[caster_id], "state_ledger", None)
        old = set() if before is None else {e.uid for e in before.entries}
        if any(e.uid in old for e in matched):
            raise ValueError("Native preparation reused prior state UID")
        proof.extend(
            {"state_id": state, "uid": e.uid, "level": e.level} for e in matched
        )
    return proof


def guarded_native_provider(base, recipe, caster_id):
    """One normal runtime preview, retaining its criteria/cost/RNG and transaction."""

    class StateCheckedProvider(base):
        def preview(self, fight, action, action_id, *, forecast):
            result = super().preview(fight, action, action_id, forecast=forecast)
            self.native_state_preparation_proof = verify_state_transaction(
                fight, result, recipe, action, caster_id
            )
            return result

    return StateCheckedProvider


def verify_committed_states(fight, proof, caster_id):
    ledger = getattr(fight.actors[caster_id], "state_ledger", None)
    entries = () if ledger is None else ledger.entries
    if not proof or any(
        not any(
            e.uid == p["uid"]
            and e.reference == p["state_id"]
            and e.target_id == caster_id
            for e in entries
        )
        for p in proof
    ):
        raise ValueError("Committed native state preparation receipt differs")
    return list(proof)
