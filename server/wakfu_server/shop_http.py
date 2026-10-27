"""Native Shopi HTTP adapter; fulfillment remains in the transactional domain."""

import base64
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from wakfu_server.shop_assets import item_icon_url, serve_item_icon

LOG = logging.getLogger(__name__)


def collection(values):
    return {"count": len(values), "values": values}


def article(row):
    ident = str(row["id"])
    icon = item_icon_url(row.get("item_ref", row.get("item_id")))
    price = {
        "amount": row["price_kamas"],
        "original_amount": row["price_kamas"],
        "currency": "OGR",
    }
    return {
        "id": ident,
        "key": row["key"],
        "name": row["name"],
        "description": row.get("description", ""),
        "short_description": row.get("description", ""),
        "subtitle": "Wakemu · 1 ogrine = 1 kama",
        "type": "CLASSIC",
        "media": [
            {
                "discriminator": "MediaImage",
                "media_image": {"image": {"uri": icon}, "key": "main", "type": "image"},
            }
        ]
        if icon
        else [],
        "single_references": [
            {
                "line_number": 1,
                "quantity": row.get("quantity", 1),
                "reference": {
                    "discriminator": "GameActionReference",
                    "game_action_reference": {
                        "id": ident,
                        "name": row["name"],
                        "description": row.get("description", ""),
                        "images": [{"uri": icon, "key": "main"}] if icon else [],
                        "stock_status": "IN_STOCK",
                        "definition": {
                            "id": ident,
                            "actions": [
                                {
                                    "discriminator": "WakfuItemAction",
                                    "wakfu_item_action": {
                                        "item_id": str(
                                            row.get("item_ref", row.get("item_id"))
                                        )
                                    },
                                }
                            ],
                        },
                    },
                },
            }
        ],
        "choosable_references": [],
        "payment_modes": [
            {
                "discriminator": "ArticleVirtualPaymentMode",
                "article_virtual_payment_mode": {
                    "payment_mode_id": "OG",
                    "promotion_ids": [],
                    "price": price,
                },
            }
        ],
        "promotions": [],
        "metadata": [],
        "notices": [],
        "purchase_alone": True,
        "max_quantity": 1,
    }


