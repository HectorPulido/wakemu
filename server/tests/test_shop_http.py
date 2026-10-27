"""Shopi protocol adapter tests without a database or network server."""

import unittest
from unittest.mock import patch

from wakfu_server.shop_http import ShopAdapter
from wakfu_server.shop_http import article as serialize_article


class FakeShopDomain:
    def __init__(self):
        self.rows = [
            {
                "id": 7,
                "key": "jalato-hammer",
                "name": "Jalamartillo",
                "description": "A test weapon",
                "item_ref": 2027,
                "quantity": 1,
                "price_kamas": 1000,
                "category": "weapons",
            },
            {
                "id": 8,
                "key": "pet-companion",
                "name": "Test Pet",
                "description": "A second test product",
                "item_ref": 2027,
                "quantity": 1,
                "price_kamas": 1000,
                "category": "pets",
            },
            {
                "id": 9,
                "key": "hidden-article",
                "name": "Hidden Product",
                "description": "Disabled department product",
                "item_ref": 2027,
                "quantity": 1,
                "price_kamas": 1000,
                "category": "disabled",
            },
        ]
        self.category_rows = [
            {
                "id": 10,
                "key": "items",
                "name": "Items",
                "description": "",
                "sort_order": 10,
                "enabled": True,
            },
            {
                "id": 20,
                "key": "weapons",
                "name": "Weapons",
                "description": "",
                "sort_order": 20,
                "enabled": True,
            },
            {
                "id": 30,
                "key": "disabled",
                "name": "Disabled",
                "description": "",
                "sort_order": 30,
                "enabled": False,
            },
            {
                "id": 40,
                "key": "pets",
                "name": "Pets",
                "description": "",
                "sort_order": 40,
                "enabled": True,
            },
        ]
        self.purchases = []

    def authenticate(self, token):
        if token != "valid-session-token-123456789":
            raise PermissionError("expired")
        return {"account_id": 11}

    def balance(self, token):
        self.authenticate(token)
        return 5000

    def catalog(self):
        enabled = {row["key"] for row in self.categories()}
        return [row for row in self.rows if row["category"] in enabled]

    def categories(self):
        return sorted(
            [row for row in self.category_rows if row["enabled"]],
            key=lambda row: (row["sort_order"], row["id"]),
        )

    def purchase(self, token, article_id, request_key, *, expected_price=None):
        self.authenticate(token)
        call = (token, article_id, request_key, expected_price)
        self.purchases.append(call)
        return {"order_id": "order-1"}


