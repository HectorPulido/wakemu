"""Authenticated native account conversations over the separate intergame transport."""
import re
import secrets

from wakfu_server.social_contacts import _authorize
from wakfu_server.account_bans import require_access


_CHANNEL = re.compile(r"DM_([1-9][0-9]*)_([1-9][0-9]*)\Z")


def channel_id(first, second):
    if (
        any(
            type(value) is not int or not 0 < value < 1 << 63
            for value in (first, second)
        )
        or first == second
    ):
        raise ValueError("Invalid intergame participants")
    return f"DM_{min(first, second)}_{max(first, second)}"


def user(row):
    # Local account names are unique. The stable local tag is the account ID.
    return {"user_id": row["id"], "name": row["username"], "tag": str(row["id"])}


class Intergame:
    def __init__(self, store):
        self.store = store

    def issue_token(self, api_key):
        if type(api_key) is not str or not 20 <= len(api_key) <= 512:
            raise PermissionError("Invalid intergame authentication")
        token = secrets.token_urlsafe(32)
        with self.store.connection() as db:
            owner = db.execute(
                "SELECT account_id FROM tokens WHERE digest=%s AND kind='api'",
                (self.store.digest(api_key),),
            ).fetchone()
            if owner is None:
                raise PermissionError(
                    "Intergame session expired; reconnect to the game"
                )
            require_access(db, owner["account_id"], self.store.now())
            row = db.execute(
                "SELECT t.account_id,t.generation FROM tokens t JOIN sessions s "
                "ON s.account_id=t.account_id AND s.generation=t.generation "
                "WHERE t.digest=%s AND t.kind='api' AND t.expires_at>%s "
                "AND s.expires_at>%s FOR UPDATE OF s",
                (self.store.digest(api_key), self.store.now(), self.store.now()),
            ).fetchone()
            if row is None:
                raise PermissionError(
                    "Intergame session expired; reconnect to the game"
                )
            db.execute(
                "DELETE FROM intergame_tokens WHERE expires_at<=%s", (self.store.now(),)
            )
            db.execute(
                "INSERT INTO intergame_tokens(digest,account_id,generation,expires_at) VALUES(%s,%s,%s,%s)",
                (
                    self.store.digest(token),
                    row["account_id"],
                    row["generation"],
                    self.store.now(60),
                ),
            )
        return {"token": token}

    def authenticate(self, token):
        if type(token) is not str or not 20 <= len(token) <= 512:
            raise PermissionError("Invalid intergame token")
        with self.store.connection() as db:
            owner = db.execute(
                "SELECT account_id FROM intergame_tokens WHERE digest=%s",
                (self.store.digest(token),),
            ).fetchone()
            if owner is None:
                raise PermissionError("Intergame token expired or consumed")
            require_access(db, owner["account_id"], self.store.now())
            row = db.execute(
                "SELECT t.account_id,t.generation FROM intergame_tokens t JOIN sessions s "
                "ON s.account_id=t.account_id AND s.generation=t.generation "
                "WHERE t.digest=%s AND t.expires_at>%s AND s.expires_at>%s FOR UPDATE OF s,t",
                (self.store.digest(token), self.store.now(), self.store.now()),
            ).fetchone()
            if row is None:
                raise PermissionError("Intergame token expired or consumed")
            db.execute(
                "DELETE FROM intergame_tokens WHERE digest=%s",
                (self.store.digest(token),),
            )
            return dict(row)

    def _authorize(self, db, identity):
        require_access(db, identity["account_id"], self.store.now())
        _authorize(self.store, db, identity["account_id"], identity["generation"])

    def active(self, identity):
        with self.store.connection() as db:
            self._authorize(db, identity)

    @staticmethod
    def _same_account(request, identity):
        field = "author_user_id" if "author_user_id" in request else "user_id"
        if request.get(field) != identity["account_id"]:
            raise PermissionError("Intergame sender identity mismatch")

    def _target(self, db, account_id, channel):
        match = _CHANNEL.fullmatch(channel) if type(channel) is str else None
        if match is None:
            raise ValueError("Invalid native conversation ID")
        first, second = map(int, match.groups())
        if (
            first >= second
            or max(first, second) >= 1 << 63
            or account_id not in (first, second)
        ):
            raise PermissionError("Conversation belongs to another account")
        target = second if first == account_id else first
        row = db.execute(
            "SELECT id,username FROM accounts WHERE id=%s", (target,)
        ).fetchone()
        if row is None:
            raise ValueError("Unknown conversation recipient")
        return row

    def _allow_message(self, db, sender, target):
        if (
            db.execute(
                "SELECT 1 FROM account_bans WHERE account_id=%s AND (expires_at IS NULL OR expires_at>%s)",
                (target, self.store.now()),
            ).fetchone()
            is not None
        ):
            raise PermissionError("Recipient access is suspended")
        blocked = db.execute(
            "SELECT 1 FROM account_social_contacts WHERE relation='ignore' AND "
            "((owner_account_id=%s AND contact_account_id=%s) OR "
            "(owner_account_id=%s AND contact_account_id=%s))",
            (sender, target, target, sender),
        ).fetchone()
        dnd = db.execute(
            "SELECT do_not_disturb FROM account_social_preferences WHERE account_id=%s",
            (target,),
        ).fetchone()
        if blocked is not None or (dnd is not None and dnd["do_not_disturb"]):
            raise PermissionError("Recipient does not accept this conversation")
        friend = db.execute(
            "SELECT 1 FROM account_social_contacts WHERE owner_account_id=%s "
            "AND contact_account_id=%s AND relation='friend'",
            (sender, target),
        ).fetchone()
        if friend is None:
            raise PermissionError("Recipient is not in the native friend directory")

    @staticmethod
    def _message(row, author):
        return {
            "message_id": str(row["id"]),
            "channel_id": channel_id(
                row["sender_account_id"], row["recipient_account_id"]
            ),
            "created_timestamp": int(row["created_at"].timestamp() * 1000),
            "content": row["content"],
            "author": user(author),
        }

    def handle(self, identity, name, request):
        """Return (response type, response body, targeted native events)."""
        account = identity["account_id"]
        events = []
        with self.store.connection() as db:
            self._authorize(db, identity)
            if name.startswith("user.") or name == "channel.CreateChannelMessageCmd":
                self._same_account(request, identity)
            if name == "user.ListUserFriendsCmd":
                rows = db.execute(
                    "SELECT a.id,a.username FROM account_social_contacts c JOIN accounts a ON a.id=c.contact_account_id "
                    "WHERE c.owner_account_id=%s AND c.relation='friend' ORDER BY a.username_key",
                    (account,),
                ).fetchall()
                return (
                    "user.FriendList",
                    {"values": [{"user": user(row)} for row in rows]},
                    [],
                )
            if name == "user.ListUserBlockedUsersCmd":
                rows = db.execute(
                    "SELECT a.id,a.username FROM account_social_contacts c JOIN accounts a ON a.id=c.contact_account_id "
                    "WHERE c.owner_account_id=%s AND c.relation='ignore' ORDER BY a.username_key",
                    (account,),
                ).fetchall()
                return "user.UserList", {"values": [user(row) for row in rows]}, []
            if name == "user.ListUserFriendGroupsCmd":
                return "user.FriendGroupList", {}, []
            if name == "user.ListUserFriendInvitesCmd":
                rows = db.execute(
                    "SELECT i.inviter_account_id,i.recipient_account_id,a.username AS inviter_name,b.username AS recipient_name "
                    "FROM intergame_friend_invites i JOIN accounts a ON a.id=i.inviter_account_id "
                    "JOIN accounts b ON b.id=i.recipient_account_id "
                    "WHERE i.inviter_account_id=%s OR i.recipient_account_id=%s",
                    (account, account),
                ).fetchall()
                return (
                    "friend_invite.FriendInviteList",
                    {"values": [self._invite(row) for row in rows]},
                    [],
                )
            if name in (
                "user.UpdateUserStatusCmd",
                "user.UpdateUserEndpointPropertiesCmd",
            ):
                if name == "user.UpdateUserStatusCmd":
                    status = request.get("status", 0)
                    if type(status) is not int or status not in (0, 1, 2):
                        raise ValueError("Invalid intergame status")
                    db.execute(
                        "INSERT INTO intergame_account_state(account_id,status) VALUES(%s,%s) "
                        "ON CONFLICT(account_id) DO UPDATE SET status=EXCLUDED.status",
                        (account, status),
                    )
                # Endpoint metadata is not an authority for account, map or privileges.
                return None, None, []
            if name == "channel.CreateChannelMessageCmd":
                target = self._target(db, account, request.get("channel_id"))
                text = request.get("content")
                if (
                    type(text) is not str
                    or not text.strip()
                    or "\x00" in text
                    or len(text.encode()) > 2048
                ):
                    raise ValueError("Invalid intergame message text")
                self._allow_message(db, account, target["id"])
                policy = db.execute(
                    "SELECT value FROM settings WHERE name='chat_channel_policy'"
                ).fetchone()
                policy = None if policy is None else policy["value"]
                if (
                    type(policy) is not dict
                    or policy.get("version") != 1
                    or type(policy.get("minimum_interval_ms")) is not int
                    or not 1 <= policy["minimum_interval_ms"] <= 60000
                    or type(policy.get("maximum_bytes")) is not int
                    or not 1 <= policy["maximum_bytes"] <= 2048
                ):
                    raise ValueError("Invalid chat rate policy")
                if len(text.encode()) > policy["maximum_bytes"]:
                    raise ValueError("Intergame message is too long")
                previous = db.execute(
                    "SELECT created_at FROM intergame_messages WHERE sender_account_id=%s ORDER BY id DESC LIMIT 1",
                    (account,),
                ).fetchone()
                if (
                    previous is not None
                    and (self.store.now() - previous["created_at"]).total_seconds()
                    * 1000
                    < policy["minimum_interval_ms"]
                ):
                    raise PermissionError("Intergame chat rate exceeded")
                row = db.execute(
                    "INSERT INTO intergame_messages(sender_account_id,recipient_account_id,content,created_at) "
                    "VALUES(%s,%s,%s,%s) RETURNING *",
                    (account, target["id"], text, self.store.now()),
                ).fetchone()
                author = db.execute(
                    "SELECT id,username FROM accounts WHERE id=%s", (account,)
                ).fetchone()
                message = self._message(row, author)
                events = [
                    (peer, "channel.ChannelMessageCreatedEvt", {"message": message})
                    for peer in (account, target["id"])
                ]
                return "channel.ChannelMessage", message, events
            if name == "channel.ListChannelMessagesCmd":
                target = self._target(db, account, request.get("channel_id"))
                self._allow_message(db, account, target["id"])
                limit = request.get("limit", 20)
                if type(limit) is not int or not 1 <= limit <= 100:
                    raise ValueError("Invalid conversation history limit")
                boundary, comparison = (
                    request.get("before", request.get("after")),
                    "<" if "before" in request else ">",
                )
                if boundary is not None and (
                    type(boundary) is not str
                    or not boundary.isdecimal()
                    or len(boundary) > 19
                    or not 0 < int(boundary) < 1 << 63
                ):
                    raise ValueError("Invalid conversation cursor")
                rows = db.execute(
                    "SELECT m.*,a.username FROM intergame_messages m JOIN accounts a ON a.id=m.sender_account_id "
                    "WHERE LEAST(sender_account_id,recipient_account_id)=%s AND GREATEST(sender_account_id,recipient_account_id)=%s "
                    + (f"AND m.id{comparison}%s " if boundary is not None else "")
                    + "ORDER BY m.id DESC LIMIT %s",
                    (
                        min(account, target["id"]),
                        max(account, target["id"]),
                        *(() if boundary is None else (int(boundary),)),
                        limit,
                    ),
                ).fetchall()
                return (
                    "channel.ChannelMessageList",
                    {
                        "values": [
                            self._message(
                                row,
                                {
                                    "id": row["sender_account_id"],
                                    "username": row["username"],
                                },
                            )
                            for row in reversed(rows)
                        ]
                    },
                    [],
                )
            if name == "friend_invite.CreateFriendInviteCmd":
                if request.get("inviter_user_id") != account:
                    raise PermissionError("Friend invitation identity mismatch")
                return self._create_invite(db, account, request)
            if name == "friend_invite.DeleteFriendInviteCmd":
                return self._resolve_invite(db, account, request)
            if name == "user.DeleteUserFriendCmd":
                target = request.get("friend_user_id")
                db.execute(
                    "DELETE FROM account_social_contacts WHERE owner_account_id=%s AND contact_account_id=%s AND relation='friend'",
                    (account, target),
                )
                return (
                    None,
                    None,
                    [
                        (
                            account,
                            "user.UserFriendDeletedEvt",
                            {"user_id": account, "friend_user_id": target},
                        )
                    ],
                )
            raise ValueError("Unsupported native intergame command")

    @staticmethod
    def _invite(row):
        return {
            "inviter": user(
                {"id": row["inviter_account_id"], "username": row["inviter_name"]}
            ),
            "recipient": user(
                {"id": row["recipient_account_id"], "username": row["recipient_name"]}
            ),
        }

    def _create_invite(self, db, account, request):
        if "recipient_user_id" in request:
            target = db.execute(
                "SELECT id,username FROM accounts WHERE id=%s",
                (request["recipient_user_id"],),
            ).fetchone()
        else:
            named = request.get("recipient_user_name_and_tag", {})
            name = named.get("name", request.get("recipient_user_name"))
            target = db.execute(
                "SELECT id,username FROM accounts WHERE username_key=%s",
                (name.casefold() if type(name) is str else "",),
            ).fetchone()
            if target is not None and named and named.get("tag") != str(target["id"]):
                target = None
        if target is None or target["id"] == account:
            raise ValueError("Unknown native friend recipient")
        if (
            db.execute(
                "SELECT 1 FROM account_bans WHERE account_id=%s AND (expires_at IS NULL OR expires_at>%s)",
                (target["id"], self.store.now()),
            ).fetchone()
            is not None
        ):
            raise PermissionError("Recipient access is suspended")
        if (
            db.execute(
                "SELECT 1 FROM account_social_contacts WHERE relation='ignore' AND ((owner_account_id=%s AND contact_account_id=%s) OR (owner_account_id=%s AND contact_account_id=%s))",
                (account, target["id"], target["id"], account),
            ).fetchone()
            is not None
        ):
            raise PermissionError("Friend invitation is blocked")
        db.execute(
            "INSERT INTO intergame_friend_invites(inviter_account_id,recipient_account_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (account, target["id"]),
        )
        inviter = db.execute(
            "SELECT id,username FROM accounts WHERE id=%s", (account,)
        ).fetchone()
        value = {"inviter": user(inviter), "recipient": user(target)}
        return (
            "friend_invite.FriendInvite",
            value,
            [
                (peer, "friend_invite.FriendInviteCreatedEvt", {"invite": value})
                for peer in (account, target["id"])
            ],
        )

    def _resolve_invite(self, db, account, request):
        inviter, recipient, reason = (
            request.get("inviter_user_id"),
            request.get("recipient_user_id"),
            request.get("reason", 0),
        )
        if reason not in (0, 1, 2) or account != (
            inviter if reason == 2 else recipient
        ):
            raise PermissionError("Cannot resolve another account's invitation")
        row = db.execute(
            "DELETE FROM intergame_friend_invites WHERE inviter_account_id=%s AND recipient_account_id=%s RETURNING *",
            (inviter, recipient),
        ).fetchone()
        if row is None:
            raise ValueError("Friend invitation no longer exists")
        inviter_row = db.execute(
            "SELECT id,username FROM accounts WHERE id=%s", (inviter,)
        ).fetchone()
        recipient_row = db.execute(
            "SELECT id,username FROM accounts WHERE id=%s", (recipient,)
        ).fetchone()
        invite = {"inviter": user(inviter_row), "recipient": user(recipient_row)}
        events = [
            (
                peer,
                "friend_invite.FriendInviteDeletedEvt",
                {"invite": invite, "reason": reason},
            )
            for peer in (inviter, recipient)
        ]
        if reason == 0:
            for owner, contact in ((inviter, recipient), (recipient, inviter)):
                if (
                    db.execute(
                        "SELECT 1 FROM account_bans WHERE account_id=%s AND (expires_at IS NULL OR expires_at>%s)",
                        (contact, self.store.now()),
                    ).fetchone()
                    is not None
                ):
                    raise PermissionError("Friend access is suspended")
                previous = db.execute(
                    "SELECT relation FROM account_social_contacts WHERE owner_account_id=%s AND contact_account_id=%s",
                    (owner, contact),
                ).fetchone()
                if previous is not None and previous["relation"] == "ignore":
                    raise PermissionError("Friend invitation is blocked")
                db.execute(
                    "INSERT INTO account_social_contacts(owner_account_id,contact_account_id,relation) VALUES(%s,%s,'friend') ON CONFLICT DO NOTHING",
                    (owner, contact),
                )
                row = db.execute(
                    "SELECT id,username FROM accounts WHERE id=%s", (contact,)
                ).fetchone()
                events.append(
                    (
                        owner,
                        "user.UserFriendCreatedEvt",
                        {"user_id": owner, "friend": {"user": user(row)}},
                    )
                )
        return None, None, events
