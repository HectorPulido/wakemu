"""Bonus for the current effect-free authoritative player snapshot.

Native eRN returns zero for absent PLANTATION_PROBABILTY entries. This provider
must be replaced when personal/running profession effects are implemented;
profession level does not grant an implicit planting bonus.
"""


def current(prepared):
    from .wire import EMPTY_SECTIONS, ENTITY_DEFAULTS

    expected = {"PERSONAL_EFFECTS": bytes(6), "RUNNING_EFFECTS": bytes(2)}
    if any(
        name not in EMPTY_SECTIONS or ENTITY_DEFAULTS[name] != value
        for name, value in expected.items()
    ):
        raise ValueError("Authoritative profession effect bonus requires a provider")
    return 0


def resolver(store):
    """Supply native2000 from current selected equipment to planting arithmetic."""

    def resolve(prepared):
        from wakfu_server.profession_equipment_modifiers import modifiers

        character = prepared["character"]
        with store.connection() as db:
            return modifiers(
                store, db, character["id"], prepared["seed"]["profession_id"]
            )["plant_probability"]

    return resolve