class ShopAdapter:
    """Short-lived carts are owner-bound; the domain durably deduplicates payments."""

    def __init__(self, domain):
        self.domain = domain
        self.carts = {}
        self.lock = threading.RLock()

    def dispatch(self, method, path, body, token, api_key=""):
        if urlsplit(path).path == "/json/Ankama/v5/Account/CreateToken":
            parameters = parse_qs(urlsplit(path).query)
            if method != "GET" or parameters.get("game") != ["99"]:
                raise ValueError("Unsupported intergame token request")
            from wakfu_server.intergame_domain import Intergame

            return Intergame(self.domain.store).issue_token(api_key)
        if path.split("?")[0] == "/json/Ankama/v5/Shop/GetAccessTokenFromAnkamaApiKey":
            self.domain.authenticate(api_key)
            return {"token": api_key}
        if path.split("?")[0] == "/json/Ankama/v5/Money/OgrinsAmount":
            balance = self.domain.balance(api_key)
            amount = (
                balance.get("balance", balance.get("amount", 0))
                if isinstance(balance, dict)
                else balance
            )
            return {"amount": amount, "currency": "OGR"}
        parsed = urlsplit(path)
        if parsed.path == "/health":
            return {"status": "ok"}
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 4 or parts[1] != "shops" or parts[2].upper() != "WAKFU_INGAME":
            raise LookupError("Unknown shop endpoint")
        route = "/".join(parts[3:])
        if hasattr(self.domain, "public_catalog"):
            snapshot = self.domain.public_catalog()
            rows, category_rows = snapshot["articles"], snapshot["categories"]
        else:
            rows, category_rows = self.domain.catalog(), self.domain.categories()
        category_icons = {}
        for row in rows:
            if row["category"] not in category_icons:
                category_icons[row["category"]] = item_icon_url(
                    row.get("item_ref", row.get("item_id"))
                )
        categories = [
            {
                "id": str(row["id"]),
                "key": row["key"],
                "name": row["name"],
                "description": row.get("description", ""),
                "parent_category_id": "0",
                "level": 0,
                "has_children": False,
                "image": {
                    "uri": category_icons.get(
                        row["key"], "http://127.0.0.1:18083/shop-icon.png"
                    )
                },
            }
            for row in category_rows
        ]

        def find_category(ident):
            return (
                next((value for value in categories if value["id"] == str(ident)), None)
                or self.missing()
            )

        def scoped_rows(ident, *, missing_ok=False):
            selected = next(
                (value for value in categories if value["id"] == str(ident)), None
            )
            if selected is None:
                if missing_ok:
                    return []
                self.missing()
            return [row for row in rows if row["category"] == selected["key"]]

        def page_of(selected_rows, default_limit=20):
            limit = max(1, min(100, int(body.get("limit", default_limit))))
            page = max(1, int(body.get("page", 1)))
            return {
                "count": len(selected_rows),
                "values": [
                    article(row)
                    for row in selected_rows[(page - 1) * limit : page * limit]
                ],
            }

        if method == "GET" and route == "categories":
            return collection(categories)
        if method == "GET" and route.startswith("categories/"):
            category_id = route.split("/")[1]
            selected = find_category(category_id)
            if route.endswith("/breadcrumb"):
                return collection([selected])
            if route == "categories/" + category_id:
                return selected
        if (
            method == "GET"
            and route.startswith("articles/")
            and route.endswith("/breadcrumb")
        ):
            article_id = route.split("/")[1]
            selected_row = next(
                (row for row in rows if str(row["id"]) == article_id), None
            )
            if selected_row is None:
                self.missing()
            return collection(
                [
                    next(
                        value
                        for value in categories
                        if value["key"] == selected_row["category"]
                    )
                ]
            )
        if route.endswith("promoteGroup"):
            if route.startswith("categories/"):
                featured_rows = scoped_rows(route.split("/")[1])[:24]
            else:
                # A small representative home section; the full catalog stays paginated.
                buckets = {value["key"]: [] for value in categories}
                for row in rows:
                    if row["category"] in buckets and len(buckets[row["category"]]) < 3:
                        buckets[row["category"]].append(row)
                featured_rows = [
                    bucket[index]
                    for index in range(3)
                    for bucket in buckets.values()
                    if len(bucket) > index
                ][:24]
            targets = [article(row) for row in featured_rows]
            return {
                "id": "wakemu-home",
                "promote_sections": [
                    {
                        "discriminator": "PromoteSectionArticle",
                        "promote_section_article": {
                            "key": "wakemu-featured",
                            "title": "Wakemu",
                            "description": "Local shop",
                            "targets": targets,
                        },
                    }
                ],
            }
        if route == "catalog-pages:get" and method == "POST":
            category_id = body.get("category_id")
            # Catalog category IDs are filters, including native categories
            # without any local offers. An absent department has an empty page;
            # explicit category resource requests still return 404.
            selected_rows = (
                rows
                if category_id is None
                else scoped_rows(category_id, missing_ok=True)
            )
            return {
                "articles": page_of(selected_rows),
                "possible_sorts": [],
                "current_sort": {
                    "discriminator": "VirtualPriceSort",
                    "virtual_price_sort": {"ordering": "ASC", "currency": "OGR"},
                },
            }
        if route == "articles:search" and method == "POST":
            query = str(body.get("text", "")).casefold()
            return page_of(
                [row for row in rows if query in row["name"].casefold()], 100
            )
        if route == "articles" and method == "GET":
            return page_of(rows, 100)
        if route == "articles:get-by-key" and method == "POST":
            return (
                next(
                    (article(row) for row in rows if row["key"] == body.get("key")),
                    None,
                )
                or self.missing()
            )
        if route.startswith("articles/") and method == "GET":
            return (
                next(
                    (
                        article(row)
                        for row in rows
                        if str(row["id"]) == route.split("/")[1]
                    ),
                    None,
                )
                or self.missing()
            )
        if not token:
            raise PermissionError("An authenticated game session is required")
        self.domain.authenticate(token)
        with self.lock:
            now = time.monotonic()
            self.carts = {
                key: value
                for key, value in self.carts.items()
                if now - value["created"] < 3600
            }
            if route == "carts" and method == "POST":
                details = body.get("cart_details", [])
                if len(details) != 1:
                    raise ValueError("The pilot accepts exactly one article")
                detail = details[0].get("cart_detail_classic_request", {})
                if detail.get("quantity") != 1:
                    raise ValueError("The pilot accepts one fixed article")
                ident = str(detail.get("article_id", ""))
                row = next((row for row in rows if str(row["id"]) == ident), None)
                if row is None:
                    self.missing()
                # Native bTe sends fixed single references as chosen references too.
                chosen = detail.get("chosen_references") or []
                expected = [
                    {
                        "reference_id": ident,
                        "line_number": 1,
                        "quantity": row.get("quantity", 1),
                    }
                ]
                if chosen and chosen != expected:
                    raise ValueError("Chosen references do not match the fixed article")
                cart_id = str(uuid.uuid4())
                self.carts[cart_id] = {
                    "token": token,
                    "article_id": ident,
                    "created": now,
                    "price": row["price_kamas"],
                }
                return self.cart_response(cart_id)
            if (
                route.startswith("payment/providers/ankama/types/ogrine:create-payment")
                and method == "POST"
            ):
                cart_id = str(body.get("order_id", ""))
                cart = self.owned_cart(cart_id, token)
                if not cart.get("ordered"):
                    raise ValueError("Create the order before paying")
                receipt = self.domain.purchase(
                    token,
                    int(cart["article_id"]),
                    cart_id,
                    expected_price=cart["price"],
                )
                return {"payment_id": str(receipt["order_id"]), "order_id": cart_id}
            if route.startswith("carts/"):
                suffix = route[len("carts/") :]
                cart_id = suffix.split("/")[0].split(":")[0]
                cart = self.owned_cart(cart_id, token)
                if method == "DELETE":
                    del self.carts[cart_id]
                    return None
                if suffix == cart_id and method == "GET":
                    return self.cart_response(cart_id)
                if suffix.endswith((":list-payment-modes", "/payment-modes")):
                    return collection(
                        [
                            {
                                "discriminator": "CartVirtualPaymentMode",
                                "cart_virtual_payment_mode": {
                                    "payment_mode_id": "OG",
                                    "recommended": True,
                                    "title": "Wakemu kamas",
                                    "description_html": "1 ogrine = 1 kama",
                                    "price": {
                                        "amount": cart["price"],
                                        "original_amount": cart["price"],
                                        "currency": "OGR",
                                    },
                                    "options": [],
                                    "promotions": [],
                                    "is_under_maintenance": False,
                                },
                            }
                        ]
                    )
                if suffix.endswith("/orders") and method == "POST":
                    payment = body.get("payment", {})
                    virtual = payment.get("virtual_payment_request", {})
                    if (
                        payment.get("discriminator") != "VIRTUAL"
                        or virtual.get("payment_mode_id") != "OG"
                    ):
                        raise ValueError("Unsupported payment mode")
                    if (
                        virtual.get("amount") != cart["price"]
                        or virtual.get("currency") != "OGR"
                    ):
                        raise ValueError("The catalog price changed; reopen the shop")
                    cart["ordered"] = True
                    return {
                        "id": cart_id,
                        "type": "CLI",
                        "payment": {
                            "discriminator": "VIRTUAL",
                            "virtual_payment": dict(
                                virtual, original_amount=cart["price"]
                            ),
                        },
                        "creation_date": datetime.now(timezone.utc).isoformat(),
                        "order_details": [],
                        "shipments": [],
                        "codes": [],
                    }
        self.missing()

    @staticmethod
    def missing():
        raise LookupError("Shop resource not found")

    def owned_cart(self, cart_id, token):
        cart = self.carts.get(cart_id)
        if cart is None:
            self.missing()
        if cart["token"] != token:
            raise PermissionError("Cart belongs to another session")
        return cart

    @staticmethod
    def cart_response(cart_id):
        return {
            "id": cart_id,
            "need_secure": False,
            "need_carrier": False,
            "cart_details": [],
            "problems": [],
            "estimated_totals": [],
            "codes": [],
        }


