"""Load genuine flora and monster integrations plus the updated neutrality rule."""
import importlib
from wakfu_server import (
    national_earnings,
    neutrality_item_actions,
    flora_ecology,
    monster_birth_ecology,
    monster_removal_ecology,
)
import test_national_earnings_postgres

for module in (
    national_earnings,
    neutrality_item_actions,
    flora_ecology,
    monster_birth_ecology,
    monster_removal_ecology,
    test_national_earnings_postgres,
):
    importlib.reload(module)
