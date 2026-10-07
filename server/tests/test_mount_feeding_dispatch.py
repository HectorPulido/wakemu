import unittest
from unittest.mock import patch

from wakfu_server import mount_feeding_dispatch


class MountFeedingDispatchTests(unittest.TestCase):
    def test_publishes_committed_packet_batch_once(self):
        packets = [(12470, b"food"), (12470, b"pet"), (12471, b"snapshot")]
        result = {"applied": True, "replayed": False, "packets": packets}
        published = []
        with patch(
            "wakfu_server.mount_feeding_dispatch.mount_feeding.feed",
            return_value=result,
        ):
            actual = mount_feeding_dispatch.handle(
                object(),
                1,
                "lease",
                2,
                b"request",
                in_fight=False,
                publish=published.append,
            )
        self.assertIs(actual, result)
        self.assertEqual(published, [packets])

    def test_replay_does_not_republish_and_preserves_result(self):
        result = {"applied": False, "replayed": True, "packets": []}
        published = []
        with patch(
            "wakfu_server.mount_feeding_dispatch.mount_feeding.feed",
            return_value=result,
        ):
            actual = mount_feeding_dispatch.handle(
                object(),
                1,
                "lease",
                2,
                b"request",
                in_fight=False,
                publish=published.append,
            )
        self.assertIs(actual, result)
        self.assertEqual(published, [])

    def test_publish_failure_propagates_without_retry(self):
        result = {"applied": True, "replayed": False, "packets": [(12471, b"snapshot")]}
        calls = []

        def fail(packets):
            calls.append(packets)
            raise OSError("socket send failed")

        with patch(
            "wakfu_server.mount_feeding_dispatch.mount_feeding.feed",
            return_value=result,
        ):
            with self.assertRaisesRegex(OSError, "socket send failed"):
                mount_feeding_dispatch.handle(
                    object(), 1, "lease", 2, b"request", in_fight=False, publish=fail
                )
        self.assertEqual(calls, [result["packets"]])

    def test_publisher_value_error_is_post_commit_and_propagates(self):
        result = {"applied": True, "replayed": False, "packets": [(12471, b"snapshot")]}
        publisher_calls = []

        def fail_after_commit(packets):
            publisher_calls.append(packets)
            raise ValueError("bad outgoing frame")

        with patch(
            "wakfu_server.mount_feeding_dispatch.mount_feeding.feed",
            return_value=result,
        ) as feed:
            with self.assertRaisesRegex(ValueError, "bad outgoing frame"):
                mount_feeding_dispatch.handle(
                    object(),
                    1,
                    "lease",
                    2,
                    b"request",
                    in_fight=False,
                    publish=fail_after_commit,
                )
        feed.assert_called_once()
        self.assertEqual(publisher_calls, [result["packets"]])

    def test_publisher_is_mandatory(self):
        with self.assertRaisesRegex(ValueError, "publisher is required"):
            mount_feeding_dispatch.handle(
                object(), 1, "lease", 2, b"request", in_fight=False, publish=None
            )


if __name__ == "__main__":
    unittest.main()
