"""eLI/eLK identifiers from the actual event source Qe, never its listener.

eII.aU selects eZR.fSd first, then eVt.fLP. eLI returns fyW.guI or0;
eLK returns source.baZ.awM (runner action family), not aZE definition ID.
"""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS


@lru_cache(maxsize=1)
def zone_trigger_policies():
    from wakfu_server.combat_published_catalogs import compilation_mode
    from wakfu_server.native_catalog_document import load_published_document

    data = (
        protocol_catalog.load(DATA_ROOT / "native-zone-trigger-policies.json")
        if compilation_mode()
        else load_published_document("native-zone-trigger-policies.json")
    )
    if data.get("schema") != 1 or data.get("source_count") != len(
        data.get("effects", {})
    ):
        raise ValueError("Incomplete native zone policy population")
    return data["effects"]


def source_identifiers(retention, effect, invocation, *, synthetic_authority=None):
    if synthetic_authority is not None:
        from .combat_collision_source import NativeCollisionSourceAuthority

        if type(synthetic_authority) is not NativeCollisionSourceAuthority:
            raise ValueError("Unverified native synthetic identifier authority")
        return synthetic_authority.identifiers(effect, invocation)
    descriptor, identity = retention.container(invocation)
    present = descriptor["container_present"]
    if type(present) is not bool:
        raise ValueError("Native source container presence required")
    container = {"present": present}
    if present:
        kind = descriptor["container_type"]
        if type(kind) is not int:
            raise ValueError("Native source container kind required")
        direct = None if invocation is None else invocation.native_retained_container
        is_area = (
            kind == 3
            and invocation is not None
            and invocation.state_uid is None
            and isinstance(direct, dict)
            and direct.get("native_kind") == "effect_area"
        )
        if is_area:
            row = getattr(retention.fight, "native_effect_areas", {}).get(identity)
            if row is None:
                row = getattr(retention.fight, "native_retired_area_managers", {}).get(
                    identity
                )
            if (
                row is None
                or row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
            ):
                raise ValueError("Missing actual Qq source container")
            container.update(type=3, native_type=3, is_state=False)
        else:
            container.update(type=kind, is_state=kind == 1)
        if kind == 1:
            if type(identity) is not int:
                raise ValueError("Native fyW packed identity required")
            raw = (identity >> 16) & 65535
            container["state_id"] = raw - 65536 if raw >= 32768 else raw
    action = effect["effect_class"]
    if type(action) is not int or not -(1 << 31) <= action < (1 << 31):
        raise ValueError("Native source awM action required")
    flags = effect.get("native_effect_flags")
    if flags is not None and (
        not isinstance(flags, (list, tuple))
        or any(type(flag) is not int or flag < 0 for flag in flags)
    ):
        raise ValueError("Invalid actual source definition REP flags")
    result = {
        "native_container": container,
        "effect_action_id": action,
        "effect_flags": None if flags is None else tuple(flags),
        "native_definition_present": True,
        "native_definition_variant": effect.get("variant"),
    }
    if invocation is not None:
        row = zone_trigger_policies().get(str(invocation.reference))
        if (
            not isinstance(row, list)
            or len(row) != 3
            or row[0] != action
            or any(type(v) is not bool for v in row[1:])
        ):
            raise ValueError("Missing native source zone policy")
        result["zone_trigger_policy"] = {
            "definition_present": True,
            "zone_flag": row[1],
            "point_area": row[2],
        }
    return result


