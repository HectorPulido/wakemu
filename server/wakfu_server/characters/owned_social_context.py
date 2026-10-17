"""Owned SQL social components, pinned by explicit Wakemu admission policy.

This is a read-only context loader, independent of guild UI enablement. A
missing receipt remains unknown. It does not freeze native guild components.
"""
from dataclasses import dataclass, asdict
import hashlib
import json

POLICY = "wakemu-fight-admission-social-snapshot-v1"
SOURCE = "owned-social-components-mvcc-v1"


@dataclass(frozen=True)
class OwnedSocialContext:
    actor_id: int
    account_id: int
    nation_id: int
    guild_id: int | None
    guild_level: int
    source_revision: str
    source: str = SOURCE
    policy: str = POLICY
    source_sha256: str = ""

    def __post_init__(self):
        if self.source_sha256 == "":
            object.__setattr__(self, "source_sha256", _digest(self._source_fields()))
        self.validate()

    def _source_fields(self):
        return {
            key: value for key, value in asdict(self).items() if key != "source_sha256"
        }

    def validate(self):
        if (
            type(self.actor_id) is not int
            or self.actor_id <= 0
            or type(self.account_id) is not int
            or self.account_id <= 0
            or type(self.nation_id) is not int
            or self.nation_id not in (0, 30, 31, 32, 33, 34)
            or type(self.guild_level) is not int
            or not isinstance(self.source_revision, str)
            or not self.source_revision
            or len(self.source_revision) > 512
            or self.source != SOURCE
            or self.policy != POLICY
        ):
            raise ValueError("Invalid owned social component receipt")
        if self.guild_id is None:
            if self.guild_level != 0:
                raise ValueError("Known empty native guild requires level zero")
        elif (
            type(self.guild_id) is not int
            or self.guild_id <= 0
            or not 1 <= self.guild_level <= 32767
        ):
            raise ValueError("Invalid native guild membership receipt")
        if self.source_sha256 != _digest(self._source_fields()):
            raise ValueError("Owned social source digest mismatch")
        return self

    def require_owner(self, actor_id, account_id):
        self.validate()
        if (
            type(actor_id) is not int
            or type(account_id) is not int
            or (self.actor_id, self.account_id) != (actor_id, account_id)
        ):
            raise ValueError("Owned social receipt actor/account mismatch")
        return self

    def to_record(self):
        self.validate()
        payload = asdict(self)
        payload["sha256"] = _digest(payload)
        return payload

    @classmethod
    def from_record(cls, record):
        if not isinstance(record, dict):
            raise ValueError("Missing owned social checkpoint record")
        values = {key: value for key, value in record.items() if key != "sha256"}
        if set(values) != set(cls.__dataclass_fields__) or record.get(
            "sha256"
        ) != _digest(values):
            raise ValueError("Owned social checkpoint integrity mismatch")
        return cls(**values).validate()


def _digest(values):
    return hashlib.sha256(
        json.dumps(
            values, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def load(db, account_id, actor_id):
    """One MVCC statement proves membership or its actual absence.

    No settings are changed and no guild UI policy is implicitly enabled.
    Dissolved guilds do not provide an installed membership component.
    """
    row = db.execute(
        "SELECT c.id AS actor_id,c.account_id,COALESCE(n.nation_id,0) AS nation_id,"
        "g.id AS guild_id,COALESCE(g.level,0) AS guild_level,"
        "'rows:' || c.xmin::text || ':' || "
        "COALESCE(n.xmin::text,'absent') || ':' || "
        "COALESCE(m.xmin::text,'absent') || ':' || "
        "COALESCE(g.xmin::text,'absent') AS source_revision "
        "FROM characters c LEFT JOIN character_chat_nations n ON n.character_id=c.id "
        "LEFT JOIN guild_members m ON m.character_id=c.id "
        "LEFT JOIN guilds g ON g.id=m.guild_id AND g.dissolved_at IS NULL "
        "WHERE c.id=%s AND c.account_id=%s AND c.deleted_at IS NULL",
        (actor_id, account_id),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned social SQL source")
    return OwnedSocialContext(**dict(row)).require_owner(actor_id, account_id)


def pin(fight, character):
    receipt = character.get("native_social_context")
    if receipt is None:
        return  # Older pure fixtures remain explicitly unknown.
    receipt = OwnedSocialContext.from_record(receipt)
    receipt.require_owner(character["id"], character["account_id"])
    actor = fight.actors.get(receipt.actor_id)
    if actor is None or actor.controlled is not True:
        raise ValueError("Social receipt requires actual owned PC in fight")
    records = dict(getattr(fight, "native_social_contexts", {}))
    previous = records.get(receipt.actor_id)
    if previous is not None:
        if type(previous) is not OwnedSocialContext:
            raise ValueError("Invalid pinned social authority")
        previous.require_owner(receipt.actor_id, receipt.account_id)
        return  # Explicit admission snapshot policy, never a hidden refresh.
    records[receipt.actor_id] = receipt
    fight.native_social_contexts = records


def current(fight, character):
    record = getattr(fight, "native_social_contexts", {}).get(character["id"])
    if record is None:
        return None
    if type(record) is not OwnedSocialContext:
        raise ValueError("Invalid restored social context type")
    return record.require_owner(character["id"], character["account_id"])
