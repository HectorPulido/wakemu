"""Load just the new complete companion equip/refusal integration case."""
import importlib
import test_national_progression_postgres


class NationalCompanionRefusalQualification(
    importlib.reload(
        test_national_progression_postgres
    ).NationalProgressionPostgresTests
):
    pass