def condition_identifiers(source):
    if source is None:
        return dict(triggering_effect_present=False)
    if not isinstance(source, dict):
        raise ValueError("Native triggering source required")
    result = dict(triggering_effect_present=True)
    is_state_runner = source.get("native_source_is_eWu")
    if is_state_runner is not None:
        if type(is_state_runner) is not bool:
            raise ValueError("Invalid actual source eWu type")
        result["triggering_source_is_eWu"] = is_state_runner
        if is_state_runner:
            reference = source.get("native_apply_state_reference")
            if type(reference) is not int or not -32768 <= reference <= 32767:
                raise ValueError("Missing actual source eWu.ejo reference")
            result["triggering_apply_state_reference"] = reference
    definition_present = source.get("native_definition_present")
    if definition_present is not None:
        if type(definition_present) is not bool:
            raise ValueError("Invalid native source definition presence")
        result["triggering_effect_definition_present"] = definition_present
    variant = source.get("native_definition_variant")
    if variant is not None:
        if type(variant) is not int or not -(1 << 63) <= variant < (1 << 63):
            raise ValueError("Invalid actual source PK variant")
        result["triggering_effect_variant"] = variant
    status = source.get("native_execution_status")
    if status is not None:
        if type(status) is not int or not -128 <= status <= 127:
            raise ValueError("Invalid actual source execution status")
        result["triggering_effect_execution_status"] = status
    blocked = source.get("native_execution_blocked")
    if blocked is not None:
        if type(blocked) is not bool:
            raise ValueError("Invalid source blocked predicate")
        if status is not None and blocked != (status == 7):
            raise ValueError("Source blocked predicate differs from execution status")
        result["triggering_effect_blocked"] = blocked
    policy = source.get("zone_trigger_policy")
    if policy is not None:
        if (
            not isinstance(policy, dict)
            or type(policy.get("definition_present")) is not bool
        ):
            raise ValueError("Invalid native zone definition presence")
        if not policy["definition_present"]:
            result["triggering_zone_effect"] = False
        elif any(type(policy.get(k)) is not bool for k in ("zone_flag", "point_area")):
            raise ValueError("Incomplete native source zone policy")
        else:
            result["triggering_zone_effect"] = (
                policy["zone_flag"] or not policy["point_area"]
            )
    flags = source.get("effect_flags")
    if flags is not None:
        if not isinstance(flags, (list, tuple)) or any(
            type(flag) is not int or flag < 0 for flag in flags
        ):
            raise ValueError("Invalid native source definition REP flags")
        result["triggering_effect_flags"] = frozenset(flags)
    reference = source.get("generic_effect")
    if reference is not None:
        if type(reference) is not int or not -(1 << 31) <= reference < (1 << 31):
            raise ValueError("Invalid native running-effect definition")
        result["triggering_effect_reference_id"] = reference
    value = source.get("value")
    if value is not None:
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Invalid native running-effect value")
        result["triggering_effect_value"] = value
    action = source.get("effect_action_id")
    if action is not None:
        if type(action) is not int or not -(1 << 31) <= action < (1 << 31):
            raise ValueError("Invalid native awM action")
        result["triggering_effect_action_id"] = action
    container = source.get("native_container")
    if container is None:
        return result  # Unknown metadata is not a null container.
    if not isinstance(container, dict) or type(container.get("present")) is not bool:
        raise ValueError("Invalid native source container")
    if not container["present"]:
        result["triggering_container_type"] = 0
        result["triggering_container_is_state"] = False
    else:
        kind = container.get("type")
        if kind is not None:
            if type(kind) is not int or not -(1 << 31) <= kind < (1 << 31):
                raise ValueError("Invalid native source container eVo.aZY")
            # Serialized PL discriminator is native eVo.aZY: fyW=1,
            # effect-area=3, fnR item=12, fyG=11/25. It is not cmZ (level).
            native_type = container.get("native_type")
            if native_type is not None:
                if type(native_type) is not int:
                    raise ValueError("Invalid explicit native PL.aZY")
                result["triggering_container_type"] = native_type
            elif kind in (1, 3, 11, 12, 25):
                result["triggering_container_type"] = kind
    if container["present"] and type(container.get("is_state")) is bool:
        result["triggering_container_is_state"] = container["is_state"]
        if container["is_state"]:
            reference = container.get("state_id")
            if type(reference) is not int or not -32768 <= reference <= 32767:
                raise ValueError("Native fyW.guI short reference required")
            result["triggering_container_state_id"] = reference
    return result