class ShopHttpTests(unittest.TestCase):
    def setUp(self):
        self.domain = FakeShopDomain()
        self.adapter = ShopAdapter(self.domain)
        self.token = "valid-session-token-123456789"
        self.base = "/en/shops/WAKFU_INGAME/"

    def test_catalog_article_exposes_item_action_and_one_og_price(self):
        result = self.adapter.dispatch(
            "POST", self.base + "catalog-pages:get", {"page": 1, "limit": 20}, ""
        )
        self.assertEqual(2, result["articles"]["count"])
        value = next(row for row in result["articles"]["values"] if row["id"] == "7")
        self.assertEqual("jalato-hammer", value["key"])
        self.assertEqual(
            "2027",
            value["single_references"][0]["reference"]["game_action_reference"][
                "definition"
            ]["actions"][0]["wakfu_item_action"]["item_id"],
        )
        payment = value["payment_modes"][0]["article_virtual_payment_mode"]
        self.assertEqual("OG", payment["payment_mode_id"])
        self.assertEqual(
            {"amount": 1000, "original_amount": 1000, "currency": "OGR"},
            payment["price"],
        )

    def test_native_media_and_reference_images_share_the_item_icon(self):
        value = self.adapter.dispatch("GET", self.base + "articles/7", {}, "")
        media = value["media"][0]
        self.assertEqual("MediaImage", media["discriminator"])
        url = media["media_image"]["image"]["uri"]
        self.assertTrue(url.endswith("/item-icons/2027.jpg"))
        reference = value["single_references"][0]["reference"]["game_action_reference"]
        self.assertEqual(url, reference["images"][0]["uri"])

    def test_large_catalog_promotions_search_and_pages_have_bounded_payloads(self):
        self.domain.rows = [
            dict(self.domain.rows[0], id=index, key=f"item-{index}")
            for index in range(12000)
        ]
        with patch("wakfu_server.shop_http.article", wraps=serialize_article) as encode:
            page = self.adapter.dispatch(
                "POST", self.base + "catalog-pages:get", {"page": 2, "limit": 20}, ""
            )
            self.assertEqual(12000, page["articles"]["count"])
            self.assertEqual(20, encode.call_count)
            self.assertEqual("20", page["articles"]["values"][0]["id"])
        home = self.adapter.dispatch("GET", self.base + "promoteGroup", {}, "")
        targets = home["promote_sections"][0]["promote_section_article"]["targets"]
        self.assertLessEqual(len(targets), 24)
        search = self.adapter.dispatch("POST", self.base + "articles:search", {}, "")
        self.assertEqual(12000, search["count"])
        self.assertEqual(100, len(search["values"]))

    def test_category_list_catalog_membership_and_disabled_scope_do_not_leak_articles(
        self,
    ):
        listed = self.adapter.dispatch("GET", self.base + "categories", {}, "")
        self.assertEqual(["10", "20", "40"], [row["id"] for row in listed["values"]])
        self.assertEqual(
            ["items", "weapons", "pets"], [row["key"] for row in listed["values"]]
        )

        weapons = self.adapter.dispatch(
            "POST",
            self.base + "catalog-pages:get",
            {"category_id": "20", "limit": 20},
            "",
        )
        self.assertEqual(1, weapons["articles"]["count"])
        self.assertEqual(["7"], [row["id"] for row in weapons["articles"]["values"]])
        pets = self.adapter.dispatch(
            "POST",
            self.base + "catalog-pages:get",
            {"category_id": "40", "limit": 20},
            "",
        )
        self.assertEqual(["8"], [row["id"] for row in pets["articles"]["values"]])
        promote = self.adapter.dispatch(
            "GET", self.base + "categories/20/promoteGroup", {}, ""
        )
        self.assertEqual(
            ["7"],
            [
                row["id"]
                for row in promote["promote_sections"][0]["promote_section_article"][
                    "targets"
                ]
            ],
        )

        all_articles = self.adapter.dispatch("GET", self.base + "articles", {}, "")
        self.assertEqual({"7", "8"}, {row["id"] for row in all_articles["values"]})
        with self.assertRaises(LookupError):
            self.adapter.dispatch("GET", self.base + "categories/30", {}, "")
        for category_id in ("999", "30", "450"):
            absent = self.adapter.dispatch(
                "POST",
                self.base + "catalog-pages:get",
                {"category_id": category_id},
                "",
            )
            self.assertEqual(absent["articles"], {"count": 0, "values": []})

    def test_cart_order_and_payment_purchase_once_at_catalog_price(self):
        cart = self.adapter.dispatch(
            "POST",
            self.base + "carts",
            {
                "cart_details": [
                    {
                        "discriminator": "CartDetailClassicRequest",
                        "cart_detail_classic_request": {
                            "article_id": "7",
                            "quantity": 1,
                            "chosen_references": [
                                {"reference_id": "7", "line_number": 1, "quantity": 1}
                            ],
                        },
                    }
                ]
            },
            self.token,
        )
        cart_id = cart["id"]
        self.adapter.dispatch(
            "POST",
            self.base + f"carts/{cart_id}/orders",
            {
                "payment": {
                    "discriminator": "VIRTUAL",
                    "virtual_payment_request": {
                        "payment_mode_id": "OG",
                        "amount": 1000,
                        "currency": "OGR",
                    },
                }
            },
            self.token,
        )
        self.adapter.dispatch(
            "POST",
            self.base + "payment/providers/ankama/types/ogrine:create-payment",
            {"order_id": cart_id},
            self.token,
        )
        self.assertEqual([(self.token, 7, cart_id, 1000)], self.domain.purchases)

    def test_fixed_article_accepts_exact_java_chosen_reference_and_rejects_tampering(
        self,
    ):
        exact = {"reference_id": "7", "line_number": 1, "quantity": 1}
        valid_detail = {
            "discriminator": "CartDetailClassicRequest",
            "cart_detail_classic_request": {
                "article_id": "7",
                "quantity": 1,
                "chosen_references": [exact],
            },
        }
        cart = self.adapter.dispatch(
            "POST",
            self.base + "carts",
            {"cart_details": [valid_detail]},
            self.token,
        )
        self.assertIn(cart["id"], self.adapter.carts)

        tampered_details = (
            {
                "article_id": "7",
                "quantity": 1,
                "chosen_references": [
                    {"reference_id": "2027", "line_number": 1, "quantity": 1},
                ],
            },
            {
                "article_id": "7",
                "quantity": 1,
                "chosen_references": [
                    {"reference_id": "7", "line_number": 1, "quantity": 2},
                ],
            },
            {"article_id": "7", "quantity": 2, "chosen_references": [exact]},
            {
                "article_id": "7",
                "quantity": 1,
                "chosen_references": [
                    {"reference_id": "7", "line_number": 2, "quantity": 1},
                ],
            },
        )
        for index, detail in enumerate(tampered_details):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.adapter.dispatch(
                    "POST",
                    self.base + "carts",
                    {"cart_details": [{"cart_detail_classic_request": detail}]},
                    self.token,
                )

    def test_cart_is_session_bound_and_rejects_unsupported_quantity_and_currency(self):
        with self.assertRaisesRegex(ValueError, "exactly one article"):
            self.adapter.dispatch(
                "POST", self.base + "carts", {"cart_details": []}, self.token
            )
        cart = self.adapter.dispatch(
            "POST",
            self.base + "carts",
            {
                "cart_details": [
                    {
                        "cart_detail_classic_request": {
                            "article_id": "7",
                            "quantity": 1,
                            "chosen_references": [],
                        }
                    }
                ]
            },
            self.token,
        )
        with self.assertRaises(PermissionError):
            self.adapter.dispatch(
                "GET",
                self.base + f"carts/{cart['id']}",
                {},
                "another-session-token-123456",
            )
        with self.assertRaisesRegex(ValueError, "Unsupported payment mode"):
            self.adapter.dispatch(
                "POST",
                self.base + f"carts/{cart['id']}/orders",
                {"payment": {"discriminator": "FREE", "virtual_payment_request": {}}},
                self.token,
            )

    def test_payment_cannot_run_before_order_or_with_a_malformed_order_price(self):
        cart = self.adapter.dispatch(
            "POST",
            self.base + "carts",
            {
                "cart_details": [
                    {
                        "cart_detail_classic_request": {
                            "article_id": "7",
                            "quantity": 1,
                            "chosen_references": [],
                        }
                    }
                ]
            },
            self.token,
        )
        payment_path = (
            self.base + "payment/providers/ankama/types/ogrine:create-payment"
        )
        with self.assertRaisesRegex(ValueError, "Create the order before paying"):
            self.adapter.dispatch(
                "POST", payment_path, {"order_id": cart["id"]}, self.token
            )
        with self.assertRaisesRegex(ValueError, "catalog price changed"):
            self.adapter.dispatch(
                "POST",
                self.base + f"carts/{cart['id']}/orders",
                {
                    "payment": {
                        "discriminator": "VIRTUAL",
                        "virtual_payment_request": {
                            "payment_mode_id": "OG",
                            "amount": 999,
                            "currency": "OGR",
                        },
                    }
                },
                self.token,
            )
        self.assertEqual([], self.domain.purchases)

    def test_wallet_endpoints_use_api_key_and_current_authoritative_balance(self):
        self.assertEqual(
            {"token": self.token},
            self.adapter.dispatch(
                "GET",
                "/json/Ankama/v5/Shop/GetAccessTokenFromAnkamaApiKey",
                {},
                "",
                self.token,
            ),
        )
        self.assertEqual(
            {"amount": 5000, "currency": "OGR"},
            self.adapter.dispatch(
                "GET", "/json/Ankama/v5/Money/OgrinsAmount", {}, "", self.token
            ),
        )
        with self.assertRaises(PermissionError):
            self.adapter.dispatch(
                "GET", "/json/Ankama/v5/Money/OgrinsAmount", {}, "", "stale-api-token"
            )
