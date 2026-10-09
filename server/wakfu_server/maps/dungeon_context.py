"""Version-pinned authoritative ProtoDungeon policy.

The native protobuf field layout is verified, but the installed Jalató values
and the meaning of ``allowed_ids`` are not. Policies therefore require an
explicit SQL row and provenance; missing configuration fails closed. The
fight-in-progress bit is runtime state and must be supplied by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass

from wakfu_server import dungeon_instances


@dataclass(frozen=True)
class ContextPolicy:
    route_key: str
    policy_version: int
    template_id: int
    definition_id: int
    max_level: int
    min_level: int
    difficulty_level: int
    is_difficulty_available: bool
    can_increase_difficulty: bool
    is_competitive_cancelled: bool
    allowed_ids: tuple[int, ...]
    provenance: str

    def proto_context(self, *, fight_in_progress):
        if type(fight_in_progress) is not bool:
            raise ValueError("Authoritative dungeon fight state is required")
        return {
            "max_level": self.max_level,
            "min_level": self.min_level,
            "difficulty_level": self.difficulty_level,
            "is_difficulty_available": self.is_difficulty_available,
            "can_increase_difficulty": self.can_increase_difficulty,
            "is_fight_in_progress": fight_in_progress,
            "is_competitive_cancelled": self.is_competitive_cancelled,
            # This is an explicit policy list. Never infer it from party members.
            "allowed_ids": self.allowed_ids,
        }


_FIELDS = (
    "route_key",
    "policy_version",
    "template_id",
    "definition_id",
    "max_level",
    "min_level",
    "difficulty_level",
    "is_difficulty_available",
    "can_increase_difficulty",
    "is_competitive_cancelled",
    "allowed_ids",
    "provenance",
)


def _policy(row, route):
    if row is None:
        raise ValueError("Dungeon ProtoDungeon context policy is not configured")
    if row["route_key"] != route.key or (row["template_id"], row["definition_id"]) != (
        route.template_id,
        route.definition_id,
    ):
        raise ValueError("Dungeon context policy does not match its native route")
    for key in (
        "policy_version",
        "template_id",
        "definition_id",
        "max_level",
        "min_level",
    ):
        if type(row[key]) is not int:
            raise ValueError("Dungeon context policy has invalid integer fields")
    if (
        row["policy_version"] <= 0
        or row["template_id"] <= 0
        or row["definition_id"] <= 0
    ):
        raise ValueError("Dungeon context policy has invalid identity")
    if (
        not 0 <= row["max_level"] <= 0x7FFFFFFF
        or not 0 <= row["min_level"] <= 0x7FFFFFFF
    ):
        raise ValueError("Dungeon context policy has invalid level bounds")
    if row["max_level"] and row["min_level"] > row["max_level"]:
        raise ValueError("Dungeon context policy has inverted level bounds")
    difficulty = row["difficulty_level"]
    if type(difficulty) is not int or not 1 <= difficulty <= 10:
        raise ValueError("Dungeon context policy has invalid difficulty")
    for key in (
        "is_difficulty_available",
        "can_increase_difficulty",
        "is_competitive_cancelled",
    ):
        if type(row[key]) is not bool:
            raise ValueError("Dungeon context policy has invalid boolean fields")
    allowed_ids = row["allowed_ids"]
    if not isinstance(allowed_ids, (tuple, list)) or any(
        type(identity) is not int or not -(1 << 63) <= identity <= (1 << 63) - 1
        for identity in allowed_ids
    ):
        raise ValueError("Dungeon context policy has invalid allowed_ids")
    if not isinstance(row["provenance"], str) or not row["provenance"].strip():
        raise ValueError("Dungeon context policy requires provenance")
    return ContextPolicy(
        route_key=row["route_key"],
        policy_version=row["policy_version"],
        template_id=row["template_id"],
        definition_id=row["definition_id"],
        max_level=row["max_level"],
        min_level=row["min_level"],
        difficulty_level=difficulty,
        is_difficulty_available=row["is_difficulty_available"],
        can_increase_difficulty=row["can_increase_difficulty"],
        is_competitive_cancelled=row["is_competitive_cancelled"],
        allowed_ids=tuple(allowed_ids),
        provenance=row["provenance"],
    )


def active_policy(db, route):
    """Read and lock a route's selected version inside the caller transaction."""
    row = db.execute(
        "SELECT p.route_key,p.policy_version,p.template_id,p.definition_id,"
        "p.max_level,p.min_level,p.difficulty_level,p.is_difficulty_available,"
        "p.can_increase_difficulty,p.is_competitive_cancelled,p.allowed_ids,"
        "p.provenance FROM dungeon_context_active_policies a "
        "JOIN dungeon_context_policy_versions p USING(route_key,policy_version) "
        "WHERE a.route_key=%s FOR SHARE OF a",
        (route.key,),
    ).fetchone()
    return _policy(row, route)


def policy_version(db, route, version):
    """Load the immutable policy pinned when an active run was created."""
    if type(version) is not int or version <= 0:
        raise ValueError("Dungeon instance has no pinned context policy")
    row = db.execute(
        "SELECT route_key,policy_version,template_id,definition_id,max_level,"
        "min_level,difficulty_level,is_difficulty_available,"
        "can_increase_difficulty,is_competitive_cancelled,allowed_ids,provenance "
        "FROM dungeon_context_policy_versions WHERE route_key=%s AND policy_version=%s",
        (route.key, version),
    ).fetchone()
    return _policy(row, route)


def for_instance(store, instance_id, *, fight_in_progress):
    """Return pinned ProtoDungeon values plus required authoritative fight state."""
    if type(instance_id) is not int or instance_id <= 0:
        raise ValueError("Invalid dungeon instance identity")
    if type(fight_in_progress) is not bool:
        raise ValueError("Authoritative dungeon fight state is required")
    with store.connection() as db:
        row = db.execute(
            "SELECT i.context_route_key,i.context_policy_version "
            "FROM dungeon_instances i WHERE i.instance_id=%s AND i.status='active'",
            (instance_id,),
        ).fetchone()
        if row is None or row["context_route_key"] is None:
            raise ValueError("Dungeon instance has no pinned ProtoDungeon policy")
        configured = dungeon_instances.route(row["context_route_key"])
        policy = policy_version(db, configured, row["context_policy_version"])
    return policy.proto_context(fight_in_progress=fight_in_progress)
