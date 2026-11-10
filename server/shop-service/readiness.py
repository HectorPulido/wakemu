"""Shop readiness includes the catalog used by transactional item delivery."""

import json
import logging
from urllib.parse import urlsplit

from wakfu_server.shop_http import make_server

LOG = logging.getLogger(__name__)


def validate_fulfillment(domain):
    from wakfu_server import native_catalog
    from wakfu_server.native_compiled_catalog import resolve_publication
    from wakfu_server.inventory_items import (
        grant,
    )  # Load the real delivery dependencies.
    from wakfu_server.combat_drop_delivery import _template_binding

    publication = resolve_publication(source_revision=native_catalog.release())
    snapshot = domain.public_catalog()
    if snapshot["articles"]:
        _template_binding(snapshot["articles"][0]["item_ref"])
    return publication["generation"]


def make_ready_server(domain, host="0.0.0.0", port=18083, *, check=None):
    check = check or (lambda: validate_fulfillment(domain))
    server = make_server(domain, host, port)
    base_handler = server.RequestHandlerClass

    class ReadyHandler(base_handler):
        def handle_request(self):
            if urlsplit(self.path).path != "/health":
                return super().handle_request()
            try:
                generation = check()
                status, result = 200, {"status": "ok", "catalog_generation": generation}
            except Exception:
                LOG.exception("Shop fulfillment readiness failed")
                status, result = 503, {"status": "unavailable"}
            data = json.dumps(result).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = handle_request

    server.RequestHandlerClass = ReadyHandler
    return server
