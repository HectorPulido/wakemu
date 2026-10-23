"""Transactional guild authority. Local policy is explicit and disabled by default.

Lock order: acting session/character, guild aggregate, wallet, inventory. Never
lock a target character after acquiring a guild. Logical deletion is fenced by
its SQL trigger; membership writers serialize through the guild row.
"""
import re
import unicodedata
from psycopg.types.json import Jsonb


def _has_unsettled_holdings(service, record):
    """Known economy bookkeeping is not a refundable economic holding."""
    if not isinstance(record, dict):
        return True
    if not record:
        return False
    if service != "economy" or set(record) - {
        "kamas",
        "week",
        "bonuses",
        "learning_duration_factor",
        "maximum_simultaneous_learning",
        "points_earned_factor",
        "bonus_cycles",
        "native_weekly_point_cap",
    }:
        return True
    # Original learned bonus modifiers are bookkeeping, not refundable custody.
    # Unknown/malformed state remains a blocker instead of being discarded.
    for name, allowed in (
        ("learning_duration_factor", (1, 0.9)),
        ("maximum_simultaneous_learning", (1, 2)),
        ("points_earned_factor", (1, 1.1)),
    ):
        if name in record and (
            type(record[name]) not in (int, float) or record[name] not in allowed
        ):
            return True
    if "bonus_cycles" in record:
        cycles = record["bonus_cycles"]
        if not isinstance(cycles, dict) or any(
            not isinstance(key, str)
            or not 1 <= len(key) <= 10
            or not key.isascii()
            or not key.isdecimal()
            or str(int(key)) != key
            or not 0 < int(key) < 2**31
            or type(value) is not int
            or value < 0
            for key, value in cycles.items()
        ):
            return True
    if "native_weekly_point_cap" in record and (
        type(record["native_weekly_point_cap"]) is not int
        or not 1 <= record["native_weekly_point_cap"] < 2**31
    ):
        return True
    kamas = record.get("kamas", 0)
    return type(kamas) is not int or kamas != 0


