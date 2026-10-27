"""Resolve eXt's actual source PV without manufacturing fighter resources."""


def native_damage_source(fight, identity):
    from .combat_native_actor_lookup import native_actor
    from .combat_state_managers import registered_area_pv, retained_area_pv_row

    actor = native_actor(fight, identity)
    if actor is not None:
        return actor
    source = registered_area_pv(fight, identity)
    if source is None:
        raise ValueError("Missing actual native eXt source PV")
    row = retained_area_pv_row(fight, identity)
    # faP/faY inherit faV's absent PA contract. Other Qq subclasses have
    # independent characteristic constructors and require their own adapters.
    if row.get("native_area_contract") not in ("faP", "faY"):
        raise ValueError("Unsupported native damage source PA contract")
    if source.native_is_area is not True or source.native_characteristics is not None:
        raise ValueError("Changed native faV source PA contract")
    return source


def plain_area_source(source):
    return getattr(source, "native_is_area", False) is True
