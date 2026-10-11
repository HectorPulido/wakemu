"""Exact native inert state representation qualification, separate from casts."""
import hashlib
import json


def receipt_hash(receipt):
    return hashlib.sha256(
        json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def passive_state_identity(monster, level, spell, spell_level, document, casting):
    """Reconstruct a sole disabled304 root and exact native cle level identity."""
    from wakfu_server.combat_parameters import parameter_value
    from wakfu_server.combat_state_parameters import interpret_state_parameters
    from wakfu_server.combat_summon_initial_states import initial_state_plan
    from collections import ChainMap

    if (
        type(level) is not int
        or not monster["min_level"] <= level <= monster["max_level"]
    ):
        return None
    if type(spell_level) is not int or spell_level < 1:
        return None
    native = casting.get(str(spell), {})
    if native.get("cast_criterion_raw", "").strip() != "False":
        return None
    owned = [a for a in monster["native_abilities"] if a["spell_id"] == spell]
    maximum = native.get("maximum_level")
    if len(owned) != 1 or type(maximum) is not int or maximum < 1:
        return None
    requested = (
        level if owned[0]["level_parameter"] == -1 else owned[0]["level_parameter"]
    )
    if min(requested, maximum) != spell_level:
        return None
    record = document.get("spells", {}).get(str(spell), {})
    levels = record.get("levels", ())
    if spell_level > len(levels) or len(levels[spell_level - 1][2]) != 1:
        return None
    reference = str(levels[spell_level - 1][2][0])
    effect = ChainMap(
        document.get("effects", {}), document.get("baseline_effects", {})
    ).get(reference, {})
    if (
        effect.get("effect_class") != 304
        or effect.get("variant") != 0
        or effect.get("criteria", "").strip() != "False"
        or effect.get("children")
        or effect.get("native_target_selector") != {"class": "fcE", "mask": 0}
        or len(effect.get("parameters", ())) != 6
    ):
        return None
    try:
        parameters = [
            parameter_value(effect["parameters"], index, spell_level)
            for index in range(3)
        ]
        specification = interpret_state_parameters(parameters)
        plan = initial_state_plan(monster["initial_state_triples"], level)
    except (ValueError, TypeError, KeyError):
        return None
    matching = [
        state
        for state in plan
        if state.state_id == specification["reference"]
        and state.level == specification["level"]
    ]
    if len(matching) != 1:
        return None
    return dict(
        reference=monster["ref"],
        descriptor_level=level,
        spell_id=spell,
        spell_level=spell_level,
        root_effect_id=int(reference),
        state_id=specification["reference"],
        state_level=specification["level"],
        evaluated_state_parameters=parameters,
    )


def passive_initialization_proof(
    monster, level, spell, spell_level, document, casting, receipt, initialization_check
):
    identity = passive_state_identity(
        monster, level, spell, spell_level, document, casting
    )
    if identity is None or not initialization_check(
        monster["ref"], level, monster["initial_state_triples"], receipt
    ):
        return None
    return dict(
        schema="native-passive-initialization-proof-v1",
        **identity,
        initialization_receipt_sha256=receipt_hash(receipt),
        qualification="passive_initialization_only"
    )


def passive_case_proven(case, monster, document, casting, initialization_check):
    """Never accept a status label without rederiving source and receipt proof."""
    if (
        case.get("reference") != monster["ref"]
        or case.get("status") != "passive_initialization_only"
        or case.get("attempts") != 0
        or case.get("successful_targets") != []
        or case.get("errors") != {}
    ):
        return False
    for receipt in case.get("initialization_receipts", ()):
        try:
            expected = passive_initialization_proof(
                monster,
                case["level"],
                case["spell_id"],
                case["spell_level"],
                document,
                casting,
                receipt,
                initialization_check,
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            expected is not None
            and case.get("passive_initialization_proof") == expected
        ):
            return True
    return False


def effectful_cast_case(case):
    return case.get("status") == "validated" and any(
        target.get("effectful") is True for target in case.get("successful_targets", ())
    )