class GuildService:
    def __init__(self, store):
        self.store = store

    def _policy(self, db):
        row = db.execute(
            "SELECT value FROM settings WHERE name='guild_policy'"
        ).fetchone()
        return row["value"] if row else {"enabled": False}

    def enabled(self):
        with self.store.connection() as db:
            return self._policy(db).get("enabled") is True

    def native_enabled(self):
        with self.store.connection() as db:
            policy = self._policy(db)
            return (
                policy.get("enabled") is True
                and policy.get("native_sync_enabled") is True
            )

    def authorize_native_request(self, opcode):
        """Keep the explicit identity-only capability separate from guild sync."""
        with self.store.connection() as db:
            policy = self._policy(db)
            if (
                policy.get("enabled") is not True
                or policy.get("native_sync_enabled") is not True
            ):
                raise ValueError("Guild system is disabled")
            primary = policy.get("primary_identity_only", False)
            if type(primary) is not bool:
                raise ValueError("Invalid guild primary capability policy")
            if primary and opcode not in (13757, 12937, 12575, 15877):
                raise ValueError("Guild operation is unavailable in identity-only mode")
            if policy.get("management_enabled") is True:
                allowed = policy.get("native_request_opcodes")
                if (
                    not isinstance(allowed, list)
                    or any(type(value) is not int for value in allowed)
                    or opcode not in allowed
                ):
                    raise ValueError(
                        "Guild operation is unavailable in management mode"
                    )

    def _start(self, db, account, generation, character):
        self.store.lock_character(db, account, generation, character)
        policy = self._policy(db)
        if policy.get("enabled") is not True:
            raise ValueError("Guild system is disabled")
        return policy

    def _guild(self, db, character):
        row = db.execute(
            "SELECT g.* FROM guilds g JOIN guild_members m ON m.guild_id=g.id WHERE m.character_id=%s AND g.dissolved_at IS NULL FOR UPDATE OF g",
            (character,),
        ).fetchone()
        if row is None:
            raise ValueError("Character is not a guild member")
        return row

    def _permission(self, db, guild, character, policy, action):
        member = db.execute(
            "SELECT m.*,r.position,r.permissions FROM guild_members m JOIN guild_ranks r ON r.guild_id=m.guild_id AND r.id=m.rank_id WHERE m.character_id=%s AND m.guild_id=%s",
            (character, guild["id"]),
        ).fetchone()
        bit = policy.get("permissions", {}).get(action)
        if (
            member is None
            or type(bit) is not int
            or not 0 <= bit < 63
            or not member["permissions"] & (1 << bit)
        ):
            raise ValueError("Guild permission denied: " + action)
        return member

    def _event(self, db, guild_id, kind, payload):
        revision = db.execute(
            "UPDATE guilds SET revision=revision+1 WHERE id=%s RETURNING revision",
            (guild_id,),
        ).fetchone()["revision"]
        db.execute(
            "INSERT INTO guild_events(guild_id,revision,kind,payload) VALUES(%s,%s,%s,%s)",
            (guild_id, revision, kind, Jsonb(payload)),
        )

    def _snapshot(self, db, guild_id):
        guild = dict(
            db.execute("SELECT * FROM guilds WHERE id=%s", (guild_id,)).fetchone()
        )
        guild["created_at"] = guild["created_at"].isoformat()
        guild["dissolved_at"] = (
            guild["dissolved_at"].isoformat() if guild["dissolved_at"] else None
        )
        guild["ranks"] = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM guild_ranks WHERE guild_id=%s ORDER BY position,id",
                (guild_id,),
            ).fetchall()
        ]
        guild["members"] = [
            dict(r)
            for r in db.execute(
                "SELECT m.character_id,m.rank_id,m.points,COALESCE(cp.xp,0) AS xp,c.account_id,c.name,c.breed,c.sex,COALESCE(n.nation_id,0) AS nation_id,COALESCE(cp.xp,0) AS character_xp,EXISTS(SELECT 1 FROM sessions s WHERE s.account_id=c.account_id AND s.character_id=c.id AND s.expires_at>CURRENT_TIMESTAMP) AS connected,(EXTRACT(EPOCH FROM m.last_seen)*1000)::bigint AS save_date FROM guild_members m JOIN characters c ON c.id=m.character_id LEFT JOIN character_progression cp ON cp.character_id=c.id LEFT JOIN character_chat_nations n ON n.character_id=c.id WHERE m.guild_id=%s ORDER BY m.character_id",
                (guild_id,),
            ).fetchall()
        ]
        chat = db.execute(
            "SELECT value FROM settings WHERE name='chat_channel_policy'"
        ).fetchone()["value"]
        for member in guild["members"]:
            prefs = db.execute(
                "SELECT language_mask,community FROM account_chat_preferences WHERE account_id=%s",
                (member["account_id"],),
            ).fetchone()
            member["language_mask"] = (
                prefs["language_mask"] if prefs else chat["language_mask"]
            )
            member["community"] = prefs["community"] if prefs else chat["community"]
        policy = self._policy(db)
        from .guild_model import point_limits

        from .guild_economy import economy_record

        economy = economy_record(db, guild_id)
        point_limits(policy, guild, economy_record=economy, now=self.store.now())
        bonuses = [
            dict(
                bonus_id=int(key),
                activation_date=value.get("activated_at_ms", 0),
                buy_date=value["purchased_at_ms"],
            )
            for key, value in economy.get("bonuses", {}).items()
        ]
        result = {
            "guild": guild,
            "ranks": guild.pop("ranks"),
            "members": guild.pop("members"),
            "bonuses": bonuses,
            "member_bonus_records": dict(economy.get("bonuses", {})),
            "policy": policy,
        }
        if policy.get("native_sync_enabled") is True:
            from .guild_model import native_model, moderation_factor
            from .guild_wire import local_section

            if (
                len(local_section(native_model(result), moderation_factor(result))) + 40
                > 65535
            ):
                raise ValueError("Guild snapshot exceeds native actor carrier length")
        return result

    def snapshot(self, account_id, generation, character_id):
        with self.store.connection() as db:
            self._start(db, account_id, generation, character_id)
            row = db.execute(
                "SELECT guild_id FROM guild_members WHERE character_id=%s",
                (character_id,),
            ).fetchone()
            if row:
                db.execute(
                    "SELECT id FROM guilds WHERE id=%s FOR UPDATE", (row["guild_id"],)
                )
            if (
                row
                and not db.execute(
                    "SELECT 1 FROM guild_members WHERE character_id=%s AND guild_id=%s",
                    (character_id, row["guild_id"]),
                ).fetchone()
            ):
                return None
            if row:
                from .guild_progression import settle_due

                policy = self._policy(db).get("economy", {})
                if (
                    policy.get("bonus_catalog_authority")
                    == "native_guild_progression_v1"
                ):
                    guild = db.execute(
                        "SELECT * FROM guilds WHERE id=%s", (row["guild_id"],)
                    ).fetchone()
                    settle_due(db, self.store, guild, policy)
            return self._snapshot(db, row["guild_id"]) if row else None

    def create(
        self,
        account_id,
        generation,
        character_id,
        name,
        blazon,
        leader_name,
        member_name,
        *,
        operation_key
    ):
        if not isinstance(operation_key, str) or not 1 <= len(operation_key) <= 200:
            raise ValueError("A stable bounded operation key is required")
        request = dict(
            name=name, blazon=blazon, leader_name=leader_name, member_name=member_name
        )
        with self.store.connection() as db:
            policy = self._start(db, account_id, generation, character_id)
            receipt = db.execute(
                "SELECT request,result FROM guild_operation_receipts WHERE character_id=%s AND operation_key=%s",
                (character_id, operation_key),
            ).fetchone()
            if receipt:
                if receipt["request"] != request:
                    raise ValueError("Operation key reused with a different request")
                prior = receipt["result"]
                current = db.execute(
                    "SELECT dissolved_at FROM guilds WHERE id=%s FOR UPDATE",
                    (prior["guild"]["id"],),
                ).fetchone()
                if current is None or current["dissolved_at"] is not None:
                    raise ValueError("Original guild operation is no longer active")
                if not db.execute(
                    "SELECT 1 FROM guild_members WHERE character_id=%s AND guild_id=%s",
                    (character_id, prior["guild"]["id"]),
                ).fetchone():
                    raise ValueError(
                        "Original guild operation no longer belongs to this member"
                    )
                return self._snapshot(db, prior["guild"]["id"])
            name = self._identity_name(name, policy)
            self._identity_blazon(blazon)
            if policy.get("owner_id_semantics") not in ("character", "account"):
                raise ValueError("Guild owner identity policy is unavailable")
            for label in (leader_name, member_name):
                if (
                    not isinstance(label, str)
                    or not 1 <= len(label.encode("utf-16-le")) // 2 <= 16
                    or len(label.encode("utf-8")) > 127
                ):
                    raise ValueError("Invalid rank name")
            masks = self._initial_rank_masks(policy)
            if db.execute(
                "SELECT 1 FROM guild_members WHERE character_id=%s", (character_id,)
            ).fetchone():
                raise ValueError("Character already belongs to a guild")
            cost, item = policy["creation_kamas"], policy["creation_item"]
            if type(cost) is not int or cost < 0 or type(item) is not int or item <= 0:
                raise ValueError("Invalid guild creation policy")
            self._consume_identity_cost(db, account_id, character_id, item, cost)
            key = unicodedata.normalize("NFKC", name).casefold()
            guild_id = db.execute(
                "INSERT INTO guilds(name,name_key,blazon,leader_id) VALUES(%s,%s,%s,%s) RETURNING id",
                (name, key, blazon, character_id),
            ).fetchone()["id"]
            ranks = []
            for position, label in enumerate((leader_name, member_name)):
                ranks.append(
                    db.execute(
                        "INSERT INTO guild_ranks(guild_id,name,position,permissions) VALUES(%s,%s,%s,%s) RETURNING id",
                        (guild_id, label, position, masks[position]),
                    ).fetchone()["id"]
                )
            db.execute(
                "INSERT INTO guild_members(character_id,guild_id,rank_id) VALUES(%s,%s,%s)",
                (character_id, guild_id, ranks[0]),
            )
            self._event(db, guild_id, "created", {"character_id": character_id})
            result = self._snapshot(db, guild_id)
            db.execute(
                "INSERT INTO guild_operation_receipts(character_id,operation_key,request,result) VALUES(%s,%s,%s,%s)",
                (character_id, operation_key, Jsonb(request), Jsonb(result)),
            )
            return result

    def _rank(self, db, guild, rank_id):
        rank = db.execute(
            "SELECT * FROM guild_ranks WHERE guild_id=%s AND id=%s",
            (guild["id"], rank_id),
        ).fetchone()
        if rank is None:
            raise ValueError("Unknown guild rank")
        return rank

    def _rank_values(self, actor, name, permissions):
        from wakfu_server.guild_native_validators import validate_rank_mask

        validate_rank_mask(permissions)
        if (
            not isinstance(name, str)
            or not 1 <= len(name.encode("utf-16-le")) // 2 <= 16
            or len(name.encode("utf-8")) > 127
        ):
            raise ValueError("Invalid rank name")
        if (
            type(permissions) is not int
            or not 0 <= permissions < (1 << 63)
            or permissions & ~actor["permissions"]
        ):
            raise ValueError("Rank permissions exceed authority")

    def rank_create(self, account_id, generation, character_id, name, permissions):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            actor = self._permission(db, g, character_id, p, "rank_create")
            self._rank_values(actor, name, permissions)
            count = db.execute(
                "SELECT count(*) AS n FROM guild_ranks WHERE guild_id=%s", (g["id"],)
            ).fetchone()["n"]
            if actor["position"] >= count - 1:
                raise ValueError("Cannot create a rank above own rank")
            if count >= p["max_ranks"]:
                raise ValueError("Guild rank capacity reached")
            db.execute(
                "UPDATE guild_ranks SET position=position+1 WHERE guild_id=%s AND position=%s",
                (g["id"], count - 1),
            )
            db.execute(
                "INSERT INTO guild_ranks(guild_id,name,position,permissions) VALUES(%s,%s,%s,%s)",
                (g["id"], name, count - 1, permissions),
            )
            self._event(db, g["id"], "ranks_changed", {})
            return self._snapshot(db, g["id"])

    def rank_edit(
        self, account_id, generation, character_id, rank_id, name, permissions
    ):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            actor = self._permission(db, g, character_id, p, "rank_edit")
            rank = self._rank(db, g, rank_id)
            if rank["position"] <= actor["position"]:
                raise ValueError("Cannot edit own or superior rank")
            self._rank_values(actor, name, permissions)
            bottom = db.execute(
                "SELECT max(position) AS p FROM guild_ranks WHERE guild_id=%s",
                (g["id"],),
            ).fetchone()["p"]
            if rank["position"] == bottom:
                from wakfu_server.guild_native_validators import validate_rank_mask

                validate_rank_mask(permissions, lowest=True)
            db.execute(
                "UPDATE guild_ranks SET name=%s,permissions=%s WHERE id=%s",
                (name, permissions, rank_id),
            )
            self._event(db, g["id"], "ranks_changed", {})
            return self._snapshot(db, g["id"])

    def rank_remove(self, account_id, generation, character_id, rank_id):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            actor = self._permission(db, g, character_id, p, "rank_remove")
            rank = self._rank(db, g, rank_id)
            bottom = db.execute(
                "SELECT max(position) AS p FROM guild_ranks WHERE guild_id=%s",
                (g["id"],),
            ).fetchone()["p"]
            if (
                rank["position"] == bottom
                or rank["position"] <= actor["position"]
                or db.execute(
                    "SELECT 1 FROM guild_members WHERE guild_id=%s AND rank_id=%s",
                    (g["id"], rank_id),
                ).fetchone()
            ):
                raise ValueError("Cannot remove occupied, own or superior rank")
            db.execute("DELETE FROM guild_ranks WHERE id=%s", (rank_id,))
            db.execute(
                "UPDATE guild_ranks SET position=position-1 WHERE guild_id=%s AND position>%s",
                (g["id"], rank["position"]),
            )
            self._event(db, g["id"], "ranks_changed", {})
            return self._snapshot(db, g["id"])

    def rank_move(self, account_id, generation, character_id, rank_id, position):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            actor = self._permission(db, g, character_id, p, "rank_move")
            rank = self._rank(db, g, rank_id)
            ranks = db.execute(
                "SELECT id FROM guild_ranks WHERE guild_id=%s ORDER BY position",
                (g["id"],),
            ).fetchall()
            if (
                type(position) is not int
                or not actor["position"] < position < len(ranks) - 1
                or rank["position"] <= actor["position"]
                or rank["position"] == len(ranks) - 1
            ):
                raise ValueError("Cannot move own or superior rank")
            ids = [r["id"] for r in ranks]
            ids.remove(rank_id)
            ids.insert(position, rank_id)
            for index, value in enumerate(ids):
                db.execute(
                    "UPDATE guild_ranks SET position=%s WHERE id=%s", (index, value)
                )
            self._event(db, g["id"], "ranks_changed", {})
            return self._snapshot(db, g["id"])

    def member_rank(self, account_id, generation, character_id, target_id, rank_id):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            actor = self._permission(db, g, character_id, p, "member_rank")
            rank = self._rank(db, g, rank_id)
            target = db.execute(
                "SELECT m.*,r.position FROM guild_members m JOIN guild_ranks r ON r.id=m.rank_id WHERE m.guild_id=%s AND m.character_id=%s",
                (g["id"], target_id),
            ).fetchone()
            if (
                target is None
                or target_id == character_id
                or target["position"] <= actor["position"]
            ):
                raise ValueError("Target rank exceeds authority")
            if rank["position"] == 0:
                if g["leader_id"] != character_id:
                    raise ValueError("Only leader can transfer leadership")
                db.execute(
                    "UPDATE guild_members SET rank_id=%s WHERE character_id=%s",
                    (target["rank_id"], character_id),
                )
                db.execute(
                    "UPDATE guilds SET leader_id=%s WHERE id=%s", (target_id, g["id"])
                )
            elif (
                rank["position"] <= actor["position"]
                or rank["permissions"] & ~actor["permissions"]
            ):
                raise ValueError("Assigned rank exceeds authority")
            db.execute(
                "UPDATE guild_members SET rank_id=%s WHERE character_id=%s",
                (rank_id, target_id),
            )
            self._event(
                db,
                g["id"],
                "member_rank",
                {"character_id": target_id, "rank_id": rank_id},
            )
            return self._snapshot(db, g["id"])

    def remove_member(self, account_id, generation, character_id, target_id):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            if target_id == g["leader_id"]:
                raise ValueError("Leader must transfer leadership or dissolve")
            target = db.execute(
                "SELECT r.position FROM guild_members m JOIN guild_ranks r ON r.id=m.rank_id WHERE m.guild_id=%s AND m.character_id=%s",
                (g["id"], target_id),
            ).fetchone()
            if target is None:
                raise ValueError("Target is not a guild member")
            if target_id != character_id:
                actor = self._permission(db, g, character_id, p, "kick")
                if target["position"] <= actor["position"]:
                    raise ValueError("Cannot expel own or superior rank")
            db.execute(
                "DELETE FROM guild_members WHERE guild_id=%s AND character_id=%s",
                (g["id"], target_id),
            )
            self._event(db, g["id"], "member_removed", {"character_id": target_id})
            return self._snapshot(db, g["id"])

    def dissolve(self, account_id, generation, character_id):
        with self.store.connection() as db:
            self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            if g["leader_id"] != character_id:
                raise ValueError("Only leader can dissolve guild")
            # Economic holdings must be settled under an explicit refund policy.
            holdings = db.execute(
                "SELECT service,record FROM guild_service_state WHERE guild_id=%s",
                (g["id"],),
            ).fetchall()
            if any(
                _has_unsettled_holdings(r["service"], r["record"]) for r in holdings
            ):
                raise ValueError(
                    "Guild service holdings require settlement before dissolution"
                )
            if db.execute(
                "SELECT 1 FROM guild_chests WHERE guild_id=%s AND jsonb_array_length(items)>0 LIMIT 1",
                (g["id"],),
            ).fetchone():
                raise ValueError("Empty guild chests before dissolution")
            member_ids = [
                row["character_id"]
                for row in db.execute(
                    "SELECT character_id FROM guild_members WHERE guild_id=%s",
                    (g["id"],),
                ).fetchall()
            ]
            db.execute("DELETE FROM guild_members WHERE guild_id=%s", (g["id"],))
            db.execute(
                "UPDATE guild_invitations SET status='cancelled' WHERE guild_id=%s AND status='pending'",
                (g["id"],),
            )
            db.execute(
                "UPDATE guilds SET dissolved_at=CURRENT_TIMESTAMP WHERE id=%s",
                (g["id"],),
            )
            self._event(db, g["id"], "dissolved", {"member_ids": member_ids})
            return self._snapshot(db, g["id"])

    def metadata_set(self, account_id, generation, character_id, field, value):
        if field not in ("description", "message") or not isinstance(value, str):
            raise ValueError("Invalid guild metadata")
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            self._permission(db, g, character_id, p, field)
            limit = p.get(field + "_max_bytes")
            if type(limit) is not int or len(value.encode("utf-8")) > limit:
                raise ValueError("Metadata limit unavailable or exceeded")
            db.execute(
                "UPDATE guilds SET " + field + "=%s WHERE id=%s", (value, g["id"])
            )
            self._event(
                db, g["id"], "metadata_changed", {"field": field, "value": value}
            )
            return self._snapshot(db, g["id"])

    def _invite(self, db, p, g, character_id, target_id, target_generation=None):
        self._permission(db, g, character_id, p, "invite")
        target = db.execute(
            "SELECT id FROM characters WHERE id=%s AND deleted_at IS NULL", (target_id,)
        ).fetchone()
        if (
            target is None
            or db.execute(
                "SELECT 1 FROM guild_members WHERE character_id=%s", (target_id,)
            ).fetchone()
        ):
            raise ValueError("Target is unavailable")
        db.execute(
            "UPDATE guild_invitations SET status='cancelled' WHERE target_id=%s AND status='pending' AND expires_at<=CURRENT_TIMESTAMP",
            (target_id,),
        )
        if target_generation is not None:
            # A replaced recipient session cannot answer its old native prompt.
            db.execute(
                "UPDATE guild_invitations SET status='cancelled' WHERE target_id=%s AND status='pending' AND target_generation IS DISTINCT FROM %s",
                (target_id, target_generation),
            )
        pending = db.execute(
            "SELECT * FROM guild_invitations WHERE target_id=%s AND status='pending'",
            (target_id,),
        ).fetchone()
        if pending:
            if (
                pending["guild_id"] == g["id"]
                and pending["inviter_id"] == character_id
                and pending["target_generation"] == target_generation
            ):
                return pending["id"]
            raise ValueError("Target already has a pending guild invitation")
        seconds = p.get("invitation_seconds")
        if type(seconds) is not int or seconds <= 0:
            raise ValueError("Invalid invitation expiry policy")
        invitation = db.execute(
            "INSERT INTO guild_invitations(guild_id,inviter_id,target_id,target_generation,expires_at) VALUES(%s,%s,%s,%s,CURRENT_TIMESTAMP+%s*interval '1 second') RETURNING id",
            (g["id"], character_id, target_id, target_generation, seconds),
        ).fetchone()["id"]
        self._event(
            db,
            g["id"],
            "invited",
            {"invitation_id": invitation, "target_id": target_id},
        )
        return invitation

    def invite_character(self, account_id, generation, character_id, target_id):
        """Internal offline invitation API; native invitations use invite by name."""
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            return self._invite(db, p, g, character_id, target_id)

    def invite(self, account_id, generation, character_id, target_name):
        # Maintain the explicit numeric backend API used by integration fixtures.
        if type(target_name) is int:
            return self.invite_character(
                account_id, generation, character_id, target_name
            )
        if not isinstance(target_name, str):
            raise ValueError("Invalid invitation target name")
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            target = db.execute(
                "SELECT c.id,s.generation FROM characters c JOIN sessions s ON s.character_id=c.id AND s.account_id=c.account_id WHERE c.name=%s AND c.deleted_at IS NULL AND s.expires_at>CURRENT_TIMESTAMP",
                (target_name,),
            ).fetchone()
            if target is None:
                raise ValueError(
                    "Invitation target is not connected on selected character"
                )
            self._invite(db, p, g, character_id, target["id"], target["generation"])
            inviter = db.execute(
                "SELECT name FROM characters WHERE id=%s", (character_id,)
            ).fetchone()
            return {
                "inviter_name": inviter["name"],
                "guild_name": g["name"],
                "target_id": target["id"],
                "target_generation": target["generation"],
            }

    def respond_invitation(self, account_id, generation, character_id, accepted):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            invitation = db.execute(
                "SELECT id FROM guild_invitations WHERE target_id=%s AND target_generation=%s AND status='pending' AND expires_at>CURRENT_TIMESTAMP",
                (character_id, generation),
            ).fetchone()
            if invitation is None:
                raise ValueError("No pending invitation for current selected session")
            return self._answer(
                db, p, generation, character_id, invitation["id"], accepted
            )

    def invitation_answer(
        self, account_id, generation, character_id, invitation_id, accept
    ):
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            return self._answer(db, p, generation, character_id, invitation_id, accept)

    def _answer(self, db, p, generation, character_id, invitation_id, accept):
        if type(accept) is not bool:
            raise ValueError("Invalid invitation response")
        invitation = db.execute(
            "SELECT * FROM guild_invitations WHERE id=%s AND target_id=%s",
            (invitation_id, character_id),
        ).fetchone()
        if invitation is None:
            raise ValueError("Unknown invitation")
        g = db.execute(
            "SELECT * FROM guilds WHERE id=%s AND dissolved_at IS NULL FOR UPDATE",
            (invitation["guild_id"],),
        ).fetchone()
        invitation = db.execute(
            "SELECT * FROM guild_invitations WHERE id=%s AND status='pending' AND expires_at>CURRENT_TIMESTAMP FOR UPDATE",
            (invitation_id,),
        ).fetchone()
        if (
            g is None
            or invitation is None
            or invitation["target_generation"] not in (None, generation)
        ):
            raise ValueError("Invitation unavailable or expired")
        if accept:
            self._permission(db, g, invitation["inviter_id"], p, "invite")
            if db.execute(
                "SELECT 1 FROM guild_members WHERE character_id=%s", (character_id,)
            ).fetchone():
                raise ValueError("Character already belongs to a guild")
            count = db.execute(
                "SELECT count(*) AS n FROM guild_members WHERE guild_id=%s", (g["id"],)
            ).fetchone()["n"]
            capacity = p.get("max_members")
            if type(capacity) is int:
                capacity += g.get("member_capacity_bonus", 0)
            if type(capacity) is not int or count >= capacity:
                raise ValueError("Guild capacity reached")
            rank = db.execute(
                "SELECT id FROM guild_ranks WHERE guild_id=%s AND position>0 ORDER BY position DESC LIMIT 1",
                (g["id"],),
            ).fetchone()
            if rank is None:
                raise ValueError("Guild has no member rank")
            db.execute(
                "INSERT INTO guild_members(character_id,guild_id,rank_id) VALUES(%s,%s,%s)",
                (character_id, g["id"], rank["id"]),
            )
        db.execute(
            "UPDATE guild_invitations SET status=%s WHERE id=%s",
            ("accepted" if accept else "rejected", invitation_id),
        )
        self._event(
            db,
            g["id"],
            "invitation_answer",
            {"character_id": character_id, "accepted": accept},
        )
        return self._snapshot(db, g["id"])

    def change_identity(
        self, account_id, generation, character_id, field, value, *, operation_key
    ):
        """Change name or emblem under explicit local leader/cost policy."""
        if (
            field not in ("name", "blazon")
            or not isinstance(operation_key, str)
            or not 1 <= len(operation_key) <= 200
        ):
            raise ValueError("Invalid guild identity operation")
        request = dict(operation="guild_identity", field=field, value=value)
        with self.store.connection() as db:
            p = self._start(db, account_id, generation, character_id)
            g = self._guild(db, character_id)
            policy = p.get("identity_changes", {}).get(field, {})
            if policy.get("enabled") is not True or policy.get("authority") != "leader":
                raise ValueError("Guild identity change policy is unavailable")
            if g["leader_id"] != character_id:
                raise ValueError("Only guild leader can change identity")
            receipt = db.execute(
                "SELECT request,result FROM guild_operation_receipts WHERE character_id=%s AND operation_key=%s",
                (character_id, operation_key),
            ).fetchone()
            if receipt:
                if (
                    receipt["request"] != request
                    or receipt["result"].get("guild_id") != g["id"]
                ):
                    raise ValueError("Operation key reused with a different request")
                return self._snapshot(db, g["id"])
            if field == "name":
                value = self._identity_name(value, p)
                name_key = unicodedata.normalize("NFKC", value).casefold()
            else:
                self._identity_blazon(value)
            cost, item = policy.get("kamas"), policy.get("item")
            if type(cost) is not int or cost < 0 or type(item) is not int or item <= 0:
                raise ValueError("Explicit identity change cost policy required")
            if value == g[field]:
                raise ValueError("Guild identity already has requested value")
            self._consume_identity_cost(db, account_id, character_id, item, cost)
            if field == "name":
                db.execute(
                    "UPDATE guilds SET name=%s,name_key=%s WHERE id=%s",
                    (value, name_key, g["id"]),
                )
            else:
                db.execute("UPDATE guilds SET blazon=%s WHERE id=%s", (value, g["id"]))
            self._event(
                db, g["id"], "identity_changed", {"field": field, "value": value}
            )
            db.execute(
                "INSERT INTO guild_operation_receipts(character_id,operation_key,request,result) VALUES(%s,%s,%s,%s)",
                (
                    character_id,
                    operation_key,
                    Jsonb(request),
                    Jsonb({"guild_id": g["id"]}),
                ),
            )
            return self._snapshot(db, g["id"])

    @classmethod
    def _identity_name(cls, name, policy):
        from .guild_native_validators import validate_name_structure

        value = validate_name_structure(name)
        cls._name_bounds(value)
        if (
            policy.get("primary_identity_only") is True
            or policy.get("management_enabled") is True
        ):
            # Wakemu deliberately disables local censorship for this bounded
            # capability; this is not an absent or recovered official word list.
            if (
                policy.get("name_validation") != "native_structure"
                or policy.get("name_normalization") != "NFKC_CASEFOLD"
                or policy.get("local_name_censorship")
                != {"enabled": False, "patterns": []}
            ):
                raise ValueError("Guild primary name policy is unavailable")
            return value
        # Structural approval is distinct from censorship and the existing
        # explicit database uniqueness policy. Keep those fail-closed.
        pattern = policy.get("name_pattern")
        if (
            not isinstance(pattern, str)
            or not pattern
            or not re.fullmatch(pattern, value)
            or policy.get("name_normalization") != "NFKC_CASEFOLD"
        ):
            raise ValueError(
                "Guild name validation policy is unavailable or rejects name"
            )
        return value

    @staticmethod
    def _identity_blazon(value):
        from .guild_native_validators import decode_blazon

        decode_blazon(value)

    @staticmethod
    def _initial_rank_masks(policy):
        from .guild_native_validators import catalog, validate_rank_mask

        native = catalog()
        result = []
        for key, expected, highest in (
            ("leader_permissions", native["highest_rank_authorizations"], True),
            ("member_permissions", native["lowest_rank_authorizations"], False),
        ):
            configured = policy.get(key)
            if configured is not None and (
                type(configured) is not int or configured != expected
            ):
                raise ValueError(
                    "Initial guild rank permissions conflict with the native contract"
                )
            result.append(
                validate_rank_mask(expected, highest=highest, lowest=not highest)
            )
        return result

    @staticmethod
    def _name_bounds(name):
        if (
            not 5 <= len(name.encode("utf-16-le")) // 2 <= 30
            or len(name.encode("utf-8")) > 127
        ):
            raise ValueError("Guild name exceeds native character or byte bounds")

    def _consume_identity_cost(self, db, account_id, character_id, item, cost):
        """Consume one plain policy item and account currency atomically.

        Policy items are fixed identity consumables, never arbitrary client
        inventory references. Domain-specific mount/companion state is excluded.
        """
        if item not in (16942, 25100, 25101):
            raise ValueError("Guild identity item lacks plain consumable contract")
        from wakfu_server.simple_item_actions import _idle

        _idle(db, character_id, self.store.now())
        wallet = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        items = db.execute(
            "SELECT uid,quantity FROM inventory_items WHERE character_id=%s AND reference=%s ORDER BY uid LIMIT 1 FOR UPDATE",
            (character_id, item),
        ).fetchone()
        if wallet is None or wallet["kamas"] < cost or items is None:
            raise ValueError("Guild identity requirements not met")
        db.execute(
            "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s",
            (cost, account_id),
        )
        if items["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (items["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (items["uid"],),
            )
