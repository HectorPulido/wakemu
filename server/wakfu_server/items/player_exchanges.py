"""Durable bilateral exchange authority and atomic inventory/currency commit.

Both selected session generations are locked before either character, in
stable account/character order. No client packet can supply an owner account.
"""
from psycopg.types.json import Jsonb


def _policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='player_exchange_policy'"
    ).fetchone()
    value = row["value"] if row else None
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] != 1
        or type(value.get("invitation_seconds")) is not int
        or not 1 <= value["invitation_seconds"] <= 300
        or type(value.get("maximum_offer_items")) is not int
        or not 1 <= value["maximum_offer_items"] <= 128
    ):
        raise ValueError("Invalid exchange policy")
    return value


def _lock_pair(store, db, owners):
    if len(owners) != 2 or len({entry[0] for entry in owners}) != 2:
        raise ValueError("Exchange requires two distinct accounts")
    for account, character, generation in sorted(owners):
        row = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
            "AND expires_at>%s FOR UPDATE",
            (account, generation, store.now()),
        ).fetchone()
        if row is None or row["character_id"] != character:
            raise ValueError("Exchange participant session is stale or offline")
    for account, character, generation in sorted(owners, key=lambda entry: entry[1]):
        if (
            db.execute(
                "SELECT id FROM characters WHERE account_id=%s AND id=%s FOR UPDATE",
                (account, character),
            ).fetchone()
            is None
        ):
            raise ValueError("Invalid exchange owner")
    # Fight entry uses the same session/character locks. Read its durable
    # state under those locks; never modify combat or permit escrow mid-fight.
    if (
        db.execute(
            "SELECT 1 FROM combat_fight_participants p "
            "JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=ANY(%s) AND f.status IN ('placement','active') LIMIT 1",
            ([entry[1] for entry in owners],),
        ).fetchone()
        is not None
    ):
        raise ValueError("Exchange participant is in combat")


def _owners(exchange):
    return [
        (
            exchange[f"{side}_account"],
            exchange[f"{side}_id"],
            exchange[f"{side}_generation"],
        )
        for side in ("inviter", "invitee")
    ]


def _outbox(store, db, exchange, event, *, canceled_by=None, previous_state=None):
    members = [
        dict(row)
        for row in db.execute(
            "SELECT character_id,offered_kamas,published_revision,confirmed_revision "
            "FROM player_exchange_members WHERE exchange_id=%s ORDER BY character_id",
            (exchange["id"],),
        )
    ]
    items = [
        dict(row)
        for row in db.execute(
            "SELECT character_id,uid,quantity FROM player_exchange_items "
            "WHERE exchange_id=%s ORDER BY character_id,uid",
            (exchange["id"],),
        )
    ]
    if exchange["state"] == "active":
        from .inventory_items import load
        from .inventory_shards import json_safe_item

        units = {}
        for account, character, generation in _owners(exchange):
            units.update({unit["uid"]: unit for unit in load(db, character)})
        for offer in items:
            unit = units.get(offer["uid"])
            if unit is None or unit["character_id"] != offer["character_id"]:
                raise ValueError("Offered exchange unit disappeared before publication")
            offer["unit"] = json_safe_item(dict(unit, quantity=offer["quantity"]))
    for account, character, generation in _owners(exchange):
        db.execute(
            "INSERT INTO player_exchange_outbox(exchange_id,revision,character_id,"
            "generation,event,payload,created_at,delivery_sequence) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(exchange_id,delivery_sequence,character_id,event) DO NOTHING",
            (
                exchange["id"],
                exchange["revision"],
                character,
                generation,
                event,
                Jsonb(
                    {
                        "state": exchange["state"],
                        "inviter_id": exchange["inviter_id"],
                        "invitee_id": exchange["invitee_id"],
                        "members": members,
                        "items": items,
                        "canceled_by": canceled_by,
                        "previous_state": previous_state,
                    }
                ),
                store.now(),
                exchange["delivery_sequence"],
            ),
        )


