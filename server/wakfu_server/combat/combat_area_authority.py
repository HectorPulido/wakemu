"""Explicit Qq lifecycle guards, independent of fighter HP or Qs membership."""
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS


def area_guards(fight, identity):
    active = getattr(fight, "native_effect_areas", {})
    retired = getattr(fight, "native_retired_area_managers", {})
    if identity in active and identity in retired:
        raise ValueError("Area PV is both active and retired")
    from .combat_state_managers import retained_area_pv_row

    # Ordered Qe siblings can still hold this actual PV after Qs removes it.
    # The execution-local scope preserves its own Qq.b guard provenance.
    row = retained_area_pv_row(fight, identity)
    if (
        not isinstance(row, dict)
        or row.get("uid") != identity
        or row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
    ):
        raise ValueError("Missing registered native area PV")
    removed = row.get("native_qq_bhi")
    source = row.get("native_qq_guard_source")
    if (
        type(removed) is not bool
        or source not in ("Qq.constructor", "Qq.aWs", "Qq.aWr", "Qq.b")
        or removed != (source == "Qq.b")
    ):
        raise ValueError("Missing native Qq lifecycle guard provenance")
    return dict(baG=removed, baK=removed, baF=not removed)
