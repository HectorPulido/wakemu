"""Read-only roster projection from registered native fighter lifecycle."""


def hidden_snapshot_actor_ids(fight):
    from .combat_pve_departure import retired_pve_actor_ids
    from .combat_summon_retirement import retired_summon_ids
    from .combat_ordinary_qi_retirement import retired_ordinary_qi_ids
    from .combat_forced_retirement import retired_forced_fighter_ids

    hidden = set(retired_pve_actor_ids(fight) | retired_summon_ids(fight))
    if not hasattr(fight, "native_global_pv_collections"):
        return hidden
    from .combat_global_pv_collections import (
        global_fighter_registered,
        global_fighter_guards,
    )

    # Irreversible presentation removal must be backed by its actual native
    # lifecycle receipt. A naked OUT_OF_PLAY flag cannot hide a live/corpse
    # actor or release signed-byte roster capacity.
    completed = (
        hidden | retired_ordinary_qi_ids(fight) | retired_forced_fighter_ids(fight)
    )

    for identity in fight.actors:
        # A withdrawn registration and irreversible OUT_OF_PLAY are absent
        # from presentation. Reversible OFF_PLAY corpses remain reconnectable.
        if not global_fighter_registered(fight, identity):
            hidden.add(identity)
        elif global_fighter_guards(fight, identity)["baK"]:
            if identity not in completed:
                raise ValueError("Unverified native snapshot fighter retirement")
            hidden.add(identity)
    return hidden