def invite(store, account_id, generation, character_id, target_id):
    if type(target_id) is not int or target_id <= 0 or target_id == character_id:
        raise ValueError("Invalid exchange target")
    with store.connection() as db:
        target = db.execute(
            "SELECT account_id,generation FROM sessions WHERE character_id=%s "
            "AND expires_at>%s",
            (target_id, store.now()),
        ).fetchone()
        if target is None:
            raise ValueError("Exchange target is offline")
        owners = [
            (account_id, character_id, generation),
            (target["account_id"], target_id, target["generation"]),
        ]
        _lock_pair(store, db, owners)
        if db.execute(
            "SELECT 1 FROM player_exchange_members WHERE character_id IN (%s,%s)",
            (character_id, target_id),
        ).fetchone():
            raise ValueError("Exchange participant is busy")
        policy = _policy(db)
        exchange = dict(
            db.execute(
                "INSERT INTO player_exchanges(inviter_id,invitee_id,inviter_account,invitee_account,"
                "inviter_generation,invitee_generation,created_at,expires_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    character_id,
                    target_id,
                    account_id,
                    target["account_id"],
                    generation,
                    target["generation"],
                    store.now(),
                    store.now(policy["invitation_seconds"]),
                ),
            ).fetchone()
        )
        for account, character, peer_generation in owners:
            db.execute(
                "INSERT INTO player_exchange_members(character_id,exchange_id) VALUES(%s,%s)",
                (character, exchange["id"]),
            )
        _outbox(store, db, exchange, "snapshot")
        return exchange


def answer(store, account_id, generation, character_id, exchange_id, accepted):
    if type(accepted) is not bool:
        raise ValueError("Invalid exchange invitation answer")
    with store.connection() as db:
        initial = db.execute(
            "SELECT * FROM player_exchanges WHERE id=%s", (exchange_id,)
        ).fetchone()
        if (
            initial is None
            or initial["invitee_id"] != character_id
            or initial["invitee_account"] != account_id
            or initial["invitee_generation"] != generation
        ):
            raise ValueError("Unknown owned exchange invitation")
        _lock_pair(store, db, _owners(initial))
        exchange = db.execute(
            "SELECT * FROM player_exchanges WHERE id=%s FOR UPDATE", (exchange_id,)
        ).fetchone()
        if exchange["state"] != "invitation" or exchange["expires_at"] <= store.now():
            raise ValueError("Exchange invitation expired or already answered")
        state = "active" if accepted else "canceled"
        exchange = dict(
            db.execute(
                "UPDATE player_exchanges SET state=%s,revision=revision+1,"
                "delivery_sequence=delivery_sequence+1 "
                "WHERE id=%s RETURNING *",
                (state, exchange_id),
            ).fetchone()
        )
        _outbox(
            store,
            db,
            exchange,
            "snapshot" if accepted else "canceled",
            canceled_by=None if accepted else character_id,
            previous_state="invitation",
        )
        if not accepted:
            db.execute(
                "DELETE FROM player_exchange_members WHERE exchange_id=%s",
                (exchange_id,),
            )
        return exchange


