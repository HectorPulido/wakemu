"""Account for every native passive root before qualifying a state subset."""


def unplanned_passive_effect_ids(reference, parent, supplied_roots, *, templates):
    """Keep unrelated unknown passive execution deferred, never silently lost.

    Existing flat/selected-element snapshot evaluators retain their ownership.
    Active/nonzero variants remain separate item actions. The only other
    skipped root is the already source-qualified zero-static relic aura.
    """
    from .combat_equipment_root_roles import root_role

    identities = {row["id"]: row for row in templates[reference]["effects"]}
    supplied = set(supplied_roots)
    return tuple(
        root["reference"]
        for root in parent["roots"]
        if root["reference"] not in supplied
        and root_role(reference, root, identities[root["reference"]])
        == "runtime-operator"
    )
