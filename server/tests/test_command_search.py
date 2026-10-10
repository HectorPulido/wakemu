import unittest

from wakfu_server.command_search import PAGE_SIZE, build_index, search


class CommandSearchTests(unittest.TestCase):
    def setUp(self):
        self.index = build_index(
            [
                {"reference": number, "name": f"Poción azul {number}"}
                for number in range(1, 19)
            ]
            + [{"reference": 50, "name": "Épée du héros"}],
            [
                {"ref": 91, "name": "Puerco salvaje", "min_level": 3, "max_level": 5},
                {"ref": 92, "name": "Puerco mayor", "min_level": 8, "max_level": 10},
            ],
        )

    def test_accent_case_and_typo_matching(self):
        for query in ("ÉPÉE", "epee", "epée", "heroe"):
            with self.subTest(query=query):
                result = search(query, index=self.index)
                self.assertEqual(result["matches"][0]["id"], 50)
        self.assertEqual(
            search("PUERCO", index=self.index)["matches"][0]["kind"], "mob"
        )

    def test_kind_filters_and_ids(self):
        self.assertEqual(
            search("91", kind="mob", index=self.index)["matches"][0]["id"], 91
        )
        self.assertEqual(search("91", kind="item", index=self.index)["total"], 0)
        self.assertTrue(
            all(
                row["kind"] == "item"
                for row in search("poción", kind="objetos", index=self.index)["matches"]
            )
        )
        mobs = search("puerco", kind="monstruos", index=self.index)["matches"]
        self.assertEqual([row["id"] for row in mobs], [92, 91])
        self.assertIn(
            "nivel 3-5", search("puerco", kind="mob", index=self.index)["message"]
        )

    def test_pages_are_stable_and_report_bounds(self):
        first = search("poción", index=self.index)
        second = search("poción", page=2, index=self.index)
        self.assertEqual(first["total"], 18)
        self.assertEqual(first["pages"], 3)
        self.assertEqual(len(first["matches"]), PAGE_SIZE)
        self.assertEqual(len(second["matches"]), PAGE_SIZE)
        self.assertTrue(
            set(row["id"] for row in first["matches"]).isdisjoint(
                row["id"] for row in second["matches"]
            )
        )
        self.assertEqual(search("poción", page=3, index=self.index)["page"], 3)
        with self.assertRaisesRegex(ValueError, "Solo hay 3 páginas"):
            search("poción", page=4, index=self.index)

    def test_no_results_and_malformed_or_hostile_inputs_are_bounded(self):
        empty = search("xyzqwerty", index=self.index)
        self.assertEqual(empty["total"], 0)
        self.assertIn("Sin coincidencias", empty["message"])
        for query in ("", "   ", "!!!", "x" * 121, None, ["poción"]):
            with self.subTest(query=query), self.assertRaises(ValueError):
                search(query, index=self.index)
        for kwargs in (
            {"kind": "users"},
            {"page": 0},
            {"page": True},
            {"page": 1.5},
            {"page": 10001},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search("poción", index=self.index, **kwargs)
        # Query text is displayed as plain bounded text; search does not interpret it.
        hostile = '<script>alert("x")</script>'
        result = search(hostile, index=self.index)
        self.assertIn(hostile, result["message"])
        self.assertEqual(result["matches"], [])


if __name__ == "__main__":
    unittest.main()
