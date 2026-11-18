"""Read-only native reward/progress and exterior-state audit for Astrub line3.

This tool never connects a game client or changes a character. A matching
reward outbox proves durable settlement, not how a fight was won or what the
graphical client rendered. The caller records gameplay authority separately.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from tools.install_mission_bundle import local_connection
from wakfu_server.postgres import Database

QUESTS = (2135, 2140, 2143, 2144, 2145, 2146, 2138)


def audit(db, account_id, character_id):
    with db.transaction():
        db.execute("SET TRANSACTION READ ONLY")
        release = db.execute(
            "SELECT revision FROM native_quest_metadata_releases "
            "ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()
        if release is None:
            raise ValueError("No installed native quest metadata")
        rows = db.execute(
            "SELECT definition_id,data FROM native_quest_metadata_definitions "
            "WHERE revision=%s AND definition_id=ANY(%s)",
            (release["revision"], list(QUESTS)),
        ).fetchall()
        definitions = {row["definition_id"]: row["data"]["native"] for row in rows}
        if set(definitions) != set(QUESTS):
            raise ValueError("Line3 native definitions are incomplete")
        character = db.execute(
            "SELECT id,account_id,map_id,instance_id,x,y,z,hp,max_hp "
            "FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        if character is None:
            raise ValueError("Character does not belong to supplied account")
        saved = db.execute(
            "SELECT state FROM character_achievement_progress WHERE character_id=%s",
            (character_id,),
        ).fetchone()
        state = {} if saved is None else saved["state"]
        rewards = db.execute(
            "SELECT achievement_id,cycle_key,reward_key,payload,delivered_at "
            "FROM character_achievement_reward_outbox WHERE character_id=%s "
            "AND achievement_id=ANY(%s) ORDER BY achievement_id,cycle_key,reward_key",
            (character_id, list(QUESTS)),
        ).fetchall()
        contracts = {}
        for quest in QUESTS:
            native = definitions[quest]
            expected = {str(row["d"]): row for row in native["cjK"]}
            actual = [row for row in rewards if row["achievement_id"] == quest]
            missing = sorted(set(expected) - {row["reward_key"] for row in actual})
            unexpected = [
                row["reward_key"] for row in actual if row["reward_key"] not in expected
            ]
            different = [
                row["reward_key"]
                for row in actual
                if row["payload"] != expected.get(row["reward_key"])
            ]
            cycles = {row["cycle_key"] for row in actual}
            objectives = [row["d"] for row in native["cjJ"]]
            contracts[str(quest)] = dict(
                running=quest in state.get("running", ()),
                completed=quest in state.get("completed", ()),
                expected_objectives=objectives,
                earned_objectives=[
                    identity
                    for identity in objectives
                    if identity in state.get("objectives", ())
                ],
                expected_rewards=list(expected.values()),
                reward_rows=actual,
                missing_reward_keys=missing,
                unexpected_reward_keys=unexpected,
                mismatched_reward_keys=different,
                exact_rewards_once_delivered=(
                    len(actual) == len(expected)
                    and cycles == {"once"}
                    and not missing
                    and not unexpected
                    and not different
                    and all(row["delivered_at"] is not None for row in actual)
                ),
            )
        active_memberships = db.execute(
            "SELECT m.instance_id,m.status,i.status AS instance_status "
            "FROM dungeon_instance_members m JOIN dungeon_instances i USING(instance_id) "
            "WHERE m.character_id=%s AND m.status='active' AND i.status='active'",
            (character_id,),
        ).fetchall()
        company = db.execute(
            "SELECT party_id FROM player_party_members WHERE character_id=%s",
            (character_id,),
        ).fetchall()
        pending_transitions = db.execute(
            "SELECT instance_id,count(*) AS count FROM dungeon_transition_outbox "
            "WHERE character_id=%s AND status='pending' GROUP BY instance_id",
            (character_id,),
        ).fetchall()
        pending_notifications = db.execute(
            "SELECT count(*) AS count FROM character_achievement_notifications "
            "WHERE character_id=%s AND delivered_at IS NULL",
            (character_id,),
        ).fetchone()["count"]
        bread = db.execute(
            "SELECT reference,quantity FROM character_quest_items "
            "WHERE character_id=%s AND reference=12686",
            (character_id,),
        ).fetchall()
        return dict(
            read_only=True,
            at=datetime.now(timezone.utc).isoformat(),
            native_metadata_revision=release["revision"],
            character=character,
            contracts=contracts,
            quest_inventory_bread=bread,
            active_memberships=active_memberships,
            company_membership=company,
            pending_transitions=pending_transitions,
            pending_achievement_notifications=pending_notifications,
            public_solo_exit_clean=(
                character["instance_id"] == 0
                and not active_memberships
                and not company
                and not pending_transitions
            ),
            position_registry="Not inspected: live World owns the in-memory registry",
            graphical_and_natural_acceptance="Not established by this SQL audit",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, type=int)
    parser.add_argument("--character-id", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dsn = os.environ["WAKFU_DATABASE_URL"]
    local_connection(dsn)
    database = Database(
        dsn, password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    )
    try:
        with database.connection() as db:
            result = audit(db, args.account_id, args.character_id)
        text = json.dumps(result, default=str, indent=2) + "\n"
        if args.output:
            args.output.write_text(text)
        else:
            print(text, end="")
    finally:
        database.close()


if __name__ == "__main__":
    main()
