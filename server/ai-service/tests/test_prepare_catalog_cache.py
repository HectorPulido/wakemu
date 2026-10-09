"""Early catalogue publication stays outside the NPC decision deadline."""
import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

from scripts import prepare_catalog_cache as prepare


class PrepareCatalogCacheTests(unittest.TestCase):
    def test_seal_publishes_complete_catalogue_and_closes_transport(self):
        exporter = object()
        transport = Mock()
        transport.catalog.return_value = "a" * 64
        transport.metrics = {"requests": 2}
        with patch("sys.argv", ["prepare_catalog_cache.py", "--seal"]), patch.object(
            prepare, "native_exporter", return_value=exporter
        ), patch.object(
            prepare, "ContextTransport", return_value=transport
        ), contextlib.redirect_stdout(
            io.StringIO()
        ) as output:
            prepare.main()
        transport.catalog.assert_called_once_with(exporter)
        transport.close.assert_called_once_with()
        result = json.loads(output.getvalue())
        self.assertTrue(result["complete"])
        self.assertEqual(result["sha256"], "a" * 64)

    def test_preparation_failure_is_not_reported_as_ready(self):
        transport = Mock()
        transport.catalog.side_effect = ValueError("incomplete catalogue")
        with patch("sys.argv", ["prepare_catalog_cache.py", "--seal"]), patch.object(
            prepare, "native_exporter", return_value=object()
        ), patch.object(
            prepare, "ContextTransport", return_value=transport
        ), contextlib.redirect_stdout(
            io.StringIO()
        ) as output:
            with self.assertRaisesRegex(ValueError, "incomplete catalogue"):
                prepare.main()
        self.assertEqual(output.getvalue(), "")
        transport.close.assert_called_once_with()
