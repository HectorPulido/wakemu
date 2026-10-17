"""Selection retries require the same current owned character lease."""
import unittest
from wakfu_server.character_selection_retry import already_selected_owned_character


class ReadOnlyLeaseStore:
    def __init__(self):
        self.actual_lease = (13, "current-generation", 31)
        self.calls = []

    def current_character_session(self, account, generation, character):
        self.calls.append((account, generation, character))
        return (account, generation, character) == self.actual_lease

    def select_character(self, *args):
        raise AssertionError("Retry must not replay selection or earned rewards")


class CharacterSelectionRetryTests(unittest.TestCase):
    def setUp(self):
        self.store = ReadOnlyLeaseStore()
        self.actor = {"id": 31, "account_id": 13, "name": "Resilience Ally uzn"}
        self.request = {"character_id": 31, "character_name": "Resilience Ally uzn"}

    def test_same_owned_selection_requires_current_selected_generation(self):
        self.assertTrue(
            already_selected_owned_character(
                self.store, 13, "current-generation", self.actor, self.request
            )
        )
        self.assertEqual(self.store.calls, [(13, "current-generation", 31)])
        self.assertEqual(
            self.actor, {"id": 31, "account_id": 13, "name": "Resilience Ally uzn"}
        )

    def test_replaced_expired_or_cleared_selected_lease_does_not_accept_retry(self):
        for lease in ((13, "replacement", 31), (13, "current-generation", None), None):
            with self.subTest(lease=lease):
                self.store.actual_lease = lease
                self.assertFalse(
                    already_selected_owned_character(
                        self.store, 13, "current-generation", self.actor, self.request
                    )
                )

    def test_other_character_wrong_name_and_foreign_owner_cannot_bypass_selection(self):
        cases = [
            ({**self.actor, "account_id": 14}, self.request),
            (self.actor, {**self.request, "character_id": 32}),
            (self.actor, {**self.request, "character_name": "other"}),
            (self.actor, {**self.request, "character_id": True}),
        ]
        for actor, request in cases:
            with self.subTest(actor=actor, request=request):
                self.assertFalse(
                    already_selected_owned_character(
                        self.store, 13, "current-generation", actor, request
                    )
                )
        self.assertEqual(self.store.calls, [])

    def test_unauthenticated_or_missing_local_actor_does_not_query_lease(self):
        for account, generation, actor in (
            (None, "current-generation", self.actor),
            (13, None, self.actor),
            (13, "", self.actor),
            (13, "current-generation", None),
        ):
            with self.subTest(account=account, generation=generation, actor=actor):
                self.assertFalse(
                    already_selected_owned_character(
                        self.store, account, generation, actor, self.request
                    )
                )
        self.assertEqual(self.store.calls, [])
