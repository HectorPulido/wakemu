"""Account for every native passive root before qualifying a state subset."""
from wakfu_server.equipment_stats import _flat, passive_null_marker
from .combat_equipment_snapshot_roles import _relic_aura


def unplanned_passive_effect_ids(reference, parent, supplied_roots, *, templates):
    """Keep unrelated unknown passive execution deferred, never silently lost.

    Existing flat/selected-element snapshot evaluators retain their ownership.
    Active/nonzero variants remain separate item actions. The only other
    skipped root is the already source-qualified zero-static relic aura.
    """
    identities = {row["id"]: row for row in templates[reference]["effects"]}
    supplied = set(supplied_roots)
    blocked = []
    for root in parent["roots"]:
        identity = identities[root["reference"]]
        if (
            type(identity.get("native_variant")) is not int
            or type(identity.get("native_active_effect")) is not bool
        ):
            raise ValueError("Missing complete native passive root identity")
        if identity["native_variant"] != 0 or identity["native_active_effect"]:
            continue
        if root["reference"] in supplied:
            continue
        if (
            _flat(identity) is not None
            or passive_null_marker(identity)
            or identity["generic"] in (1068, 1069)
            or _relic_aura(root)
        ):
            continue
        blocked.append(root["reference"])
    return tuple(blocked)
