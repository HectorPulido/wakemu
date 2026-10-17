"""Owned captured-roster persistence; caller supplies an existing transaction."""
from psycopg.types.json import Jsonb
from .captured_roster import OwnedCapturedRoster


def load(db, character):
    if character["breed"] != 2:
        return None
    schema = db.execute(
        "SELECT to_regclass('character_captured_rosters') AS relation", ()
    ).fetchone()
    if schema is None or schema["relation"] is None:
        # Rolling code delivery before offline DDL: component authority unknown.
        # This is not a proven empty roster; eON must reject missing authority.
        return None
    row = db.execute(
        "SELECT record,revision FROM character_captured_rosters WHERE character_id=%s",
        (character["id"],),
    ).fetchone()
    if row is None:
        # Native biB.dqt constructs an empty ten-slot component when absent.
        return OwnedCapturedRoster(character["id"]).to_record()
    return OwnedCapturedRoster.from_record(
        row["record"], expected_owner_id=character["id"]
    ).to_record()


def save(db, character, roster):
    if character["breed"] != 2 or not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Owned Osamodas roster required")
    if roster.owner_id != character["id"]:
        raise ValueError("Captured roster owner mismatch")
    # Serialize capture/select mutations with the owning character row.
    owner = db.execute(
        "SELECT id FROM characters WHERE id=%s AND account_id=%s "
        "AND breed=2 AND deleted_at IS NULL FOR UPDATE",
        (character["id"], character["account_id"]),
    ).fetchone()
    if owner is None:
        raise ValueError("Captured roster character ownership unavailable")
    return db.execute(
        "INSERT INTO character_captured_rosters(character_id,record,revision) "
        "VALUES(%s,%s,1) ON CONFLICT(character_id) DO UPDATE "
        "SET record=EXCLUDED.record,revision=character_captured_rosters.revision+1 "
        "RETURNING revision",
        (character["id"], Jsonb(roster.to_record())),
    ).fetchone()["revision"]
