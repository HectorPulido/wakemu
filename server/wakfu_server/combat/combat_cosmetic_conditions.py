"""Native cosmetic condition values for explicitly initialized actors.

eJi reads the selected values on eGj/eSU for categories 3..7 and otherwise
reads the active eSP list. eLX checks membership in that active list. A missing
component remains unknown; an empty mapping is an authoritative empty native
component.
"""
from dataclasses import dataclass
from collections.abc import Mapping

# fn.ce(int): MOUNT/PET_SKIN, PLAYER_COSTUME/SPRINT/FINISHER/AURA/TITLE,
# head/chest/shoulder/back/boots/weapon skins, HAVEN_BAG_SKIN, ACCESSORY.
_COSMETIC_TYPES = frozenset(range(1, 17))


@dataclass(frozen=True)
class NativeCosmeticState:
    is_native_fighter: bool | None
    selected_values: Mapping[int, object] | None
    active_cosmetics: Mapping[int, tuple[int, ...]] | None


def fresh_player_cosmetic_state(character):
    """Capture the local fresh PC's actual empty eSU/eSP constructor state.

    The client account cosmetic sections are initialized empty by this server.
    Appearance refs are not treated as equipped cosmetics; only currentTitle
    is the eSU title value exposed by the native getter.
    """
    if not isinstance(character, Mapping) or type(character.get("id")) is not int:
        raise ValueError("Missing owned fresh player cosmetic source")
    appearance = character.get("appearance")
    if appearance is None:
        appearance = {}
    if not isinstance(appearance, Mapping):
        raise ValueError("Malformed owned player appearance")
    title = appearance.get("currentTitle", 0)
    title = _int32(title, "appearance currentTitle")
    finishers = ()
    record = character.get("owned_cosmetics")
    if record is not None:
        from wakfu_server.characters.cosmetics import OwnedCosmetics

        account = OwnedCosmetics.from_record(
            record, account_id=character.get("account_id")
        )
        finishers = account.selected_finishers(character["id"])
    return {
        "selected_values": {3: 0, 4: 0, 5: finishers, 6: 0, 7: title},
        "active_cosmetics": {} if not finishers else {5: finishers},
    }


def initialize_fresh_player_cosmetics(actor, character):
    """Attach the server-owned constructor baseline to a fresh player actor."""
    if not getattr(actor, "controlled", False) or actor.id != character.get("id"):
        raise ValueError("Fresh cosmetic state requires its owned PC actor")
    if getattr(actor, "native_cosmetic_state", None) is not None:
        raise ValueError("Fresh actor already has cosmetic provenance")
    actor.native_cosmetic_state = fresh_player_cosmetic_state(character)


def _int32(value, label):
    if type(value) is not int:
        raise ValueError(f"Missing native {label} integer")
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def active_cosmetic_id(state, category):
    category = _int32(category, "cosmetic category")
    if state.is_native_fighter is False:
        return 0  # eJi.d returns 0 for non-eGj input.
    if state.is_native_fighter is not True:
        raise ValueError("Missing native eGj cosmetic actor identity")
    if category not in _COSMETIC_TYPES:
        return 0  # fn.ce returns null for unknown IDs; eSP's empty result is 0.
    if 3 <= category <= 7:
        values = state.selected_values
        if not isinstance(values, Mapping) or category not in values:
            raise ValueError("Missing native eSU selected cosmetic values")
        value = values[category]
        if category == 5:
            if not isinstance(value, (tuple, list)):
                raise ValueError("Missing native eSU finisher list")
            value = 0 if not value else value[0]
        return _int32(value, "selected cosmetic")
    active = state.active_cosmetics
    if not isinstance(active, Mapping):
        raise ValueError("Missing native eSP active cosmetic component")
    items = active.get(category, ())
    if not isinstance(items, (tuple, list)):
        raise ValueError("Malformed native eSP cosmetic list")
    return 0 if not items else _int32(items[0], "active cosmetic")


def has_active_cosmetic(state, category, cosmetic_id):
    category = _int32(category, "cosmetic category")
    cosmetic_id = _int32(cosmetic_id, "cosmetic id")
    if state.is_native_fighter is False:
        return False  # eLX returns -1 for non-eGj, i.e. false to eIX.
    if state.is_native_fighter is not True:
        raise ValueError("Missing native eGj cosmetic actor identity")
    if category not in _COSMETIC_TYPES:
        return False  # eLX's unknown fn yields its native false sentinel.
    active = state.active_cosmetics
    if not isinstance(active, Mapping):
        raise ValueError("Missing native eSP active cosmetic component")
    items = active.get(category, ())
    if not isinstance(items, (tuple, list)):
        raise ValueError("Malformed native eSP cosmetic list")
    return any(_int32(item, "active cosmetic") == cosmetic_id for item in items)
