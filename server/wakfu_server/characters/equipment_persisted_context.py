"""Read-only owned data for native player equipment predicates.

The caller owns authorization and the transaction. This loader never calls
Store.character, computes equipment bonuses, changes professions or publishes
packets, so it can be used before equipment reconciliation without recursion.
"""
import math
import struct

from wakfu_server.profession_wire import level as profession_level
from wakfu_server.owned_social_context import OwnedSocialContext
from wakfu_server.ecology_progression import basis_points, native_score

_UNSUPPLIED = object()


def native_gauges(value):
    """Original fzY curve and eLQ/eLq signed, float32 percent conversion."""
    score = native_score(basis_points(value))
    curve = 721.3475204444817  # Original fzZ.tCr, verified by original JVM.
    ratio = -math.expm1(-abs(score) / curve)
    if score < 0:
        ratio = -ratio
    ratio = struct.unpack(">f", struct.pack(">f", ratio))[0]
    percent = struct.unpack(">f", struct.pack(">f", ratio * 100.0))[0]
    wakfu = int(percent)  # Native float-to-long truncates toward zero.
    return wakfu, -wakfu


def load(db, character, *, achievement_authority=_UNSUPPLIED):
    """Combine a hydrated owned actor with its actual account craft rows.

    Missing professions remain absent from profession_levels. The original
    predicate evaluator separately gives an absent craft level zero, and
    HasCraft uses presence (except the original special craft ID zero).
    Ecology stays in canonical basis-point units here, not an assumed percent.
    """
    if not isinstance(character, dict):
        raise ValueError("Missing player equipment context")
    for key in ("id", "account_id", "breed", "level", "effective_level"):
        if type(character.get(key)) is not int or character[key] <= 0:
            raise ValueError("Invalid player equipment context identity or level")
    if type(character.get("account_is_admin")) is not bool:
        raise ValueError("Missing player equipment administrator authority")
    social = OwnedSocialContext.from_record(character.get("native_social_context"))
    social.require_owner(character["id"], character["account_id"])
    ecology = basis_points(character.get("ecology_value"))
    wakfu, stasis = native_gauges(ecology)
    rows = db.execute(
        "SELECT p.profession_id,p.xp,s.name AS neo_mode_name,s.value AS neo_mode_value "
        "FROM characters c LEFT JOIN account_professions p ON c.account_id=p.account_id "
        "LEFT JOIN settings s ON s.name='dungeon_server_mode' "
        "WHERE c.id=%s AND c.account_id=%s AND c.deleted_at IS NULL "
        "ORDER BY p.profession_id",
        (character["id"], character["account_id"]),
    )
    professions = {}
    mode = None
    from wakfu_server.neo_regeneration import mode_from_record

    for row in rows:
        if mode is None:
            mode = mode_from_record(
                None
                if row["neo_mode_name"] is None
                else {"value": row["neo_mode_value"]}
            )
        identity = row["profession_id"]
        if identity is None and row["xp"] is None:
            continue  # An owned character with no learned professions still has mode authority.
        if type(identity) is not int or not 0 < identity < (1 << 31):
            raise ValueError("Invalid owned equipment profession identity")
        professions[identity] = profession_level(row["xp"])
    if type(mode) is not bool:
        raise ValueError("Missing owned equipment server-mode authority")
    context = dict(
        actor_kind="player",
        actor_id=character["id"],
        account_id=character["account_id"],
        level=character["effective_level"],
        real_level=character["level"],
        breed_id=character["breed"],
        is_admin=character["account_is_admin"],
        profession_levels=professions,
        guild_level=social.guild_level,
        guild_id=social.guild_id,
        nation_id=social.nation_id,
        ecology_basis_points=ecology,
        wakfu_gauge=wakfu,
        stasis_gauge=stasis,
        is_neo_server=mode,
    )
    if achievement_authority is _UNSUPPLIED:
        authority = db.execute(
            "SELECT aa.snapshot FROM character_achievement_authority aa "
            "JOIN characters c ON c.id=aa.character_id "
            "WHERE c.id=%s AND c.account_id=%s AND c.deleted_at IS NULL",
            (character["id"], character["account_id"]),
        ).fetchone()
        achievement_authority = None if authority is None else authority["snapshot"]
    if achievement_authority is not None:
        from wakfu_server.dungeon_achievement_authority import queries_from_snapshot

        queries_from_snapshot(achievement_authority)
        context["completed_achievements"] = tuple(
            sorted(achievement_authority["completed"])
        )
    from wakfu_server.company_authority import load as load_company

    context["company_snapshot"] = load_company(db, character).record()
    from wakfu_server.national_progression import load as load_national

    national = load_national(
        db, character["account_id"], character["id"], social.nation_id
    )
    if national is not None:
        context["national_progression"] = national.record()
    return context
