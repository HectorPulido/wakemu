"""Exercise the production Session selection method against isolated SQL state."""

from types import SimpleNamespace

from postgres_case import PostgresCase
from wakfu_server import builds
from wakfu_server.application.dispatch_result import DispatchResult
from wakfu_server.application.session import Session


class ApplicationSelectionPostgresTests(PostgresCase):
    def test_selection_commits_owned_lease_and_retry_does_not_republish(self):
        account_id = self.store.register(
            "application-selection", "isolated-test-password"
        )["id"]
        actor = self.store.create_character(account_id, "Application Selection")
        generation = self.store.begin_session(account_id)
        sent = []
        events = []
        attached = []
        replayed = []

        runtime = SimpleNamespace(
            STORE=self.store,
            decode_body=lambda _direction, _opcode, _body: {
                "character_id": actor["id"],
                "character_name": actor["name"],
            },
            record=lambda **event: events.append(event),
            send=lambda _connection, _service, opcode, body: sent.append(
                (opcode, body)
            ),
            COMBAT_SESSIONS=SimpleNamespace(
                session=lambda *args: args,
                live_reconnect_available=lambda _session: False,
                reconcile_disconnected_pve=lambda *_args, **_kwargs: None,
                recover_withdrawn_pve=lambda _session: None,
                lookup_character=lambda _identity: None,
            ),
            COMBAT_GROUPS=object(),
            reconcile_closed_rift_login=lambda *_args, **_kwargs: None,
            # Health initialization is outside this regression's SQL contract
            # and requires the published combat catalog. Re-read the owned row
            # at that boundary so the downstream selection uses durable state.
            health_store=SimpleNamespace(
                initialize=lambda store, owner, lease, identity, **_kwargs: store.character(
                    owner, identity
                )
            ),
            POSITIONS=SimpleNamespace(attach=lambda *args: attached.append(args)),
            Movement=lambda position: dict(position),
            replay=lambda *args, **kwargs: replayed.append((args, kwargs)),
            builds=builds,
            rich_inventory_packet=lambda _character: (65001, b"inventory-fixture"),
        )
        session = object.__new__(Session)
        session.runtime = runtime
        session.state = SimpleNamespace(
            opcode=23664,
            body=b"selection-fixture",
            account_id=account_id,
            generation=generation,
            character=None,
            selected=False,
            training_transit_active=False,
            connection=object(),
            service="world",
            position={"x": -12, "y": -8, "z": -1},
        )
        # Reward delivery is a publication boundary; the Store selection,
        # company alignment, health ownership and UID reservation remain real.
        session.deliver_custom_task_rewards = lambda **_kwargs: None

        result = session.handle_character_select()

        self.assertIs(result, DispatchResult.FALLTHROUGH)
        self.assertTrue(session.state.selected)
        self.assertEqual(session.state.character["id"], actor["id"])
        self.assertTrue(
            self.store.current_character_session(account_id, generation, actor["id"])
        )
        self.assertEqual(len(attached), 1)
        self.assertEqual(len(replayed), 1)
        self.assertIn((13778, session.state.message_body), sent)
        with self.store.connection() as db:
            reserved = db.execute(
                "SELECT count(*) AS count FROM inventory_reserved_uids "
                "WHERE account_id=%s AND generation=%s AND character_id=%s "
                "AND used_request IS NULL",
                (account_id, generation, actor["id"]),
            ).fetchone()["count"]
        self.assertEqual(reserved, 32)

        sent_before_retry = list(sent)
        result = session.handle_character_select()

        self.assertIs(result, DispatchResult.CONTINUE)
        self.assertEqual(sent, sent_before_retry)
        self.assertEqual(len(attached), 1)
        self.assertEqual(len(replayed), 1)
        self.assertEqual(
            [event["event"] for event in events],
            ["character_selected", "character_selection_retry_ignored"],
        )
        with self.store.connection() as db:
            reserved_after_retry = db.execute(
                "SELECT count(*) AS count FROM inventory_reserved_uids "
                "WHERE account_id=%s AND generation=%s AND character_id=%s "
                "AND used_request IS NULL",
                (account_id, generation, actor["id"]),
            ).fetchone()["count"]
        self.assertEqual(reserved_after_retry, reserved)