def expire(store, *, limit=128):
    """Bounded timeout/stale-session cleanup without upstream locks or sockets.

    Lifecycle operations lock the exchange before changing its memberships.
    This worker never takes their upstream session/character locks, avoiding
    the inverse lock order while freeing players whose invitation timed out.
    """
    if type(limit) is not int or not 1 <= limit <= 128:
        raise ValueError("Invalid exchange expiration limit")
    with store.connection() as db:
        rows = db.execute(
            "SELECT e.* FROM player_exchanges e WHERE e.state IN ('invitation','active') AND ("
            "(e.state='invitation' AND e.expires_at<=%s) OR NOT EXISTS ("
            "SELECT 1 FROM sessions s WHERE s.account_id=e.inviter_account "
            "AND s.character_id=e.inviter_id AND s.generation=e.inviter_generation AND s.expires_at>%s) "
            "OR NOT EXISTS (SELECT 1 FROM sessions s WHERE s.account_id=e.invitee_account "
            "AND s.character_id=e.invitee_id AND s.generation=e.invitee_generation AND s.expires_at>%s)) "
            "ORDER BY e.expires_at,e.id LIMIT %s FOR UPDATE OF e SKIP LOCKED",
            (store.now(), store.now(), store.now(), limit),
        ).fetchall()
        expired = []
        for row in rows:
            state = "expired" if row["state"] == "invitation" else "canceled"
            exchange = dict(
                db.execute(
                    "UPDATE player_exchanges SET state=%s,revision=revision+1,"
                    "delivery_sequence=delivery_sequence+1 "
                    "WHERE id=%s RETURNING *",
                    (state, row["id"]),
                ).fetchone()
            )
            _outbox(store, db, exchange, "canceled", previous_state=row["state"])
            db.execute(
                "DELETE FROM player_exchange_members WHERE exchange_id=%s", (row["id"],)
            )
            expired.append(row["id"])
        return expired


def cancel(
    store, account_id, generation, character_id, exchange_id, *, expected_state=None
):
    """An owned live participant may cancel even if the other disconnected."""
    if expected_state not in (None, "invitation", "active"):
        raise ValueError("Invalid expected exchange state")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        exchange = db.execute(
            "SELECT * FROM player_exchanges WHERE id=%s FOR UPDATE", (exchange_id,)
        ).fetchone()
        if exchange is None or (account_id, character_id, generation) not in _owners(
            exchange
        ):
            raise ValueError("Unknown owned exchange")
        if expected_state is not None and exchange["state"] != expected_state:
            raise ValueError("Exchange state changed before cancellation")
        if exchange["state"] in ("committed", "canceled", "expired"):
            return dict(exchange)
        previous_state = exchange["state"]
        exchange = dict(
            db.execute(
                "UPDATE player_exchanges SET state='canceled',revision=revision+1,"
                "delivery_sequence=delivery_sequence+1 "
                "WHERE id=%s RETURNING *",
                (exchange_id,),
            ).fetchone()
        )
        _outbox(
            store,
            db,
            exchange,
            "canceled",
            canceled_by=character_id,
            previous_state=previous_state,
        )
        db.execute(
            "DELETE FROM player_exchange_members WHERE exchange_id=%s", (exchange_id,)
        )
        return exchange


def _active(
    store,
    db,
    account_id,
    generation,
    character_id,
    exchange_id,
    *,
    allow_committed=False,
):
    initial = db.execute(
        "SELECT * FROM player_exchanges WHERE id=%s", (exchange_id,)
    ).fetchone()
    if initial is None or (account_id, character_id, generation) not in _owners(
        initial
    ):
        raise ValueError("Unknown owned exchange")
    _lock_pair(store, db, _owners(initial))
    # Balance is account-scoped. Lock both before the exchange, matching commit
    # order and the character-before-wallet order of other inventory rewards.
    wallets = {}
    for account, character, peer_generation in sorted(_owners(initial)):
        row = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
            (account,),
        ).fetchone()
        if row is None:
            raise ValueError("Exchange account wallet unavailable")
        wallets[account] = row["kamas"]
    exchange = db.execute(
        "SELECT * FROM player_exchanges WHERE id=%s FOR UPDATE", (exchange_id,)
    ).fetchone()
    if allow_committed and exchange["state"] == "committed":
        return exchange, wallets
    if exchange["state"] != "active":
        raise ValueError("Exchange is not active")
    members = list(
        db.execute(
            "SELECT * FROM player_exchange_members WHERE exchange_id=%s", (exchange_id,)
        )
    )
    if {row["character_id"] for row in members} != {
        entry[1] for entry in _owners(exchange)
    }:
        raise ValueError("Exchange membership is incomplete")
    return exchange, wallets


