"""Narrow ordinary owned permanent state/null400 contracts, including native sex.

Native eHi.fuP/bY applies passive fnR roots to explicit SELF, independently of
root target-mask2. State children keep their own selectors, native HMI/flags,
retained generic IDs and existing eXE execution/removal. No item-ID allowlist,
stat bonus, default sex, appearance rewrite or unknown HMI route is supplied.
"""
import ast
from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion

_HMI_PHASES = frozenset(("rzc", "rzd", "rze", "rzf", "rzg", "rzh"))


def _hmi(actions, *, root):
    if not isinstance(actions, dict) or set(actions) != _HMI_PHASES:
        return False
    if any(not isinstance(rows, (tuple, list)) for rows in actions.values()):
        return False
    if root:
        return not any(actions.values())
    if actions["rzd"] or actions["rzg"]:
        return False
    # Original bfb.b uses fKV/rzc before application; bfb.c uses i/rze
    # for retained application. Both share the g/rzf native removal route.
    # The original cjj packet consumer supports either exact phase vector,
    # but simultaneous pre- and post-application would apply twice.
    if bool(actions["rzc"]) and bool(actions["rze"]):
        return False
    installed = actions["rzc"] or actions["rze"]
    if installed != actions["rzf"] or installed != actions["rzh"]:
        return False
    # Pn/Px/Pp/Pk -> bfb use independent owned cosmetic stacks. Original
    # Pp hides equipment presentation, not its statistics or actor targeting.
    # Pk clamps visual scale in the original renderer and never changes the
    # native actor footprint. Keep every original action and phase intact.
    return all(
        isinstance(row, dict)
        and set(row) == {"id", "type", "native", "aYc", "aYd"}
        and type(row["id"]) is int
        and row["id"] > 0
        and row["type"]
        in (
            "COSTUME",
            "SKIN_PART_VISIBILITY",
            "HIDE_ALL_EQUIPMENTS",
            "SCALE_MODIFICATION",
        )
        and isinstance(row["native"], str)
        and bool(row["native"])
        and row["aYc"] is False
        and row["aYd"] is False
        for row in installed
    )


def _criterion(text):
    if type(text) is not str:
        return False
    if not text.strip():
        return True
    try:
        node = parse_local_criterion(text)
    except ValueError:
        return False

    def qualified(value):
        # Literal False is an original disabled branch, evaluated by the
        # existing criterion gate; its definition is preserved, not removed.
        if isinstance(value, ast.Constant) and value.value is False:
            return True
        if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.And):
            return all(qualified(child) for child in value.values)
        if isinstance(value, ast.Call):
            return (
                isinstance(value.func, ast.Name)
                and value.func.id == "IsSex"
                and len(value.args) == 1
                and not value.keywords
                and isinstance(value.args[0], ast.Constant)
                and value.args[0].value in ("male", "female")
            )
        if (
            not isinstance(value, ast.Compare)
            or len(value.ops) != 1
            or len(value.comparators) != 1
            or not isinstance(value.left, ast.Call)
            or not isinstance(value.left.func, ast.Name)
            or value.left.args
            or value.left.keywords
            or not isinstance(value.comparators[0], ast.Constant)
            or type(value.comparators[0].value) is not int
        ):
            return False
        name, threshold = value.left.func.id, value.comparators[0].value
        return (
            name == "GetNationId"
            and isinstance(value.ops[0], ast.Eq)
            and threshold in (30, 31, 32, 33)
        ) or (
            name == "GetGuildLevel"
            and isinstance(value.ops[0], ast.GtE)
            and threshold in (0, 3, 5, 7, 9)
        )

    return qualified(node)


