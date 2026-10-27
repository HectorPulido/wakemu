"""Bounded HTTP integrations available only to explicitly configured behaviors."""
import json
import time
import urllib.error
import urllib.request
from fractions import Fraction
from urllib.parse import urlencode, urlsplit


class RemoteError(RuntimeError):
    def __init__(self, status, code="remote_error"):
        self.status, self.code = status, code
        super().__init__(f"Remote request failed ({status}, {code})")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        raise urllib.error.HTTPError(
            request.full_url, code, "Redirects are disabled", headers, response
        )


class JsonClient:
    def __init__(self, base_url, token="", *, timeout=3, max_response=4 * 1024 * 1024):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid integration URL")
        self.base_url, self.token = base_url.rstrip("/"), token
        self.timeout, self.max_response = timeout, max_response
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, body=None):
        data = (
            None if body is None else json.dumps(body, separators=(",", ":")).encode()
        )
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            # Do not include remote payloads or credentials in errors/logs.
            code = "remote_error"
            try:
                payload = json.loads(error.read(4096))
                candidate = payload.get("error") if isinstance(payload, dict) else None
                if candidate in {
                    "world_epoch_changed",
                    "event_cursor_expired",
                    "exchange_revision_changed",
                    "exchange_revision_stale",
                    "exchange_closed",
                    "command_expired",
                }:
                    code = candidate
            except (ValueError, OSError):
                pass
            error.close()
            raise RemoteError(error.code, code) from None
        with response:
            raw = response.read(self.max_response + 1)
        if len(raw) > self.max_response:
            raise ValueError("Integration response exceeds size limit")
        return json.loads(raw)


class WorldClient(JsonClient):
    world_epoch = None

    def snapshot(self):
        result = self.request("GET", "/internal/bots/snapshot")
        epoch = result.get("world_epoch") if isinstance(result, dict) else None
        if not isinstance(epoch, str) or not epoch:
            raise ValueError("Invalid World epoch")
        self.world_epoch = epoch
        return result

    def events(self, after):
        return self.request(
            "GET",
            "/internal/bots/events?"
            + urlencode({"after": after, "world_epoch": self.world_epoch}),
        )

    def command(self, bot_id, action, args, request_id, *, issued_at=None):
        return self.request(
            "POST",
            "/internal/bots/commands",
            {
                "bot_id": bot_id,
                "action": action,
                "args": args,
                "request_id": request_id,
                "world_epoch": self.world_epoch,
                "issued_at": time.time() if issued_at is None else issued_at,
            },
        )


class ShopClient:
    def __init__(self, http, *, ttl=15, clock=time.monotonic):
        self.http, self.ttl, self.clock = http, ttl, clock
        self.prices, self.valid_until = {}, 0

    def catalog(self):
        if self.clock() < self.valid_until:
            return self.prices
        prices = {}
        for page in range(1, 10001):
            payload = self.http.request(
                "POST",
                "/v1/shops/WAKFU_INGAME/catalog-pages:get",
                {"page": page, "limit": 100},
            )
            articles = payload["articles"]
            rows, count = articles["values"], articles["count"]
            if not isinstance(rows, list) or type(count) is not int or count < 0:
                raise ValueError("Invalid shop catalog page")
            for row in rows:
                references = row.get("single_references", [])
                if len(references) != 1:
                    continue
                reference = references[0]
                quantity = reference.get("quantity")
                actions = (
                    reference.get("reference", {})
                    .get("game_action_reference", {})
                    .get("definition", {})
                    .get("actions", [])
                )
                if type(quantity) is not int or quantity <= 0 or len(actions) != 1:
                    continue
                action = actions[0]
                if action.get("discriminator") != "WakfuItemAction":
                    continue
                item_id = int(action["wakfu_item_action"]["item_id"])
                for mode in row.get("payment_modes", []):
                    price = mode.get("article_virtual_payment_mode", {}).get(
                        "price", {}
                    )
                    amount = price.get("amount")
                    if (
                        price.get("currency") != "OGR"
                        or type(amount) is not int
                        or amount < 0
                    ):
                        continue
                    unit_price = Fraction(amount, quantity)
                    prices[item_id] = min(prices.get(item_id, unit_price), unit_price)
            if page * 100 >= count:
                self.prices, self.valid_until = prices, self.clock() + self.ttl
                return prices
            if not rows:
                raise ValueError("Incomplete shop catalog")
        raise ValueError("Shop catalog exceeds page limit")

    def quote(self, items, purchase_percent=80):
        prices = self.catalog()
        total = Fraction()
        for item in items:
            reference, quantity = item.get("reference"), item.get("quantity")
            if type(reference) is not int or type(quantity) is not int or quantity <= 0:
                raise ValueError("Invalid offered item")
            if reference not in prices:
                return None
            total += prices[reference] * quantity * purchase_percent / 100
        return total.numerator // total.denominator


class LlmClient:
    """Optional generic internal conversation endpoint; no implicit provider access."""

    def __init__(self, http):
        self.http = http

    def reply(self, bot_id, personality, message):
        payload = self.http.request(
            "POST",
            "/reply",
            {
                "bot_id": bot_id,
                "messages": [
                    {"role": "system", "content": personality},
                    {"role": "user", "content": message},
                ],
            },
        )
        text = payload.get("text") if isinstance(payload, dict) else None
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text.encode()) > 1024
            or "\x00" in text
            or text.startswith("!")
        ):
            raise ValueError("Invalid conversation reply")
        return text.strip()
