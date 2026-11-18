"""The presentation ledger backfills old events and ignores suppressed scenes."""

from wakfu_server.achievements import storage, tutorial_presentation_once as once
from postgres_case import PostgresCase


class TutorialPresentationOncePostgresTests(PostgresCase):
    def test_suppressed_legacy_receipt_does_not_consume_later_scene_and_claim_is_unique(
        self,
    ):
        account = self.store.register("presentation-once-test", "local-password")["id"]
        character = self.store.create_character(account, "Presentation Once")
        legacy = dict(
            schema="owned-story-controller-v1",
            owner=character["id"],
            step="boss-intro",
            presentation_suppressed=True,
        )
        witness = dict(
            prefix="owned-story:temple:",
            payload=dict(
                schema="owned-story-controller-v1",
                owner=character["id"],
                step="boss-intro",
            ),
            exclude_payload={"presentation_suppressed": True},
        )
        with self.store.connection() as db:
            self.assertTrue(
                storage.record_event(
                    db,
                    character["id"],
                    "owned-story:temple:instance-1:boss-intro",
                    legacy,
                )
            )
            self.assertTrue(
                storage.record_event(
                    db,
                    character["id"],
                    "astrub-cat-story:old:scene:23928",
                    dict(
                        kind="owned_cat_story_scene",
                        owner=character["id"],
                        event_id=23928,
                    ),
                )
            )
            self.assertTrue(
                storage.record_event(
                    db,
                    character["id"],
                    "astrub-cat-story:old:callback:23920",
                    dict(
                        kind="owned_cat_story_callback",
                        owner=character["id"],
                        event_id=23920,
                    ),
                )
            )
            self.assertTrue(
                once.claim(db, character["id"], 1722, 14265, legacy=(witness,))
            )
            self.assertFalse(
                once.claim(db, character["id"], 1722, 14265, legacy=(witness,))
            )
            self.assertTrue(once.claim(db, character["id"], 1722, 14288))
            old_scene = dict(
                prefix="astrub-cat-story:",
                payload=dict(
                    kind="owned_cat_story_scene",
                    owner=character["id"],
                    event_id=23928,
                ),
            )
            self.assertFalse(
                once.claim(db, character["id"], 1340, 23928, legacy=(old_scene,))
            )
            old_guide = dict(
                prefix="astrub-cat-story:",
                payload=dict(
                    kind="owned_cat_story_callback",
                    owner=character["id"],
                    event_id=23920,
                ),
            )
            self.assertFalse(
                once.claim_guide(db, character["id"], 170, legacy=(old_guide,))
            )
            with self.assertRaises(ValueError):
                once.claim(
                    db,
                    character["id"],
                    1722,
                    14290,
                    legacy=({"prefix": "", "payload": {"kind": "invalid"}},),
                )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (character["id"], "tutorial-presentation:1722:14290:0"),
                ).fetchone()
            )
            with db.transaction(force_rollback=True):
                self.assertTrue(once.claim(db, character["id"], 1722, 14291))
            self.assertTrue(once.claim(db, character["id"], 1722, 14291))

        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertFalse(once.claim(db, character["id"], 1722, 14265))

        other_account = self.store.register(
            "presentation-once-other-test", "local-password"
        )["id"]
        other = self.store.create_character(other_account, "Other Presentation")
        with self.store.connection() as db:
            self.assertTrue(once.claim(db, other["id"], 1722, 14265))
