"""Run the standalone local Wakemu administration service."""
import logging
import os
from wakfu_server.admin_domain import AdminService
from wakfu_server.admin_http import load_credentials, make_server
from wakfu_server.storage.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
store = Store(
    os.environ["WAKFU_DATABASE_URL"],
    password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
)
credentials = load_credentials(
    os.environ.get("WAKFU_ADMIN_CREDENTIALS_FILE", "/data/admin-credentials.json")
)
server = make_server(
    AdminService(store),
    os.environ.get("WAKFU_ADMIN_HOST", "0.0.0.0"),
    int(os.environ.get("WAKFU_ADMIN_PORT", "18084")),
    credentials=credentials,
)
try:
    server.serve_forever()
finally:
    server.server_close()
    store.close()
