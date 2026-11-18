"""Publish shipped reconstructed combat archetypes without touching players.

This joins two reviewed, versioned manifests through the existing immutable
metadata and combat binding validator. Existing bindings are retained exactly.
One-shot quests accept on a matching authentic victory as an explicit local
reconstruction. Otomai IV-X requires the reviewed NPC's explicit acceptance.
Default is read-only validation; --apply writes configuration atomically.
"""

import argparse
import json
import os
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from tools.install_combat_mission_bindings import install as install_combat
from wakfu_server.achievements import combat_missions
from wakfu_server.postgres import Database

MANIFESTS = SERVER_ROOT / "wakfu_server/achievements/combat_mission_profiles"


def load_batch(root=MANIFESTS):
    """Combine shipped publications; an objective cannot have competing joins."""
    combined, revision = {}, None
    for name in ("one-shot-native-targets.json", "otomai-hunter-iv-x.json"):
        document = json.loads((root / name).read_text())
        if document.get("schema") != combat_missions.SETTING:
            raise ValueError("Unexpected mission archetype batch schema")
        if revision is not None and document["revision"] != revision:
            raise ValueError("Mission archetype batches use different native revisions")
        revision = document["revision"]
        for row in document["bindings"]:
            identity = row["objective_id"]
            if identity in combined:
                raise ValueError("Conflicting mission archetype batch objective")
            combined[identity] = row
    return {
        "schema": combat_missions.SETTING,
        "revision": revision,
        "bindings": [combined[key] for key in sorted(combined)],
    }


def install(db, *, apply=False, root=MANIFESTS):
    document = load_batch(root)
    result = install_combat(db, document, write=apply)
    return {
        **result,
        "incoming_objectives": len(document["bindings"]),
        "incoming_quests": len({row["quest_id"] for row in document["bindings"]}),
        "one_shot_complete_quests": sum(
            row.get("acceptance") != "explicit" for row in document["bindings"]
        ),
        "hunter_chain_quests": len(
            {
                row["quest_id"]
                for row in document["bindings"]
                if row.get("acceptance") == "explicit"
            }
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            print(json.dumps(install(db, apply=args.apply), sort_keys=True))
    finally:
        database.close()


if __name__ == "__main__":
    main()
