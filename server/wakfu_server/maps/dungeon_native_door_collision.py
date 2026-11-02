"""Native bEG/VD.a Door collision coordinates from ordered physical columns."""
from math import isfinite

from wakfu_server.combat_sn_path import NativeSnColumns


def native_blocking_cells(
    map_id, position, *, columns=None, expected_source_sha256=None
):
    """Resolve a closed Door without changing its serialized object position.

    VD.a counts every VB.a surface, including non-floor/through rows. Exactly
    one row sets the XY column bit; every other count sets the literal XYZ bit.
    Unknown publication coverage is rejected here as missing server authority;
    the native client instead logs when its topology chunk cannot be loaded.
    """
    if type(map_id) is not int or map_id <= 0:
        raise ValueError("Invalid native Door map identity")
    if (
        not isinstance(position, (tuple, list))
        or len(position) != 3
        or any(
            not (
                type(value) is int
                or type(value) is float
                and isfinite(value)
                and value.is_integer()
            )
            for value in position
        )
        or not all(-(1 << 31) <= value < (1 << 31) for value in position[:2])
        or not -32768 <= position[2] <= 32767
    ):
        raise ValueError("Invalid native Door position")
    if expected_source_sha256 is not None and (
        not isinstance(expected_source_sha256, str)
        or len(expected_source_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_source_sha256)
    ):
        raise ValueError("Invalid native Door physical source identity")
    if columns is None:
        columns = NativeSnColumns.from_published(map_id)
    if not isinstance(columns, NativeSnColumns) or columns.map_id != map_id:
        raise ValueError("Missing matching native Door physical columns")
    if (
        expected_source_sha256 is not None
        and columns.source_sha256 != expected_source_sha256
    ):
        raise ValueError("Native Door physical source changed")
    x, y, z = (int(value) for value in position)
    surfaces = columns.column(x, y)
    if surfaces is None:
        raise ValueError("Missing native Door physical topology chunk")
    return frozenset(((x, y, surfaces[0].z if len(surfaces) == 1 else z),))
