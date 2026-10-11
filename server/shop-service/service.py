"""Run the Wakemu native shop HTTP service."""
import logging
import os
from wakfu_server.shop_domain import ShopService
from wakfu_server.shop_http import make_server
from wakfu_server.shop_cache import PublicCatalogCache, redis_from_environment
from wakfu_server.storage.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
store = Store(
    os.environ["WAKFU_DATABASE_URL"],
    password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
)
domain = ShopService(store)
domain.public_cache = PublicCatalogCache(
    domain.load_public_catalog,
    domain.catalog_revision,
    redis_client=redis_from_environment(),
)
try:
    snapshot = domain.public_cache.get()
    logging.info("Warmed shop catalog: %d active articles", len(snapshot["articles"]))
except Exception:
    logging.exception("Shop catalog warmup failed; requests will retry the database")
server = make_server(
    domain,
    os.environ.get("WAKFU_SHOP_HOST", "0.0.0.0"),
    int(os.environ.get("WAKFU_SHOP_PORT", "18083")),
)
try:
    server.serve_forever()
finally:
    server.server_close()
    store.close()
