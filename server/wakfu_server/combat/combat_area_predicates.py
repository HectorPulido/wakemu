"""eNm/eOQ/eOC predicates over explicit native target forms and PV authority."""
from .combat_effect_area_geometry import contains_area_cell
from .combat_effect_area_queries import _rows


ENUTROF_DEPOSIT_TYPE = 12  # fbp.rNR.aIc(), not its enum ordinal (10).
_TARGET_FORMS = frozenset(("null", "area", "cell", "actor"))


def _target_rows(fight, target_kind, target_id):
    if target_kind not in _TARGET_FORMS:
        raise ValueError("Missing native area predicate target form")
    rows = _rows(fight)
    if target_kind == "area":
        if target_id is None:  # Qz.bda() explicitly null.
            return ()
        # eNm/eOQ/eOz read the selected Qq itself, without requesting its
        # state manager. Active rows already passed the Qs snapshot checks.
        for row in rows:
            if row["uid"] == target_id:
                if target_id in getattr(fight, "actors", {}):
                    raise ValueError("Native area/fighter identity collision")
                return (row,)
        from .combat_state_managers import retained_area_pv_row, registered_area_pv

        row = retained_area_pv_row(fight, target_id)
        if row is None:
            raise ValueError("Missing native selected Qz area authority")
        registered_area_pv(fight, target_id)
        return (row,)
    return rows


def _identity(row, key):
    value = row.get(key)
    if type(value) is not int:
        raise ValueError("Missing native registered area " + key)
    return value


def _area_identity(fight, *, key, value, target_kind, target_id=None, cell=None):
    if type(value) is not int:
        raise ValueError("Invalid native area identity argument")
    if target_kind not in _TARGET_FORMS:
        raise ValueError("Missing native area predicate target form")
    if target_kind == "actor":
        return False  # eNm/eOQ return -2 for non-Qz, non-aBn target forms.
    rows = _target_rows(fight, target_kind, target_id)
    if target_kind == "cell" and cell is None:
        raise ValueError("Missing native aBn area target cell")
    return any(
        _identity(row, key) == value
        and (target_kind != "cell" or contains_area_cell(row, cell))
        for row in rows
    )


def is_area_type(fight, *, area_type, target_kind, target_id=None, cell=None):
    """eNm: exact long aeV identity, without enum lookup or ownership filter."""
    return _area_identity(
        fight,
        key="native_type_id",
        value=area_type,
        target_kind=target_kind,
        target_id=target_id,
        cell=cell,
    )


def is_specific_area(fight, *, reference, target_kind, target_id=None, cell=None):
    """eOQ: exact long Qq.bct prototype identity, not a state or instance UID."""
    return _area_identity(
        fight,
        key="reference",
        value=reference,
        target_kind=target_kind,
        target_id=target_id,
        cell=cell,
    )


def is_own_deposit(
    fight,
    *,
    source_id,
    target_kind,
    pv_owner_query,
    target_id=None,
    cell=None,
    exclude_center=False
):
    """eOC inherits eOz: optional true selects center-only for aBn scans.

    pv_owner_query resolves eGj.dpu/Qp.bch recursively to a canonical PV
    identity, including explicit null. A controller ID is not that contract.
    """
    if type(exclude_center) is not bool:
        raise ValueError("Invalid native own-deposit boolean argument")
    if target_kind not in _TARGET_FORMS:
        raise ValueError("Missing native area predicate target form")
    if source_id is None:
        return False
    if target_kind == "actor":
        return False
    rows = _target_rows(fight, target_kind, target_id)
    if not callable(pv_owner_query):
        raise ValueError("Missing native eII.aT PV owner authority")
    if target_kind == "cell" and cell is None:
        raise ValueError("Missing native own-deposit aBn cell")
    source_owner = pv_owner_query(source_id)
    for row in rows:
        if _identity(row, "native_type_id") != ENUTROF_DEPOSIT_TYPE:
            continue
        if "owner_id" not in row:
            raise ValueError("Missing native Qp.bch PV owner presence")
        if pv_owner_query(row["owner_id"]) != source_owner:
            continue
        if target_kind == "cell":
            if exclude_center:
                center = row.get("cell")
                if center is None:
                    raise ValueError("Missing native Qq.baM center")
                if tuple(center[:2]) != tuple(cell[:2]):  # aBn.Y compares X/Y.
                    continue
            if not contains_area_cell(row, cell):
                continue
        return True
    return False


def is_own_area(
    fight,
    *,
    source_id,
    target_kind,
    pv_owner_query,
    target_id=None,
    cell=None,
    exclude_center=False
):
    """eOz: optional true selects center-only in cell form; all Qq types."""
    if type(exclude_center) is not bool or target_kind not in _TARGET_FORMS:
        raise ValueError("Invalid native own-area argument/target form")
    if source_id is None or target_kind == "actor":
        return False
    if not callable(pv_owner_query):
        raise ValueError("Missing native eII.aT owner authority")
    if target_kind == "cell" and cell is None:
        raise ValueError("Missing native own-area cell")
    owner = pv_owner_query(source_id)
    for row in _target_rows(fight, target_kind, target_id):
        if "owner_id" not in row:
            raise ValueError("Missing native Qp.bch owner presence")
        if pv_owner_query(row["owner_id"]) != owner:
            continue
        if target_kind == "cell":
            if exclude_center:
                center = row.get("cell")
                if center is None:
                    raise ValueError("Missing native Qq.baM center")
                if tuple(center[:2]) != tuple(cell[:2]):
                    continue
            if not contains_area_cell(row, cell):
                continue
        return True
    return False
