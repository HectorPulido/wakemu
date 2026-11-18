"""Compile or publish a reviewed archetype batch with existing mission producers.

The plan command is read-only. Install writes configuration only and does not
accept quests for players; --activate selects the immutable event publication.
Recurring quests must use the existing cycle-aware mission adapters instead.
"""

import argparse
import json
import os
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from wakfu_server.achievements import mission_archetypes, mission_toolkit
from wakfu_server.postgres import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "install"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--output", type=Path, help="Write compiled toolkit JSON")
    args = parser.parse_args()
    if args.activate and args.command != "install":
        parser.error("--activate requires install")
    document = json.loads(args.manifest.read_text())
    identities = mission_archetypes.referenced_quests(document)
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            revision = mission_toolkit._revision(db)
            rows = db.execute(
                "SELECT definition_id,data FROM native_quest_metadata_definitions "
                "WHERE revision=%s AND definition_id=ANY(%s)",
                (revision, identities),
            ).fetchall()
            native = {row["definition_id"]: row["data"]["native"] for row in rows}
            profile, summary = mission_archetypes.compile_profile(document, native)
            if args.output:
                args.output.write_text(
                    json.dumps(profile, indent=2, ensure_ascii=False) + "\n"
                )
            if args.command == "install":
                summary = mission_archetypes.install(
                    db, document, activate=args.activate
                )
            print(json.dumps({"native_revision": revision, **summary}, sort_keys=True))
    finally:
        database.close()


if __name__ == "__main__":
    main()
