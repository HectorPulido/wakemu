"""Deliver explicit earned custom rewards in a separate post-game transaction.

Never call from a gameplay transaction holding a character lock. The entry point
owns account -> selected session -> live character -> entitlement lock order.
No task defaults, gift claims, native achievement identities or UI hooks exist
here. Callers publish returned packets only after commit, followed by current
absolute progression/inventory/account unlock state; reconnect recovers that
state without replaying grants.
"""
from wakfu_server.achievements import rewards
from . import completion_rewards


def deliver(store, account_id, generation, character_id):
    """Grant pending earned rows once for the authenticated selected character.

    Capacity leaves a row pending. Other validation failures abort this complete
    delivery transaction. The returned character is reloaded after all grants;
    fixed XP deltas must precede its final absolute progression publication.
    """
    for value in (account_id, character_id):
        if type(value) is not int or not 0 < value < 2**63:
            raise ValueError("Invalid custom reward owner")
    with store.connection() as db:
        if (
            db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
            ).fetchone()
            is None
        ):
            raise ValueError("Missing custom reward account")
        store.lock_character(db, account_id, generation, character_id)
        if (
            db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f "
                "ON f.id=p.fight_id WHERE p.account_id=%s AND p.character_id=%s "
                "AND f.status IN ('placement','active') LIMIT 1",
                (account_id, character_id),
            ).fetchone()
            is not None
        ):
            raise ValueError("Custom rewards require post-game delivery")
        completion_rewards.materialize(db, character_id)
        pending = db.execute(
            "SELECT r.* FROM character_custom_task_reward_outbox r "
            "JOIN character_custom_task_progress p USING(character_id,task_key) "
            "WHERE r.character_id=%s AND r.delivered_at IS NULL "
            "AND p.completed_at IS NOT NULL "
            "ORDER BY r.task_key,r.reward_index FOR UPDATE OF r",
            (character_id,),
        ).fetchall()
        packets, delivered, blocked = [], [], []
        for row in pending:
            reward = row["payload"]
            if type(reward) is not dict:
                raise ValueError("Invalid custom reward entitlement payload")
            cash = set(reward) == {"kind", "amount"} and reward["kind"] == "kamas"
            if cash:
                if (
                    type(reward["amount"]) is not int
                    or not 0 < reward["amount"] < 2**63
                ):
                    raise ValueError("Invalid custom reward kamas entitlement")
            elif set(reward) != {"aeV", "ckl"}:
                raise ValueError("Invalid custom reward entitlement payload")
            else:
                rewards.validate(reward)
            identity = (row["task_key"], row["reward_index"])
            try:
                with db.transaction():
                    character = store.character(account_id, character_id, db)
                    if cash:
                        wallet = db.execute(
                            "UPDATE account_wallets SET kamas=kamas+%s "
                            "WHERE account_id=%s AND kamas<=%s RETURNING kamas",
                            (
                                reward["amount"],
                                account_id,
                                (2**63 - 1) - reward["amount"],
                            ),
                        ).fetchone()
                        if wallet is None:
                            raise ValueError(
                                "Custom reward wallet missing or overflowing"
                            )
                        from wakfu_server.wire import account_kamas_update

                        granted = [(12753, account_kamas_update(wallet["kamas"]))]
                    else:
                        granted = rewards.grant(db, store, character, reward)
                    changed = db.execute(
                        "UPDATE character_custom_task_reward_outbox "
                        "SET delivered_at=CURRENT_TIMESTAMP WHERE character_id=%s "
                        "AND task_key=%s AND reward_index=%s AND delivered_at IS NULL "
                        "RETURNING reward_index",
                        (character_id, *identity),
                    ).fetchone()
                    if changed is None:
                        raise ValueError("Custom reward receipt changed while locked")
            except rewards.RewardCapacity:
                blocked.append(identity)
                continue
            delivered.append(identity)
            packets.extend(granted)
        character = store.character(account_id, character_id, db)
    return {
        "packets": packets,
        "delivered": delivered,
        "capacity_pending": blocked,
        "character": character,
    }
