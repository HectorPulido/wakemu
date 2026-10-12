import importlib.util
from pathlib import Path
import struct
import unittest
import sys

PATH = Path(__file__).parents[1] / "wakfu_server/custom_tasks/presentation.py"
spec = importlib.util.spec_from_file_location("custom_task_presentation_private", PATH)
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


def snapshot():
    return [
        {
            "key": "gobball-kills-20",
            "title": "Chasseur de Bouftous",
            "description": "Defeat 20 Gobballs.",
            "count": 7,
            "target": 20,
            "completed": False,
        }
    ]


class PresentationTests(unittest.TestCase):
    def test_literal_nested_protocol_and_genuine_gift_preserved(self):
        gift = p.GiftPackage("Real gift", "Earned", (p.GiftItem("real:1", 12686, 2),))
        expected = (
            b"\x00\x01\x00\x09Real gift\x00\x06Earned\x00\x01\x00\x06real:1"
            + struct.pack(">ihB", 12686, 2, 0)
        )
        self.assertEqual(p.encode([gift]), expected)
        message, body = p.publication(snapshot(), existing_packages=[gift])
        self.assertEqual(message, 13369)
        self.assertEqual(body[:2], b"\x00\x02")
        self.assertIn(expected[2:-1], body)
        self.assertIn(b"In progress: 7/20", body)
        self.assertNotIn(b"gobball-kills-20", body)
        self.assertEqual(
            p.task_packages(snapshot())[0].title, "Task: Chasseur de Bouftous"
        )
        self.assertEqual(gift.contents[0].gift_id, "real:1")

    def test_completed_and_plain_text_cards_never_invent_claims(self):
        row = snapshot()[0]
        row.update(
            title="Hunter <strong>",
            description="Plant <20> & grow",
            count=20,
            completed=True,
        )
        cards = p.task_packages([row])
        self.assertEqual(cards[0].contents, ())
        self.assertIn("&lt;strong&gt;", cards[0].title)
        self.assertEqual(
            cards[0].description,
            "Plant &lt;20&gt; &amp; grow\nCompleted: 20/20\n" + p.TASK_CLAIM_NOTICE,
        )
        self.assertEqual(p.encode([]), b"\x00\x00\x00")

    def test_duplicate_titles_and_claim_ids_rejected_across_merge(self):
        card = p.task_packages(snapshot())[0]
        with self.assertRaises(ValueError):
            p.publication(snapshot(), existing_packages=[card])
        duplicate = [
            p.GiftPackage(str(i), "", (p.GiftItem("same", 1, 1),)) for i in range(2)
        ]
        with self.assertRaises(ValueError):
            p.encode(duplicate)
        visible_duplicate = snapshot() + [dict(snapshot()[0], key="other-private-key")]
        with self.assertRaises(ValueError):
            p.task_packages(visible_duplicate)
        rows = snapshot() * 2
        with self.assertRaises(ValueError):
            p.task_packages(rows)

    def test_integer_types_shapes_and_invalid_utf8_rejected(self):
        for kwargs in (
            {"reference": True},
            {"quantity": True},
            {"quantity": 32768},
            {"reference": 2**31},
            {"gift_id": "bad\0id"},
        ):
            item = dict(gift_id="id", reference=1, quantity=1)
            item.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                p.encode([p.GiftPackage("x", "", (p.GiftItem(**item),))])
        for bad in ("bad\0text", "\ud800", ""):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                p.encode([p.GiftPackage(bad, "")])
        for change in (
            {"count": True},
            {"target": True},
            {"count": 21},
            {"completed": True},
            {"foreign": 1},
        ):
            row = snapshot()[0]
            row.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.task_packages([row])

    def test_byte_lengths_packet_bounds_and_content_limits(self):
        with self.assertRaises(ValueError):
            p.encode([p.GiftPackage("é" * 32768, "")])
        with self.assertRaises(ValueError):
            p.encode([p.GiftPackage("x", "a" * p.MAX_BODY_BYTES)])
        with self.assertRaises(ValueError):
            p.encode([p.GiftPackage(str(i), "") for i in range(257)])
        with self.assertRaises(ValueError):
            p.encode(
                [
                    p.GiftPackage(
                        "x", "", tuple(p.GiftItem(str(i), 1, 1) for i in range(257))
                    )
                ]
            )
        with self.assertRaises(ValueError):
            p.encode([], cap_reached=1)
        body = p.encode([p.GiftPackage("é", "")], cap_reached=True)
        self.assertEqual(body[2:6], b"\x00\x02\xc3\xa9")
        self.assertEqual(body[-1], 1)


if __name__ == "__main__":
    unittest.main()


class TaskClaimClarityTests(unittest.TestCase):
    def test_progress_and_completed_cards_explicitly_expose_no_manual_claim(self):
        for count in (2, 20):
            rows = snapshot()
            rows[0].update(count=count, completed=count == 20)
            card = p.task_packages(rows)[0]
            self.assertEqual(card.contents, ())
            self.assertIn("No items to claim here", card.description)
            self.assertIn(
                "configured rewards are delivered automatically", card.description
            )
            gift = p.GiftPackage(
                "Genuine reward", "Claimable", (p.GiftItem("owned:1", 12686, 2),)
            )
            message, body = p.publication(rows, existing_packages=(gift,))
            self.assertEqual(message, 13369)
            self.assertIn(b"owned:1", body)
            self.assertEqual(gift.description, "Claimable")
