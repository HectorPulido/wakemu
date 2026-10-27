"""Authorize installed RanchEntrance choices without trusting client destinations."""
import struct

from wakfu_server import world_static
from wakfu_server.haven_ranch import ACTIONS, destination


def portal_target(
    character,
    bag,
    body,
    *,
    validate_lease,
    validate_entitlement,
    geometry,
    installed=None
):
    """Resolve a native choice after current connection and scene authorization.

    The caller validates the live actor lease under its existing transaction.
    Geometry is the current immutable native map export, prepared beforehand.
    """
    if len(body) != 12:
        raise ValueError("Invalid native ranch interaction length")
    source_id, action, parameter = struct.unpack(">qHH", body)
    if bag is None or not bag.owns(character):
        raise ValueError("Ranch choices require the live haven bag")
    validate_lease()
    sources = [
        row
        for row in world_static.objects(9)
        if row["id"] == source_id and row["type"] == "RanchEntrance"
    ]
    if len(sources) != 1 or action not in ACTIONS or parameter != 0:
        raise ValueError("Unknown native ranch source or choice")
    source = sources[0]
    if source.get("map_id") != 9 or geometry.get("map_id") != 9:
        raise ValueError("Ranch source geometry identity mismatch")
    actor_cell = tuple(character[key] for key in ("x", "y", "z"))
    if actor_cell not in {tuple(cell) for cell in geometry["cells"]}:
        raise ValueError("Ranch actor is outside native walkable terrain")
    if (
        character["z"] != source["z"]
        or abs(character["x"] - source["x"]) + abs(character["y"] - source["y"]) > 1
    ):
        raise ValueError("Ranch entrance is out of reach")
    if not bag.is_owner:
        # Native cXN visitors use ACTIVATE(0), distinct from an owner's biome2.
        if action != 0:
            raise ValueError("Visitors may only enter the host ranch")
        return destination(35, installed)
    target = destination(action, installed)
    validate_entitlement()
    return target


def biome_target(
    character, session, body, *, validate_lease, validate_entitlement, installed=None
):
    """Native12380 may switch only an already authorized owned ranch scene."""
    if (
        len(body) != 4
        or session is None
        or not session.owns(character)
        or not session.parent.is_owner
    ):
        raise ValueError("Ranch biome change requires an active owned ranch")
    validate_lease()
    (biome,) = struct.unpack(">i", body)
    actions = [action for action, candidate in ACTIONS.items() if candidate == biome]
    if len(actions) != 1:
        raise ValueError("Unknown installed ranch biome")
    target = destination(actions[0], installed)
    validate_entitlement()
    return target


def validate_return(character, session, body, *, validate_lease):
    """Native13982 false exits; never accept a guessed context or trailing bytes."""
    if body != b"\x00" or session is None or not session.owns(character):
        raise ValueError("Invalid native ranch return")
    validate_lease()


def require_owned_entitlement(store, account_id, generation, character):
    """Check current selected inventory/role without replacing private position.

    Native biome1 requires item32864 possession or ACCESS_ADMIN_DATA. The trusted
    account administrator role supplies that permission; captured wire bits and
    caller-provided inventory never authorize this check. This predicate consumes
    nothing and must not guard returning from an already entered private scene.
    """
    from wakfu_server.environment_interactions import _guard
    from wakfu_server.inventory_items import _lease
    from wakfu_server.combat_inventory_date_conditions import owned_item_quantity
    from wakfu_server.characters.exploration_secrets import account_quantity

    if character.get("account_id") != account_id:
        raise ValueError("Foreign Ranch entitlement owner")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character["id"])
        _guard(db, character["id"])
        saved = store.character(account_id, character["id"], db)
        if saved.get("id") != character["id"] or saved.get("account_id") != account_id:
            raise ValueError("Invalid Ranch entitlement ownership")
        administrator = saved.get("account_is_admin")
        if type(administrator) is not bool:
            raise ValueError("Missing trusted Ranch administrator authority")
        if administrator:
            return
        quantity = owned_item_quantity(saved.get("inventory_items"), (32864,))
        quantity = (
            (quantity + account_quantity(saved, (32864,)) + 2**31) % 2**32
        ) - 2**31
        if quantity < 1:
            raise ValueError(
                "Para entrar en el merkalugar necesitas Bioma Esmeralda (32864) "
                "de tu cuenta. Revisa el inventario de misión de cuenta. "
                "No se consume al entrar."
            )