def make_server(domain, host="0.0.0.0", port=18083):
    adapter = ShopAdapter(domain)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            LOG.info(
                "shop %s %s status=%s",
                self.command,
                urlsplit(self.path).path,
                args[1] if len(args) > 1 else "unknown",
            )

        def handle_request(self):
            if serve_item_icon(self):
                return
            if urlsplit(self.path).path == "/shop-icon.png":
                data = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                )
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 65536:
                    raise ValueError("Invalid request body size")
                body = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object")
                authorization = self.headers.get("Authorization", "")
                token = (
                    authorization[7:]
                    if authorization.lower().startswith("bearer ")
                    else ""
                )
                result = adapter.dispatch(
                    self.command, self.path, body, token, self.headers.get("APIKEY", "")
                )
                status = 204 if result is None else 200
            except PermissionError as error:
                status, result = 401, {
                    "title": "Unauthorized",
                    "detail": str(error),
                    "status": 401,
                }
            except LookupError as error:
                status, result = 404, {
                    "title": "Not found",
                    "detail": str(error),
                    "status": 404,
                }
            except (ValueError, TypeError, KeyError) as error:
                status, result = 400, {
                    "title": "Invalid purchase",
                    "detail": str(error),
                    "status": 400,
                }
            except Exception:
                LOG.exception("Shop request failed")
                status, result = 500, {"title": "Shop unavailable", "status": 500}
            data = json.dumps(result).encode("utf-8") if result is not None else b""
            self.send_response(status)
            self.send_header(
                "Content-Type",
                "application/json" if status < 400 else "application/problem+json",
            )
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = handle_request

    return ThreadingHTTPServer((host, port), Handler)