def _metadata(effect, *, root):
    if not isinstance(effect, dict):
        return False
    required = {
        "criteria",
        "children",
        "target_masks",
        "native_target_selector",
        "native_effect_flags",
        "native_definition_class",
        "native_execution_mode",
        "native_timing_definition",
        "native_hmi_actions",
        "native_localization_enabled",
        "area_native",
        "area_class",
        "application_flag",
        "removal_flag",
        "probability_base",
        "probability_per_level",
        "parameters",
        "parameter_count",
        "variant",
        "minimum_level",
        "maximum_level",
        "effect_class",
    }
    if (
        not required <= effect.keys()
        or any(
            type(effect.get(key)) is not int
            for key in (
                "effect_class",
                "variant",
                "parameter_count",
                "minimum_level",
                "maximum_level",
            )
        )
        or not isinstance(effect.get("parameters"), (tuple, list))
    ):
        return False
    selector = effect["native_target_selector"]
    masks = effect["target_masks"]
    if (
        not isinstance(selector, dict)
        or selector.get("class") != "fcE"
        or not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(masks)
        or bool(effect["children"])
        or effect["variant"] != 0
        or (root and effect.get("native_active_effect") is not False)
        or effect["native_localization_enabled"] is not False
        or effect["application_flag"] != "NONE"
        or effect["removal_flag"] != "NONE"
        or effect["probability_base"] != 100
        or effect["probability_per_level"] != 0
        or type(effect["criteria"]) is not str
        or not isinstance(effect["native_effect_flags"], (tuple, list))
        or not _hmi(effect["native_hmi_actions"], root=root)
    ):
        return False
    timing = effect["native_timing_definition"]
    if not isinstance(timing, dict):
        return False
    if root:
        # These roots enter only through native eHi's explicit owned SELF call.
        return (
            selector.get("mask") in (0, 2)
            and (effect["area_native"], effect["area_class"])
            in (("empty", "anA"), ("point", "anD"))
            and effect["native_definition_class"] == "eVE"
            and effect["native_execution_mode"] == 0
            and tuple(effect["native_effect_flags"]) == ()
            and timing == {"clock_on_caster": False, "clock_on_target": True}
            and (
                not effect["criteria"].strip()
                or (
                    _criterion(effect["criteria"])
                    and isinstance(
                        parse_local_criterion(effect["criteria"]), ast.Compare
                    )
                    and parse_local_criterion(effect["criteria"]).left.func.id
                    == "GetGuildLevel"
                )
            )
        )
    # fcE bit1 is VALID_IF_IN_AOE, not SELF. The owned state centers
    # this exact anD point on its recipient; ordinary runtime selection
    # still enforces membership and UNTARGETTABLE_BY_OTHER.
    return (
        type(selector.get("mask")) is int
        and selector["mask"] in (0, 1)
        and effect["area_native"] == "point"
        and effect["area_class"] == "anD"
        # Original eXE.c is empty and neither eXE nor eZR consumes
        # BUFF_BYPASS_OUT_FIGHT_MAX17. Preserve the source flag rather
        # than rewriting it to CAN_BE_EXECUTED_ON_KO15; generic target
        # guards and the actual retained definition remain engine-owned.
        and tuple(effect["native_effect_flags"]) in ((15,), (17,))
        and (
            (effect["native_definition_class"], effect["native_execution_mode"])
            == ("eVy", 2)
            and timing
            == {
                "esr": False,
                "ryE": -1,
                "ryF": 0.0,
                "ryG": False,
                "ryH": 0,
                "ryI": 0.0,
                "clock_on_caster": False,
                "clock_on_target": True,
            }
            or (
                (effect["native_definition_class"], effect["native_execution_mode"])
                == ("eVH", 1)
                and timing
                == {
                    "rzv": -1,
                    "rzw": 0.0,
                    "clock_on_caster": False,
                    "clock_on_target": True,
                }
            )
        )
        and _criterion(effect["criteria"])
    )


def permanent_null_carrier_contract(source, compiled, registry):
    """Return None only for the fully described owned native304→null400 shape."""
    if source.get("attachment_field") is not None:
        return "null_carrier_requires_ordinary_passive_source"
    level = source.get("native_retained_container", {}).get("level")
    if type(level) is not int or not 0 <= level <= 32767 or not source.get("roots"):
        return "null_carrier_missing_owned_container_or_roots"
    if registry.get("effects", {}).get("400", {}).get("runner") != "eXE":
        return "null_carrier_missing_native_null_runner"
    for reference in source["roots"]:
        root = compiled.effects.get(str(reference))
        if not _metadata(root, root=True) or root["effect_class"] != 304:
            return "null_carrier_unqualified_root_metadata"
        if (
            root["parameter_count"] != 3
            or len(root["parameters"]) != 6
            or tuple(root["parameters"][1:]) != (0, 1, 0, -1, 0)
        ):
            return "null_carrier_unqualified_state_application"
        state_id, applied_level, chance = effect_profile(root, level)["parameters"]
        definition = compiled.source_states["states"].get(str(state_id))
        if (
            not isinstance(definition, dict)
            or type(definition.get("maximum_level")) is not int
            or not 1 <= definition["maximum_level"] <= 32767
            or applied_level != 1
            or chance != -1
        ):
            return "null_carrier_unqualified_state_level_domain"
        expected = {
            "refresh": False,
            "replace": True,
            "additive": False,
            "protected": False,
            "clock_actor": "target",
            "duration_base": -1,
            "duration_per_level": 0,
            "realtime_duration_base": -1000,
            "realtime_duration_per_level": 0,
            "tick_at_turn_end": False,
        }
        # eZk.bbX retains either original cxj value with these negative
        # clocks; schedule_state_timer creates no timer for duration -1.
        # Keep the actual flag in the state ledger and protocol payload.
        if type(definition.get("skip_turn_timer")) is not bool or any(
            definition.get(key) != value for key, value in expected.items()
        ):
            return "null_carrier_unqualified_state_clock_or_stack"
        for state_level in range(definition["maximum_level"] + 1):
            state = state_profile(compiled.source_states, state_id, state_level)
            if not state["effects"]:
                return "null_carrier_missing_native_children"
            for child in state["effects"]:
                effect = compiled.effects.get(str(child))
                if (
                    not _metadata(effect, root=False)
                    or effect["effect_class"] != 400
                    or effect["parameter_count"] != 0
                    or bool(effect["parameters"])
                ):
                    return "null_carrier_unqualified_child_metadata_or_hmi"
    return None
