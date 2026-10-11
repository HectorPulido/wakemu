import io
from pathlib import Path
import tempfile
import unittest
from wakfu_server.shop_assets import serve_item_icon


class Handler:
    def __init__(self, path, headers=None, command="GET"):
        self.path = path
        self.headers = headers or {}
        self.command = command
        self.wfile = io.BytesIO()
        self.response_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def send_error(self, status):
        self.status = status


class ShopAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "icons").mkdir()
        self.data = b"\xff\xd8\xfffixture"
        (self.root / "icons" / "24110.jpg").write_bytes(self.data)

    def test_get_head_and_conditional_cache(self):
        request = Handler("/item-icons/24110.jpg?v=1")
        self.assertTrue(serve_item_icon(request, self.root))
        self.assertEqual(request.status, 200)
        self.assertEqual(request.wfile.getvalue(), self.data)
        self.assertEqual(request.response_headers["Content-Type"], "image/jpeg")
        head = Handler("/item-icons/24110.jpg", command="HEAD")
        serve_item_icon(head, self.root)
        self.assertEqual(head.status, 200)
        self.assertEqual(head.wfile.getvalue(), b"")
        cached = Handler(
            "/item-icons/24110.jpg", {"If-None-Match": request.response_headers["ETag"]}
        )
        serve_item_icon(cached, self.root)
        self.assertEqual(cached.status, 304)
        self.assertEqual(cached.wfile.getvalue(), b"")

    def test_missing_malformed_and_symlink_never_expose_files(self):
        for path in (
            "/item-icons/1.jpg",
            "/item-icons/../manifest.json",
            "/item-icons/%2e%2e/manifest.json",
            "/item-icons/0.jpg",
            "/item-icons/24110.jpg/extra",
        ):
            request = Handler(path)
            self.assertTrue(serve_item_icon(request, self.root))
            self.assertEqual(request.status, 404)
        (self.root / "icons" / "2.jpg").symlink_to(self.root / "icons" / "24110.jpg")
        request = Handler("/item-icons/2.jpg")
        serve_item_icon(request, self.root)
        self.assertEqual(request.status, 404)
        self.assertFalse(serve_item_icon(Handler("/health"), self.root))


if __name__ == "__main__":
    unittest.main()
