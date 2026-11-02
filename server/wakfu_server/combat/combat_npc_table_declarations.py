"""Normalized authoring for native constructor table listeners with any spell book."""
from copy import deepcopy
from functools import lru_cache


@lru_cache(maxsize=1)
def _declarations():
    from wakfu_server import native_catalog
    from .combat_npc_table_start_events import POLICY

    with native_catalog._database().connection() as db:
        rows = db.execute(
            "SELECT monster_reference,state_id,root_id,source_sha256,"
            "metadata_sha256,authority,source_uri "
            "FROM native_npc_constructor_table_listeners "
            "ORDER BY monster_reference,state_id,root_id"
        ).fetchall()
    result = {}
    for source in rows:
        row = dict(source)
        reference = row.pop("monster_reference")
        row["policy"] = POLICY
        result.setdefault(reference, []).append(row)
    return result


def constructor_table_declarations(reference):
    """Return independent declarations; their original state/effect hashes validate at admission."""
    return deepcopy(_declarations().get(reference, []))
