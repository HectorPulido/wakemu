"""Generation-scoped delivery adapter for durable player exchanges.

Domain mutations remain in :mod:`player_exchanges`; this module only validates
live peers, serializes each exchange, and publishes the SQL outbox on captured
connections.  A partial socket write is never acknowledged.
"""
import threading
from contextlib import contextmanager

from wakfu_server import (
    exchange_inventory,
    exchange_snapshot,
    exchange_wire,
    player_exchanges,
)


class Exchanges:
    def __init__(self, store, world):
        self.store = store
        self.world = world
        self.locks = [threading.RLock() for _ in range(1024)]
        self._memory_lock = threading.RLock()
        # Native content packets are additive. Retain the last fully-published
        # payload only for the exact exchange participant connection generation.
        self._last_payload = {}
        self._started = set()
        # If socket writes completed but the SQL ack transiently failed, retry
        # the ack without replaying additive packets on this same live socket.
        self._sent_unacked = {}
        # A failed send can have partially written before World closes the
        # peer. Never replay additive native packets on that captured lease.
        self._failed_leases = set()

    @contextmanager
    def _guard(self, exchange_id):
        lock = self.locks[hash(exchange_id) % len(self.locks)]
        with lock:
            yield

    def _authorize(self, account_id, generation, character_id):
        live = self.world.live_identity(character_id=character_id)
        if (
            live is None
            or live[0] != generation
            or live[1].get("account_id") != account_id
            or not self.store.current_character_session(
                account_id, generation, character_id
            )
        ):
            raise ValueError("La sesión del intercambio ya no está activa.")
        return live[1]

    def _peer(self, exchange, character_id):
        if character_id == exchange["inviter_id"]:
            return (
                exchange["invitee_id"],
                exchange["invitee_account"],
                exchange["invitee_generation"],
            )
        if character_id == exchange["invitee_id"]:
            return (
                exchange["inviter_id"],
                exchange["inviter_account"],
                exchange["inviter_generation"],
            )
        raise ValueError("El personaje no participa en este intercambio.")

    def _same_location(self, left, right):
        return (left.get("map_id"), left.get("instance_id")) == (
            right.get("map_id"),
            right.get("instance_id"),
        )

    def _authorize_pair(self, exchange, actor_id):
        actor = self._authorize(
            exchange["inviter_account"]
            if actor_id == exchange["inviter_id"]
            else exchange["invitee_account"],
            exchange["inviter_generation"]
            if actor_id == exchange["inviter_id"]
            else exchange["invitee_generation"],
            actor_id,
        )
        peer_id, peer_account, peer_generation = self._peer(exchange, actor_id)
        peer = self.world.live_identity(character_id=peer_id)
        if (
            peer is None
            or peer[0] != peer_generation
            or peer[1].get("account_id") != peer_account
            or not self.store.current_character_session(
                peer_account, peer_generation, peer_id
            )
        ):
            raise ValueError("El otro participante ya no está conectado.")
        if not self._same_location(actor, peer[1]):
            raise ValueError(
                "Ambos participantes deben estar en el mismo mapa e instancia."
            )
        return actor, peer[1]

    def handle(self, opcode, body, account_id, generation, character_id):
        """Validate and apply one native exchange request, then drain its outbox."""
        sender = self._authorize(account_id, generation, character_id)
        request = exchange_wire.request(opcode, body)
        if opcode == 13140:
            target_id = request["target_id"]
            target = self.world.live_identity(character_id=target_id)
            if (
                target is None
                or target[1].get("account_id") == account_id
                or not self.store.current_character_session(
                    target[1].get("account_id"), target[0], target_id
                )
            ):
                raise ValueError("El objetivo del intercambio no está conectado.")
            if not self._same_location(sender, target[1]):
                raise ValueError(
                    "Ambos participantes deben estar en el mismo mapa e instancia."
                )
            exchange = player_exchanges.invite(
                self.store, account_id, generation, character_id, target_id
            )
            with self._guard(exchange["id"]):
                self._drain_exchange(exchange["id"])
            return exchange

        exchange_id = request["exchange_id"]
        with self._guard(exchange_id):
            with self.store.connection() as db:
                row = db.execute(
                    "SELECT * FROM player_exchanges WHERE id=%s", (exchange_id,)
                ).fetchone()
            if row is None:
                raise ValueError("Intercambio desconocido.")
            exchange = dict(row)
            if (account_id, character_id, generation) not in (
                (
                    exchange["inviter_account"],
                    exchange["inviter_id"],
                    exchange["inviter_generation"],
                ),
                (
                    exchange["invitee_account"],
                    exchange["invitee_id"],
                    exchange["invitee_generation"],
                ),
            ):
                raise ValueError("El personaje no posee este intercambio.")
            # Invitation decisions and inviter cancellation use distinct native
            # branches on the same 12997 carrier; result1 is decline for the
            # invitee but cancel for the inviter. Active exchange operations
            # require both exact leases and shared location.
            if opcode == 12997:
                action = exchange_wire.invitation_action(
                    body, actor_is_inviter=character_id == exchange["inviter_id"]
                )["action"]
                if action == "cancel":
                    if character_id != exchange["inviter_id"]:
                        raise ValueError(
                            "Solo quien inició el intercambio puede cancelar la invitación."
                        )
                    if exchange["state"] != "invitation":
                        raise ValueError("La invitación ya fue respondida o cerrada.")
                    exchange = player_exchanges.cancel(
                        self.store,
                        account_id,
                        generation,
                        character_id,
                        exchange_id,
                        expected_state="invitation",
                    )
                else:
                    if character_id != exchange["invitee_id"]:
                        raise ValueError(
                            "Solo el destinatario puede responder la invitación."
                        )
                    self._authorize_pair(exchange, character_id)
                    exchange = player_exchanges.answer(
                        self.store,
                        account_id,
                        generation,
                        character_id,
                        exchange_id,
                        action == "accept",
                    )
            elif opcode == 12027:
                # A participant may cancel after the peer disconnected; the
                # domain operation locks and validates only the caller's lease.
                exchange = player_exchanges.cancel(
                    self.store, account_id, generation, character_id, exchange_id
                )
            else:
                self._authorize_pair(exchange, character_id)
                if opcode == 12781:
                    exchange = player_exchanges.offer_kamas(
                        self.store,
                        account_id,
                        generation,
                        character_id,
                        exchange_id,
                        request["kamas"],
                    )
                elif opcode == 13037:
                    exchange = player_exchanges.offer_item(
                        self.store,
                        account_id,
                        generation,
                        character_id,
                        exchange_id,
                        request["uid"],
                        request["quantity"],
                        operation="add",
                    )
                elif opcode == 12203:
                    exchange = player_exchanges.offer_item(
                        self.store,
                        account_id,
                        generation,
                        character_id,
                        exchange_id,
                        request["uid"],
                        request["quantity"],
                        operation="remove",
                    )
                elif opcode == 13113:
                    exchange = player_exchanges.withdraw_items(
                        self.store,
                        account_id,
                        generation,
                        character_id,
                        exchange_id,
                        request["uids"],
                    )
                elif opcode == 12510:
                    exchange = player_exchanges.offer_items(
                        self.store,
                        account_id,
                        generation,
                        character_id,
                        exchange_id,
                        request["uids"],
                    )
                elif opcode == 13406:
                    exchange = player_exchanges.confirm(
                        self.store, account_id, generation, character_id, exchange_id
                    )
                else:
                    raise ValueError("Unsupported exchange request opcode")
            self._drain_exchange(exchange_id)
            return exchange

    def _pending(self, exchange_id=None, limit=128):
        with self.store.connection() as db:
            if exchange_id is None:
                rows = db.execute(
                    "SELECT * FROM player_exchange_outbox WHERE delivered_at IS NULL "
                    "ORDER BY exchange_id,delivery_sequence,id LIMIT %s",
                    (limit,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM player_exchange_outbox WHERE delivered_at IS NULL "
                    "AND exchange_id=%s ORDER BY delivery_sequence,id LIMIT %s",
                    (exchange_id, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def drain(self, limit=128):
        """Publish up to ``limit`` pending rows in per-exchange sequence order."""
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError("Invalid exchange outbox drain limit")
        self._prune_memory()
        with self._memory_lock:
            uncertain_exchanges = sorted(
                {identity[0] for identity in self._sent_unacked.values()}
            )
        for exchange_id in uncertain_exchanges[:limit]:
            with self._guard(exchange_id):
                self._recover_acknowledged(exchange_id)
        count = 0
        seen = set()
        for row in self._pending(limit=limit):
            exchange_id = row["exchange_id"]
            if exchange_id in seen:
                continue
            seen.add(exchange_id)
            with self._guard(exchange_id):
                count += self._drain_exchange(exchange_id, limit=max(1, limit - count))
            if count >= limit:
                break
        return count

    def _prune_memory(self):
        with self._memory_lock:
            keys = (
                set(self._last_payload)
                | self._started
                | self._failed_leases
                | set(self._sent_unacked.values())
            )
        for key in keys:
            exchange_id, character_id, generation = key
            live = self.world.live_identity(character_id=character_id)
            if live is not None and live[0] == generation:
                continue
            with self.store.connection() as db:
                exact = db.execute(
                    "SELECT 1 FROM sessions WHERE character_id=%s AND generation=%s AND expires_at>%s",
                    (character_id, generation, self.store.now()),
                ).fetchone()
            if exact is None:
                self._retire_key(key)

    def _retire_key(self, key):
        with self._memory_lock:
            self._last_payload.pop(key, None)
            self._started.discard(key)
            self._failed_leases.discard(key)
            for outbox_key, identity_key in list(self._sent_unacked.items()):
                if identity_key == key:
                    self._sent_unacked.pop(outbox_key, None)

    def _recover_acknowledged(self, exchange_id):
        # A successful SQL commit can lose its response. That row is no longer
        # pending, but its additive socket packets have already been sent.
        # Recover the local publication baseline before any later snapshot.
        with self._memory_lock:
            uncertain = [
                key[0]
                for key, identity in self._sent_unacked.items()
                if identity[0] == exchange_id
            ]
        if uncertain:
            with self.store.connection() as db:
                acknowledged = db.execute(
                    "SELECT * FROM player_exchange_outbox WHERE id=ANY(%s) "
                    "AND delivered_at IS NOT NULL ORDER BY delivery_sequence,id",
                    (uncertain,),
                ).fetchall()
            for row in acknowledged:
                self._complete(dict(row))

    def _drain_exchange(self, exchange_id, limit=128):
        self._recover_acknowledged(exchange_id)
        sent = 0
        for row in self._pending(exchange_id, limit):
            result = self._deliver(row)
            if result == "deferred":
                break
            sent += 1
        return sent

    def _is_stale(self, row):
        live = self.world.live_identity(character_id=row["character_id"])
        if live is not None and live[0] == row["generation"]:
            return False
        # A temporarily unpublished world entry is not proof of staleness.
        with self.store.connection() as db:
            exact = db.execute(
                "SELECT 1 FROM sessions WHERE character_id=%s AND generation=%s AND expires_at>%s",
                (row["character_id"], row["generation"], self.store.now()),
            ).fetchone()
        return exact is None

    def _mark_stale(self, row):
        with self.store.connection() as db:
            db.execute(
                "UPDATE player_exchange_outbox SET delivered_at=%s "
                "WHERE id=%s AND delivered_at IS NULL",
                (self.store.now(), row["id"]),
            )
        key = (row["exchange_id"], row["character_id"], row["generation"])
        with self._memory_lock:
            self._last_payload.pop(key, None)
            self._started.discard(key)
            self._sent_unacked.pop((row["id"], row["generation"]), None)
            self._failed_leases.discard(key)

    def _deliver(self, row):
        if self._is_stale(row):
            self._mark_stale(row)
            return "stale"
        identity_key = (row["exchange_id"], row["character_id"], row["generation"])
        ack_key = (row["id"], row["generation"])
        with self._memory_lock:
            sent_unacked = ack_key in self._sent_unacked
            failed_lease = identity_key in self._failed_leases
            previous = self._last_payload.get(identity_key)
            started = identity_key in self._started
        if sent_unacked:
            if not self._ack(row):
                return "deferred"
            self._complete(row)
            return "delivered"
        if failed_lease:
            return "deferred"
        payload = row["payload"]
        event = row["event"]
        if event == "snapshot" and payload.get("state") == "invitation":
            if row["character_id"] == payload["inviter_id"]:
                packets = [
                    exchange_wire.status(
                        row["exchange_id"],
                        0,
                        payload["invitee_id"],
                        payload["inviter_id"],
                    )
                ]
            else:
                packets = [
                    exchange_wire.proposed(row["exchange_id"], payload["inviter_id"])
                ]
        elif event == "snapshot" and payload.get("state") == "active":
            packets = []
            if not started:
                accepted_by = payload.get("accepted_by", payload["invitee_id"])
                other = (
                    payload["invitee_id"]
                    if row["character_id"] == payload["inviter_id"]
                    else payload["inviter_id"]
                )
                packets.append(
                    exchange_wire.status(row["exchange_id"], 3, accepted_by, other)
                )
            packets.extend(
                exchange_snapshot.packets(
                    row["exchange_id"], row["revision"], payload, previous=previous
                )
            )
        elif event == "canceled":
            canceled_by = payload.get("canceled_by")
            close_result = (
                3
                if canceled_by is None
                else (1 if canceled_by == row["character_id"] else 2)
            )
            if payload.get("previous_state") == "invitation":
                other = (
                    payload["invitee_id"]
                    if row["character_id"] == payload["inviter_id"]
                    else payload["inviter_id"]
                )
                packets = [
                    exchange_wire.status(
                        row["exchange_id"], 2, other, row["character_id"]
                    )
                ]
            else:
                packets = [exchange_wire.closed(row["exchange_id"], close_result)]
                packets.extend(self._refresh_packets(row, payload))
        elif event == "committed":
            packets = [exchange_wire.closed(row["exchange_id"], 0)]
            packets.extend(self._receipt_packets(row))
        else:
            raise ValueError("Invalid exchange outbox event")

        for opcode, body in packets:
            if not self.world.send_to(
                row["character_id"], row["generation"], opcode, body
            ):
                with self._memory_lock:
                    self._failed_leases.add(identity_key)
                return "deferred"
        with self._memory_lock:
            self._sent_unacked[ack_key] = identity_key
        if not self._ack(row):
            return "deferred"
        self._complete(row)
        return "delivered"

    def _complete(self, row):
        identity_key = (row["exchange_id"], row["character_id"], row["generation"])
        ack_key = (row["id"], row["generation"])
        with self._memory_lock:
            self._sent_unacked.pop(ack_key, None)
            payload = row["payload"]
            if row["event"] == "snapshot" and payload.get("state") == "active":
                self._last_payload[identity_key] = payload
                self._started.add(identity_key)
            elif row["event"] in ("canceled", "committed"):
                self._last_payload.pop(identity_key, None)
                self._started.discard(identity_key)

    def _refresh_packets(self, row, payload):
        # Load current authoritative ownership; candidates include every owned
        # unit plus any unit named by the exchange snapshot (optimistic local UI).
        with self.store.connection() as db:
            owner = db.execute(
                "SELECT account_id FROM characters WHERE id=%s", (row["character_id"],)
            ).fetchone()
            if owner is None:
                raise ValueError("Exchange participant character disappeared")
            character = self.store.character(
                owner["account_id"], row["character_id"], db
            )
        offered_uids = [item["uid"] for item in payload.get("items", [])]
        with self._memory_lock:
            previous = self._last_payload.get(
                (row["exchange_id"], row["character_id"], row["generation"])
            )
        if previous is not None:
            offered_uids.extend(item["uid"] for item in previous.get("items", []))
        transfers = {
            "previous_uids": {
                str(row["character_id"]): [
                    item["uid"] for item in character["inventory_items"]
                ]
            },
            "offered_uids": offered_uids,
        }
        return exchange_inventory.packets(character, transfers)

    def _receipt_packets(self, row):
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT transfers FROM player_exchange_receipts WHERE exchange_id=%s",
                (row["exchange_id"],),
            ).fetchone()
            owner = db.execute(
                "SELECT account_id FROM characters WHERE id=%s", (row["character_id"],)
            ).fetchone()
            if receipt is None or owner is None:
                raise ValueError("Committed exchange receipt is unavailable")
            character = self.store.character(
                owner["account_id"], row["character_id"], db
            )
            balance_row = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s",
                (owner["account_id"],),
            ).fetchone()
        packets = exchange_inventory.packets(character, receipt["transfers"])
        from wakfu_server import wire

        packets.append((12753, wire.account_kamas_update(balance_row["kamas"])))
        packets.append((13873, wire.account_kamas(balance_row["kamas"])))
        return packets

    def _ack(self, row):
        with self.store.connection() as db:
            updated = db.execute(
                "UPDATE player_exchange_outbox SET delivered_at=%s WHERE id=%s AND delivered_at IS NULL",
                (self.store.now(), row["id"]),
            )
            if updated.rowcount != 1:
                return False
            if row["event"] == "snapshot" and row["payload"].get("state") == "active":
                db.execute(
                    "UPDATE player_exchange_members SET published_revision=%s "
                    "WHERE exchange_id=%s AND character_id=%s AND EXISTS ("
                    "SELECT 1 FROM player_exchanges e WHERE e.id=%s AND e.state='active' "
                    "AND e.revision=%s)",
                    (
                        row["revision"],
                        row["exchange_id"],
                        row["character_id"],
                        row["exchange_id"],
                        row["revision"],
                    ),
                )
        return True
