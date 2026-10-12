"""Keep achievement projections on the caller's database snapshot."""
import unittest
from unittest.mock import patch

from wakfu_server.achievements import catalog, service


class AchievementProjectSectionDatabaseTests(unittest.TestCase):
    def test_supplied_connection_is_forwarded_to_catalog_without_fallback(self):
        connection = object()
        progress = {
            "variables": {},
            "objectives": [],
            "running": [],
            "completed": [],
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }

        def load(supplied_connection=None):
            self.assertIs(supplied_connection, connection)
            return {"definitions": {}}

        with patch.object(catalog, "load", side_effect=load) as load_catalog:
            service.project_section(progress, None, db=connection)

        load_catalog.assert_called_once_with(connection)