def _changed(store, db, exchange_id):
    db.execute(
        "UPDATE player_exchange_members SET confirmed_revision=NULL "
        "WHERE exchange_id=%s",
        (exchange_id,),
    )
    exchange = dict(
        db.execute(
            "UPDATE player_exchanges SET revision=revision+1,"
            "delivery_sequence=delivery_sequence+1 "
            "WHERE id=%s RETURNING *",
            (exchange_id,),
        ).fetchone()
    )
    _outbox(store, db, exchange, "snapshot")
    return exchange


def offer_kamas(store, account_id, generation, character_id, exchange_id, kamas):
    if type(kamas) is not int or not 0 <= kamas < 2**63:
        raise ValueError("Invalid exchange kamas offer")
    with store.connection() as db:
        exchange, wallets = _active(
            store, db, account_id, generation, character_id, exchange_id
        )
        if kamas > wallets[account_id]:
            raise ValueError("Exchange kamas offer exceeds account balance")
        member = db.execute(
            "SELECT offered_kamas FROM player_exchange_members "
            "WHERE exchange_id=%s AND character_id=%s",
            (exchange_id, character_id),
        ).fetchone()
        if member["offered_kamas"] == kamas:
            return dict(exchange)
        db.execute(
            "UPDATE player_exchange_members SET offered_kamas=%s "
            "WHERE exchange_id=%s AND character_id=%s",
            (kamas, exchange_id, character_id),
        )
        return _changed(store, db, exchange_id)


def published(store, account_id, generation, character_id, exchange_id, revision):
    """Delivery adapter acknowledges only its successfully sent current offer.

    This is an internal operation, not a client opcode accepting a revision.
    Its caller must serialize packet publication with invitation/offer changes.
    """
    if type(revision) is not int or revision <= 0:
        raise ValueError("Invalid exchange publication revision")
    with store.connection() as db:
        exchange, wallets = _active(
            store, db, account_id, generation, character_id, exchange_id
        )
        if exchange["revision"] != revision:
            raise ValueError("Exchange publication revision is stale")
        db.execute(
            "UPDATE player_exchange_members SET published_revision=%s "
            "WHERE exchange_id=%s AND character_id=%s",
            (revision, exchange_id, character_id),
        )
        return dict(exchange)


def _offered_item(store, db, account_id, character_id, uid, quantity):
    from .exchange_rules import eligibility, ITEMS
    from .inventory_move import STACKS
    from wakfu_server.wire import proto_fields

    item = db.execute(
        "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
        (uid, character_id),
    ).fetchone()
    if item is None or quantity > item["quantity"]:
        raise ValueError("Exchange item is unavailable or foreign")
    rule = STACKS.get(item["reference"])
    if rule is None or item["quantity"] > rule["maximum"]:
        raise ValueError("Exchange item has an unsupported stack")
    binding = db.execute(
        "SELECT * FROM inventory_item_bindings WHERE uid=%s", (uid,)
    ).fetchone()
    if binding is not None and binding["template_reference"] != item["reference"]:
        raise ValueError("Exchange item binding reference differs")
    if not eligibility(item["reference"], bound=binding["bound"] if binding else None):
        raise ValueError("Native item binding or criterion prohibits exchange")
    character = store.character(account_id, character_id, db)
    for build in character["builds"].values():
        for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
            if tag == 10 and dict(proto_fields(value)).get(8) == uid:
                raise ValueError("Desequip the exchange item from every build first")
    if binding is None:
        db.execute(
            "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,%s,%s)",
            (
                uid,
                ITEMS[str(item["reference"])]["binding_template"]["default_eKo"],
                item["reference"],
            ),
        )
    return dict(item)


