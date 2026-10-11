"""Optional guild projection for every authoritative character reload."""
from .guild_model import native_model, moderation_factor, point_limits


def record_presence(db, account_id, generation):
    row = db.execute("SELECT value FROM settings WHERE name='guild_policy'").fetchone()
    if row is None or row["value"].get("enabled") is not True:
        return
    if (
        db.execute(
            "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s FOR UPDATE",
            (account_id, generation),
        ).fetchone()
        is None
    ):
        return
    db.execute(
        "UPDATE guild_members m SET last_seen=CURRENT_TIMESTAMP FROM sessions s "
        "WHERE s.account_id=%s AND s.generation=%s AND m.character_id=s.character_id",
        (account_id, generation),
    )


def load(db, store, character):
    row = db.execute("SELECT value FROM settings WHERE name='guild_policy'").fetchone()
    policy = row["value"] if row else {}
    if (
        policy.get("enabled") is not True
        or policy.get("native_sync_enabled") is not True
    ):
        return
    # One statement provides a coherent MVCC snapshot without taking guild
    # locks while a roster loader may already hold other character aggregates.
    # A generic character load must not introduce cross-guild lock ordering.
    membership = db.execute(
        "SELECT to_jsonb(g) AS guild, "
        "COALESCE((SELECT jsonb_agg(to_jsonb(r) ORDER BY r.position,r.id) "
        "FROM guild_ranks r WHERE r.guild_id=g.id),'[]'::jsonb) AS ranks, "
        "COALESCE((SELECT jsonb_agg(to_jsonb(profile) ORDER BY profile.character_id) FROM ("
        "SELECT m.character_id,m.rank_id,m.points,COALESCE(cp.xp,0) AS xp,"
        "c.account_id,c.name,c.breed,c.sex,COALESCE(n.nation_id,0) AS nation_id,"
        "EXISTS(SELECT 1 FROM sessions s WHERE s.account_id=c.account_id AND s.character_id=c.id "
        "AND s.expires_at>CURRENT_TIMESTAMP) AS connected,"
        "(EXTRACT(EPOCH FROM m.last_seen)*1000)::bigint AS save_date,"
        "COALESCE(p.language_mask,(chat.value->>'language_mask')::integer) AS language_mask,"
        "COALESCE(p.community,(chat.value->>'community')::integer) AS community "
        "FROM guild_members m JOIN characters c ON c.id=m.character_id "
        "LEFT JOIN character_progression cp ON cp.character_id=c.id "
        "LEFT JOIN character_chat_nations n ON n.character_id=c.id "
        "LEFT JOIN account_chat_preferences p ON p.account_id=c.account_id "
        "JOIN settings chat ON chat.name='chat_channel_policy' "
        "WHERE m.guild_id=g.id AND c.deleted_at IS NULL) profile),'[]'::jsonb) AS members,"
        "COALESCE((SELECT record->'bonuses' FROM guild_service_state "
        "WHERE guild_id=g.id AND service='economy'),'{}'::jsonb) AS bonuses "
        "FROM guilds g JOIN guild_members own ON own.guild_id=g.id "
        "WHERE own.character_id=%s AND g.dissolved_at IS NULL",
        (character["id"],),
    ).fetchone()
    snapshot = None
    if membership is not None:
        guild = membership["guild"]
        point_limits(policy, guild)
        snapshot = dict(
            guild=guild,
            ranks=membership["ranks"],
            members=membership["members"],
            bonuses=[
                dict(
                    bonus_id=int(key),
                    activation_date=value.get("activated_at_ms", 0),
                    buy_date=value["purchased_at_ms"],
                )
                for key, value in membership["bonuses"].items()
            ],
            policy=policy,
        )
    character["guild_native"] = native_model(snapshot)
    character["guild_moderation_factor"] = moderation_factor(snapshot)
