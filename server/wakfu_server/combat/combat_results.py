"""Native FightReport12755 and normal fight completion from own state.

This report accepts committed local XP/kamas receipts and generates no loot. It preserves real participant
identity and does not copy official result, reward or fight instance data.
"""
import struct
from .wire import proto_field


def _number(field, value):
    if type(value) is not int or not -(2**63) <= value < 2**63:
        raise ValueError("Invalid report integer")
    return proto_field(field << 3, value if value >= 0 else value + 2**64)


def _message(field, value):
    return proto_field((field << 3) | 2, value)


def _player(actor, metadata):
    name = metadata.get("name")
    account = metadata.get("account_id")
    breed = metadata.get("breed")
    if (
        not isinstance(name, str)
        or not name
        or type(account) is not int
        or account <= 0
        or type(breed) is not int
        or not 1 <= breed <= 18
        or type(metadata.get("is_male")) is not bool
    ):
        raise ValueError("Invalid own player report identity")
    kamas = metadata.get("gained_kamas", 0)
    if type(kamas) is not int or not 0 <= kamas < 2**31:
        raise ValueError("Invalid committed kama reward")
    xp = b""
    info = metadata.get("xp_info")
    if info is not None:
        from .progression import level_xp

        if not isinstance(info, dict) or set(info) != {
            "end_xp",
            "won_xp",
            "start_level",
            "end_level",
        }:
            raise ValueError("Invalid committed XP receipt")
        end, won = info["end_xp"], info["won_xp"]
        start_level, end_level = info["start_level"], info["end_level"]
        if (
            type(end) is not int
            or type(won) is not int
            or not 0 <= won <= end < 2**63
            or not 1 <= start_level <= end_level <= 200
        ):
            raise ValueError("Invalid committed XP totals")
        if end < level_xp(end_level) or end - won < level_xp(start_level):
            raise ValueError("Reward XP is below its native level threshold")
        xp = _message(
            8,
            _number(1, end)
            + _number(2, won)
            + _number(5, start_level)
            + _number(6, end_level),
        )
    return (
        _number(1, actor.id)
        + _number(2, account)
        + _message(3, name.encode("utf-8"))
        + _number(4, breed)
        + _number(5, int(metadata["is_male"]))
        + _number(6, int(metadata.get("is_hero", False)))
        + xp
        + _number(9, kamas)
        + _number(10, int(actor.hp == 0))
    )


def _monster(actor, metadata):
    from .monsters import reference

    breed = metadata.get("ref")
    reference(breed)
    return _number(1, actor.id) + _number(3, breed) + _number(6, 1)


def fight_report(
    fight, metadata, *, duration_ms, fight_instance_id, initiator_id, fight_model=2
):
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or set(metadata) != set(fight.actors)
    ):
        raise ValueError("Report requires a finished own fight and exact participants")
    if (
        type(duration_ms) is not int
        or not 0 <= duration_ms < 2**63
        or type(fight_instance_id) is not int
        or fight_instance_id <= 0
        or fight_model not in (2, 14)
    ):
        raise ValueError("Invalid report duration, instance or model")
    if initiator_id not in fight.actors:
        raise ValueError("Fight initiator is not a participant")
    initiator_team = fight.actors[initiator_id].team
    teams = {0: _number(1, 0), 1: _number(1, 1)}
    for actor in fight.actors.values():
        record = metadata[actor.id]
        if record.get("kind") == "player":
            if not actor.controlled or record.get("account_id") != actor.owner_id:
                raise ValueError("Player report does not match controller ownership")
            teams[actor.team] += _message(2, _player(actor, record))
        elif record.get("kind") == "monster":
            teams[actor.team] += _message(3, _monster(actor, record))
        else:
            raise ValueError("Unknown report participant kind")
    return (
        _number(1, fight.id)
        + _number(2, duration_ms)
        + _number(3, max(actor.turn_count for actor in fight.actors.values()))
        + _number(4, fight.winner)
        + _message(5, teams[initiator_team])
        + _message(6, teams[1 - initiator_team])
        + _number(7, initiator_id)
        + _number(8, fight_model)
        + _number(14, fight_instance_id)
    )


def finish_messages(
    runtime, metadata, *, duration_ms, fight_instance_id, initiator_id, fight_model=2
):
    """cvF normal winners/losers then cvJ report; client aUH sends12925.

    Runtime caller waits for matching12925 before restoring exploration state.
    """
    fight = runtime.fight
    report = fight_report(
        fight,
        metadata,
        duration_ms=duration_ms,
        fight_instance_id=fight_instance_id,
        initiator_id=initiator_id,
        fight_model=fight_model,
    )
    winners = [a.id for a in fight.actors.values() if a.team == fight.winner]
    losers = [a.id for a in fight.actors.values() if a.team != fight.winner]
    if max(len(winners), len(losers)) > 127:
        raise ValueError("Too many result participants")
    body = runtime._prefix() + b"\x00"
    for ids in (winners, losers, []):
        body += struct.pack(">b", len(ids)) + b"".join(
            struct.pack(">q", identity) for identity in ids
        )
    runtime.awaiting_ack = None
    runtime.pending = []
    return [(12238, body), (12755, runtime._prefix() + report)]


def continuation(fight_id, body):
    """coQ12925: matching fight ID and aUH.huO loss flag (not spectator)."""
    if len(body) != 5:
        raise ValueError("Invalid fight continuation")
    identity, flag = struct.unpack(">iB", body)
    if identity != fight_id or flag not in (0, 1):
        raise ValueError("Foreign fight continuation")
    return bool(flag)


def outside_fight_updates(fight):
    """format17/FOR_PHOENIX consists only of i32fightID; native serializer."""
    from .combat_world_refresh import actor_refresh

    return [
        actor_refresh(a.id, b"\x11" + struct.pack(">i", -1))
        for a in fight.actors.values()
    ]
