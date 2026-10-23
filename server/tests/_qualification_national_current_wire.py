"""Refresh only the national query and new representative equip test."""
import importlib
from wakfu_server import national_progression
import test_national_progression_postgres

importlib.reload(national_progression)


class CurrentNationalWireQualification(
    importlib.reload(
        test_national_progression_postgres
    ).NationalProgressionPostgresTests
):
    pass