def offer_item(
    store,
    account_id,
    generation,
    character_id,
    exchange_id,
    uid,
    quantity,
    *,
    operation="replace",
):
    """Set this owned unit's offer quantity; zero withdraws the existing offer.

    Neither adding nor withdrawing an offer moves or reserves inventory units.
    The bilateral commit must revalidate ownership, eligibility and quantity.
    """
    if (
        type(uid) is not int
        or not 0 < uid < 2**63
        or type(quantity) is not int
        or not 0 <= quantity <= 32767
    ):
        raise ValueError("Invalid exchange item offer")
    if operation not in ("replace", "add", "remove"):
        raise ValueError("Invalid exchange quantity operation")
    with store.connection() as db:
        exchange, wallets = _active(
            store, db, account_id, generation, character_id, exchange_id
        )
        old = db.execute(
            "SELECT character_id,quantity FROM player_exchange_items "
            "WHERE exchange_id=%s AND uid=%s",
            (exchange_id, uid),
        ).fetchone()
        if old is not None and old["character_id"] != character_id:
            raise ValueError("Cannot alter the other participant's offer")
        if operation != "replace":
            if quantity == 0:
                raise ValueError("Exchange quantity delta must be positive")
            prior_quantity = old["quantity"] if old is not None else 0
            quantity = (
                prior_quantity + quantity
                if operation == "add"
                else prior_quantity - quantity
            )
            if not 0 <= quantity <= 32767:
                raise ValueError("Exchange quantity delta exceeds the offer")
        if quantity == 0:
            if old is None:
                raise ValueError("Exchange item was not offered")
            db.execute(
                "DELETE FROM player_exchange_items WHERE exchange_id=%s AND uid=%s",
                (exchange_id, uid),
            )
        else:
            _offered_item(store, db, account_id, character_id, uid, quantity)
            if old is not None and old["quantity"] == quantity:
                return dict(exchange)
            if old is None:
                count = db.execute(
                    "SELECT count(*) AS n FROM player_exchange_items "
                    "WHERE exchange_id=%s AND character_id=%s",
                    (exchange_id, character_id),
                ).fetchone()["n"]
                if count >= _policy(db)["maximum_offer_items"]:
                    raise ValueError("Exchange item offer is full")
            db.execute(
                "INSERT INTO player_exchange_items(exchange_id,character_id,uid,quantity) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT(exchange_id,uid) "
                "DO UPDATE SET quantity=EXCLUDED.quantity",
                (exchange_id, character_id, uid, quantity),
            )
        return _changed(store, db, exchange_id)


def offer_items(store, account_id, generation, character_id, exchange_id, uids):
    """Atomically offer each selected owned stack at its current full quantity.

    Native12510 carries selected item identities only; quantity is not part of
    its wire payload. Validate the entire selection before changing any offer,
    then publish one revision for the batch.
    """
    if not isinstance(uids, (list, tuple)) or not uids or len(uids) > 128:
        raise ValueError("Invalid bulk exchange offer identities")
    if any(type(uid) is not int or not 0 < uid < 2**63 for uid in uids):
        raise ValueError("Invalid bulk exchange offer identities")
    if len(set(uids)) != len(uids):
        raise ValueError("Duplicate bulk exchange offer identity")
    from .inventory_items import load

    with store.connection() as db:
        exchange, wallets = _active(
            store, db, account_id, generation, character_id, exchange_id
        )
        units = {unit["uid"]: unit for unit in load(db, character_id)}
        if any(uid not in units for uid in uids):
            raise ValueError("Bulk offer contains unavailable or foreign units")

        existing = {
            row["uid"]: row["quantity"]
            for row in db.execute(
                "SELECT uid,quantity FROM player_exchange_items "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange_id, character_id),
            )
        }
        if len(set(existing) | set(uids)) > _policy(db)["maximum_offer_items"]:
            raise ValueError("Exchange item offer is full")

        # Do all policy and equipment validation before the first offer write.
        validated = []
        for uid in uids:
            unit = units[uid]
            quantity = unit.get("quantity")
            if type(quantity) is not int or not 1 <= quantity <= 32767:
                raise ValueError("Invalid owned stack quantity for bulk exchange")
            _offered_item(store, db, account_id, character_id, uid, quantity)
            validated.append((uid, quantity))

        changed = False
        for uid, quantity in validated:
            if existing.get(uid) == quantity:
                continue
            db.execute(
                "INSERT INTO player_exchange_items(exchange_id,character_id,uid,quantity) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT(exchange_id,uid) "
                "DO UPDATE SET quantity=EXCLUDED.quantity",
                (exchange_id, character_id, uid, quantity),
            )
            changed = True
        return dict(exchange) if not changed else _changed(store, db, exchange_id)


