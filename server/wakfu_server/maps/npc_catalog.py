"""PostgreSQL authority for imported native NPC catalogs; no file fallback."""
from wakfu_server.storage import native_catalog


def document(name):
    if name not in {
        "npc_dialogues",
        "npc_observed_dialogue_edges",
        "npc_objective_definitions",
    }:
        raise ValueError("Unknown native NPC catalog")
    with native_catalog._database().connection() as db:
        row = db.execute("SELECT value FROM settings WHERE name=%s", (name,)).fetchone()
    if row is None or not isinstance(row["value"], dict):
        raise RuntimeError("Missing PostgreSQL native NPC catalog: " + name)
    return row["value"]
