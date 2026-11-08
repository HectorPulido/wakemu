"""Bounded, session-fenced feedback for rejected full-inventory purchases."""
import logging

from wakfu_server import wire

LOG = logging.getLogger(__name__)


class InventoryFull(ValueError):
    def __init__(self, account_id, character_id, generation):
        super().__init__("Inventory full; free one slot before purchasing")
        self.account_id = account_id
        self.character_id = character_id
        self.generation = generation


def record(store, error, request_key):
    """Commit feedback after the rejected purchase transaction has rolled back."""
    try:
        with store.connection() as db:
            db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (error.account_id,)
            )
            if db.execute(
                "SELECT 1 FROM shop_orders WHERE account_id=%s AND request_key=%s",
                (error.account_id, request_key),
            ).fetchone():
                return
            db.execute(
                "INSERT INTO shop_purchase_feedback "
                "(account_id,character_id,generation,request_key,expires_at) "
                "VALUES(%s,%s,%s,%s,now()+interval '2 minutes') "
                "ON CONFLICT(account_id) DO UPDATE SET "
                "character_id=EXCLUDED.character_id,generation=EXCLUDED.generation,"
                "request_key=EXCLUDED.request_key,revision=shop_purchase_feedback.revision+1,"
                "expires_at=EXCLUDED.expires_at,delivered_at=NULL "
                "WHERE (shop_purchase_feedback.generation,shop_purchase_feedback.request_key) "
                "IS DISTINCT FROM (EXCLUDED.generation,EXCLUDED.request_key)",
                (error.account_id, error.character_id, error.generation, request_key),
            )
    except Exception:
        # Notification failure must preserve the original rejection and its rollback.
        LOG.exception("Could not queue shop inventory feedback")


def pending(db, account_id, character, generation):
    if generation is None:
        return None
    row = db.execute(
        "SELECT revision FROM shop_purchase_feedback "
        "WHERE account_id=%s AND character_id=%s AND generation=%s "
        "AND delivered_at IS NULL AND expires_at>now()",
        (account_id, character["id"], generation),
    ).fetchone()
    if row is None:
        return None
    message = (
        f"Tienda: el inventario de {character['name']} no tiene un espacio compatible libre. "
        "Libera un espacio y vuelve a intentarlo. No se cobraron kamas."
    )
    return row["revision"], (674, wire.chat(dict(character, name="Tienda"), message))


def acknowledge(db, account_id, character_id, generation, revision):
    if revision is not None:
        db.execute(
            "UPDATE shop_purchase_feedback SET delivered_at=now() "
            "WHERE account_id=%s AND character_id=%s AND generation=%s AND revision=%s",
            (account_id, character_id, generation, revision),
        )
