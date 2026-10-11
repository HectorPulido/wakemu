#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
probe_dir=$(mktemp -d)
trap 'rm -rf "$probe_dir"' EXIT
cd "$repo_root"
PYTHONPATH=server python3 - "$probe_dir" <<'PY'
import json
import pathlib
import sys
from wakfu_server.shop_http import ShopAdapter

class Domain:
    def catalog(self):
        return [dict(id=1, key="jalato-hammer", name="Jalamartillo", item_ref=2027, price_kamas=1000, category="weapons")]
    def categories(self):
        return [dict(id=1, key="weapons", name="Weapons", description="Equipment")]
    def authenticate(self, token):
        return dict(account_id=1)
    def purchase(self, token, article_id, request_key, *, expected_price):
        assert article_id == 1 and expected_price == 1000
        return dict(order_id="public-contract-receipt")

adapter = ShopAdapter(Domain())
prefix = "/es/shops/WAKFU_INGAME/"
def call(method, route, body=None):
    return adapter.dispatch(method, prefix + route, body or {}, "public-contract-fixture")
def save(model, response):
    (pathlib.Path(sys.argv[1]) / (model + ".json")).write_text(json.dumps(response))

save("Article", call("GET", "articles/1"))
save("Category", call("GET", "categories/1"))
save("CatalogPage", call("POST", "catalog-pages:get"))
save("PromoteGroup", call("GET", "promoteGroup"))
cart = call("POST", "carts", {"cart_details": [{"discriminator": "CartDetailClassicRequest", "cart_detail_classic_request": {"article_id": "1", "quantity": 1, "chosen_references": []}}]})
save("Cart", cart)
route = "carts/" + cart["id"]
save("CartPaymentModeList", call("POST", route + ":list-payment-modes"))
save("Order", call("POST", route + "/orders", {"payment": {"discriminator": "VIRTUAL", "virtual_payment_request": {"payment_mode_id": "OG", "amount": 1000, "currency": "OGR"}}}))
save("AnkamaOgrinePayment", call("POST", "payment/providers/ankama/types/ogrine:create-payment", {"order_id": cart["id"]}))
PY
javac -proc:none -cp 'client/lib/*' -d "$probe_dir" server/shop-service/NativeShopContractProbe.java
java -cp "$probe_dir:client/lib/*" NativeShopContractProbe "$probe_dir"

PYTHONPATH=server python3 - "$probe_dir" <<'PY'
import json
import pathlib
import sys
from wakfu_server.shop_http import ShopAdapter
class Domain:
    def catalog(self):
        return [dict(id=1, key="jalato-hammer", name="Jalamartillo", item_ref=2027, price_kamas=1000, category="weapons")]
    def categories(self):
        return [dict(id=1, key="weapons", name="Weapons", description="Equipment")]
    def authenticate(self, token):
        return dict(account_id=1)
body = json.loads((pathlib.Path(sys.argv[1]) / "NativeCreateCartRequest.json").read_text())
response = ShopAdapter(Domain()).dispatch("POST", "/es/shops/WAKFU_INGAME/carts", body, "public-contract-fixture")
assert response["id"]
print("Actual native create-cart serialization accepted by HTTP adapter: OK")
PY
