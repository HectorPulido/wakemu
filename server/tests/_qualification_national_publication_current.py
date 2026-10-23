"""Refresh only changed import and new publication qualification code."""
import importlib
from wakfu_server import national_progression
import test_national_earnings_postgres

importlib.reload(national_progression)
importlib.reload(test_national_earnings_postgres)