def confirm(store, account_id, generation, character_id, exchange_id):
    """Native13406 confirms the published current offer, without a wire revision.

    Repeated terminal requests return the existing receipt without transferring.
    The second current confirmation commits both inventories, both wallets,
    the unique receipt and durable delivery in this same SQL transaction.
    """
    with store.connection() as db:
        initial = db.execute(
            "SELECT * FROM player_exchanges WHERE id=%s", (exchange_id,)
        ).fetchone()
        if initial is None or (account_id, character_id, generation) not in _owners(
            initial
        ):
            raise ValueError("Unknown owned exchange")
        if initial["state"] == "committed":
            store.lock_character(db, account_id, generation, character_id)
            receipt = db.execute(
                "SELECT * FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange_id,),
            ).fetchone()
            if receipt is None:
                raise ValueError("Committed exchange has no receipt")
            return dict(initial, receipt=dict(receipt), applied=False)
        exchange, wallets = _active(
            store,
            db,
            account_id,
            generation,
            character_id,
            exchange_id,
            allow_committed=True,
        )
        if exchange["state"] == "committed":
            receipt = db.execute(
                "SELECT * FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange_id,),
            ).fetchone()
            if receipt is None:
                raise ValueError("Committed exchange has no receipt")
            return dict(exchange, receipt=dict(receipt), applied=False)
        member = db.execute(
            "SELECT * FROM player_exchange_members WHERE exchange_id=%s "
            "AND character_id=%s",
            (exchange_id, character_id),
        ).fetchone()
        if member["published_revision"] != exchange["revision"]:
            raise ValueError("Exchange confirmation precedes current offer publication")
        if member["confirmed_revision"] != exchange["revision"]:
            db.execute(
                "UPDATE player_exchange_members SET confirmed_revision=%s "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange["revision"], exchange_id, character_id),
            )
            exchange = dict(
                db.execute(
                    "UPDATE player_exchanges "
                    "SET delivery_sequence=delivery_sequence+1 "
                    "WHERE id=%s RETURNING *",
                    (exchange_id,),
                ).fetchone()
            )
            _outbox(store, db, exchange, "snapshot")
        members = list(
            db.execute(
                "SELECT * FROM player_exchange_members WHERE exchange_id=%s",
                (exchange_id,),
            )
        )
        if not all(
            row["confirmed_revision"] == exchange["revision"] for row in members
        ):
            return dict(exchange, applied=False)
        return _commit(store, db, exchange, wallets, members)


def withdraw_items(store, account_id, generation, character_id, exchange_id, uids):
    """Native13113 is one atomic withdrawal, including all offered identities."""
    if (
        not isinstance(uids, (list, tuple))
        or not uids
        or any(type(uid) is not int or not 0 < uid < 2**63 for uid in uids)
        or len(set(uids)) != len(uids)
    ):
        raise ValueError("Invalid exchange withdrawal identities")
    with store.connection() as db:
        exchange, wallets = _active(
            store, db, account_id, generation, character_id, exchange_id
        )
        owned = {
            row["uid"]
            for row in db.execute(
                "SELECT uid FROM player_exchange_items WHERE exchange_id=%s AND character_id=%s "
                "AND uid=ANY(%s)",
                (exchange_id, character_id, list(uids)),
            )
        }
        if owned != set(uids):
            raise ValueError("Withdrawal contains unavailable or foreign offered units")
        db.execute(
            "DELETE FROM player_exchange_items WHERE exchange_id=%s AND character_id=%s "
            "AND uid=ANY(%s)",
            (exchange_id, character_id, list(uids)),
        )
        return _changed(store, db, exchange_id)


