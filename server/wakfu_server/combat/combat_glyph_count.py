"""ePo/ePi: count actual Qs.bdm type-zero areas, optionally by Qq.bch PV."""


def native_glyph_count(rows, *, actor_id=None, filter_owner=False):
    if type(filter_owner) is not bool or (
        actor_id is not None
        and (type(actor_id) is not int or not -(1 << 63) <= actor_id < (1 << 63))
    ):
        raise ValueError("Missing native glyph owner authority")
    count = 0
    for row in rows:
        if not isinstance(row, dict) or type(row.get("native_type_id")) is not int:
            raise ValueError("Missing native Qq.aeV type")
        if row["native_type_id"] != 0:
            continue
        if filter_owner:
            if "owner_id" not in row or (
                row["owner_id"] is not None and type(row["owner_id"]) is not int
            ):
                raise ValueError("Missing native Qq.bch owner")
            if actor_id is None or row["owner_id"] != actor_id:
                continue
        count += 1
    return count
