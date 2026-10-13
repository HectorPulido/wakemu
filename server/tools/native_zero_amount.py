"""Source-qualified native dormant variants; never convert a refusal to an effect."""
import hashlib
import json
from collections import ChainMap
from wakfu_server.combat.combat_parameters import parameter_value

STATUS = "native_zero_amount_unavailable"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def certificate(spell, level, document, registry):
    record = document.get("spells", {}).get(str(spell))
    if type(level) is not int or not record or not 1 <= level <= len(record["levels"]):
        return None
    roots = record["levels"][level - 1][2]
    if not roots:
        return None
    effects = ChainMap(
        document.get("effects", {}), document.get("baseline_effects", {})
    )
    closure = {}
    leaves = []
    todo = [(str(root), ()) for root in roots]
    while todo:
        if len(closure) >= 128:
            return None
        key, path = todo.pop()
        if key in path:
            return None
        effect = effects.get(key)
        if not isinstance(effect, dict):
            return None
        closure[key] = effect
        if effect.get("native_execution_mode") != 2 or effect.get(
            "native_effect_flags"
        ) != [17]:
            return None
        if effect.get("target_masks") != [None] * 7:
            return None
        timing = effect.get("native_timing_definition", {})
        if (
            timing.get("ryH") != 0
            or timing.get("ryI") != 0
            or timing.get("ryG") is not False
        ):
            return None
        family = effect.get("effect_class")
        children = effect.get("children")
        if not isinstance(children, list):
            return None
        if family == 330:
            if (
                not children
                or effect.get("parameters") != [0.0, 0.0]
                or timing.get("ryE") != 0
                or timing.get("ryF") != 0
            ):
                return None
            todo.extend((str(child), path + (key,)) for child in children)
            continue
        row = registry.get("effects", {}).get(str(family))
        if (
            children
            or not isinstance(row, dict)
            or row.get("runner") not in ("eWQ", "eWR")
            or row.get("zero_initial_amount_rejected") is not True
            or row.get("dynamic_stat") is not False
            or len(effect.get("parameters", [])) != 2
        ):
            return None
        try:
            amount = parameter_value(effect["parameters"], 0, level)
        except (ValueError, TypeError, OverflowError):
            return None
        if amount != 0:
            return None
        leaves.append(
            dict(
                effect_id=int(key),
                family=family,
                stat_id=row["fixed_stat_id"],
                amount=amount,
                native_guard="eWW.bbH.zero_initial_amount_rejected",
                registry_row_sha256=digest(row),
            )
        )
    if not leaves:
        return None
    return dict(
        schema="native-zero-initial-amount-proof-v1",
        spell_id=spell,
        spell_level=level,
        root_ids=roots,
        closure_sha256=digest(closure),
        registry_source_sha256=digest(
            {k: registry.get(k) for k in ("source", "client_jar_sha256")}
        ),
        leaves=sorted(leaves, key=lambda row: row["effect_id"]),
        qualification=STATUS,
        effectful=False,
    )


def classify(case, document, registry):
    proof = certificate(case["spell_id"], case["spell_level"], document, registry)
    if proof is None or case.get("status") == "validated":
        return case
    observations = [
        target
        for target in case.get("successful_targets", [])
        if target.get("effectful") is False
        and target.get("native_preview_source_unchanged") is True
        and target.get("packets", 0) > 0
        and target.get("outcomes")
        and all(outcome == "False" for outcome in target["outcomes"])
        and target.get("event_kinds") == ["npc_cast"]
    ]
    if not observations:
        return case
    case = dict(case)
    case.update(status=STATUS, native_zero_amount_proof=proof)
    return case


def proven(case, document, registry):
    if case.get("status") != STATUS:
        return False
    expected = certificate(
        case.get("spell_id"), case.get("spell_level"), document, registry
    )
    if expected is None or case.get("native_zero_amount_proof") != expected:
        return False
    return (
        classify(dict(case, status="pending"), document, registry).get("status")
        == STATUS
    )
