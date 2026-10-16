"""PostgreSQL commit hints wake World's owning socket dispatcher.

Notifications are acceleration only: durable projections and periodic polling
recover disconnects, missed notifications and process restarts. The listener
never changes characters, sends game frames or grants inventory from its thread.
"""
import json
import socket
import threading
import logging
import weakref

_LOG = logging.getLogger(__name__)
_LOCK = threading.Lock()
_LISTENERS = weakref.WeakKeyDictionary()


class Subscription:
    def __init__(self, listener):
        self.listener = listener
        self.character_id = None
        self.reader, self.writer = socket.socketpair()
        self.reader.setblocking(False)
        self.writer.setblocking(False)
        self.dirty = threading.Event()

    def wake(self):
        self.dirty.set()
        try:
            self.writer.send(b"1")
        except (BlockingIOError, OSError):
            pass

    def drain(self):
        try:
            while self.reader.recv(4096):
                pass
        except (BlockingIOError, OSError):
            pass

    def close(self):
        with self.listener.lock:
            self.listener.subscriptions.discard(self)
        self.reader.close()
        self.writer.close()


class Listener:
    def __init__(self, store, stopping):
        self.store = weakref.ref(store)
        self.stopping = stopping
        self.lock = threading.Lock()
        self.subscriptions = set()
        self.thread = threading.Thread(
            target=self.run, name="objectives-updates", daemon=True
        )
        self.thread.start()

    def subscribe(self):
        subscription = Subscription(self)
        with self.lock:
            self.subscriptions.add(subscription)
        return subscription

    def notify(self, payload):
        try:
            value = None if payload == "all" else json.loads(payload)
            identity = value.get("character_id") if isinstance(value, dict) else value
            if identity is not None and (type(identity) is not int or identity < 0):
                return
        except (ValueError, TypeError):
            return
        with self.lock:
            for subscription in self.subscriptions:
                if identity in (None, 0, subscription.character_id):
                    subscription.wake()

    def run(self):
        from psycopg import connect, Error

        while not self.stopping.is_set():
            try:
                store = self.store()
                if store is None:
                    return
                database = store.database
                del store
                with connect(
                    database.conninfo,
                    **database.connection_kwargs,
                    autocommit=True,
                    connect_timeout=5
                ) as db:
                    db.execute("LISTEN wakemu_objectives_updates")
                    while not self.stopping.is_set() and self.store() is not None:
                        for notification in db.notifies(timeout=1.0):
                            self.notify(notification.payload)
            except (Error, OSError):
                _LOG.exception(
                    "Objectives update listener reconnecting; durable polling remains active"
                )
                self.stopping.wait(1.0)


def subscribe(store, stopping):
    with _LOCK:
        listener = _LISTENERS.get(store)
        if listener is None:
            listener = Listener(store, stopping)
            _LISTENERS[store] = listener
    return listener.subscribe()