def _commit(store, db, exchange, wallets, members):
    from .inventory_items import load
    from .inventory_uids import allocate
    from .exchange_rules import ITEMS
    from .exchange_transfer import plan, apply
    from wakfu_server.wire import proto_fields

    owners = _owners(exchange)
    identities = [entry[1] for entry in owners]
    offers = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM player_exchange_items " "WHERE exchange_id=%s ORDER BY uid",
            (exchange["id"],),
        )
    ]
    accounts = {character: account for account, character, generation in owners}
    offered_cash = {row["character_id"]: row["offered_kamas"] for row in members}
    balances = {}
    for account, character, generation in owners:
        other = next(identity for identity in identities if identity != character)
        if offered_cash[character] > wallets[account]:
            raise ValueError("Exchange account balance changed before commit")
        balances[account] = (
            wallets[account] - offered_cash[character] + offered_cash[other]
        )
        if not 0 <= balances[account] < 2**63:
            raise ValueError("Exchange recipient balance exceeds currency limit")
    containers = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM inventory_containers WHERE character_id=ANY(%s) ORDER BY uid FOR UPDATE",
            (identities,),
        )
    ]
    db.execute(
        "SELECT uid FROM inventory_items WHERE character_id=ANY(%s) ORDER BY uid FOR UPDATE",
        (identities,),
    ).fetchall()
    items = []
    excluded = set()
    for account, character, generation in owners:
        items.extend(load(db, character))
        saved = store.character(account, character, db)
        for build in saved["builds"].values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10:
                    excluded.add(dict(proto_fields(value)).get(8))
    bindings = {
        row["uid"]: row
        for row in db.execute(
            "SELECT * FROM inventory_item_bindings WHERE uid=ANY(%s)",
            ([row["uid"] for row in items],),
        )
    }
    for item in items:
        row = bindings.get(item["uid"])
        template = ITEMS.get(str(item["reference"]), {}).get("binding_template", {})
        item["bound"] = row["bound"] if row else template.get("default_eKo")
    from .item_custody_metadata import snapshot_many

    metadata = snapshot_many(db, [item["uid"] for item in items])
    for item in items:
        item["_custody_metadata"] = metadata[item["uid"]]
    for offer in offers:
        _offered_item(
            store,
            db,
            accounts[offer["character_id"]],
            offer["character_id"],
            offer["uid"],
            offer["quantity"],
        )
    final, movements = plan(
        items, containers, offers, allocate=lambda: allocate(db), excluded_uids=excluded
    )
    apply(db, items, final)
    for account, balance in sorted(balances.items()):
        db.execute(
            "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
            (balance, account),
        )
    transfers = {
        "items": movements,
        "balances": {str(key): value for key, value in balances.items()},
        "previous_uids": {
            str(identity): [
                row["uid"] for row in items if row["character_id"] == identity
            ]
            for identity in identities
        },
        "offered_uids": [offer["uid"] for offer in offers],
        "offered_kamas": {str(key): value for key, value in offered_cash.items()},
    }
    receipt = dict(
        db.execute(
            "INSERT INTO player_exchange_receipts(exchange_id,revision,committed_at,transfers) "
            "VALUES(%s,%s,%s,%s) RETURNING *",
            (exchange["id"], exchange["revision"], store.now(), Jsonb(transfers)),
        ).fetchone()
    )
    exchange = dict(
        db.execute(
            "UPDATE player_exchanges SET state='committed',"
            "delivery_sequence=delivery_sequence+1 WHERE id=%s RETURNING *",
            (exchange["id"],),
        ).fetchone()
    )
    _outbox(store, db, exchange, "committed")
    db.execute(
        "DELETE FROM player_exchange_members WHERE exchange_id=%s", (exchange["id"],)
    )
    return dict(exchange, receipt=receipt, applied=True)
