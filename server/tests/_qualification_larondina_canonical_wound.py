"""Reload the corrected test fixture without reloading production catalogs."""
import importlib
import test_equipment_hp_chance


class CanonicalWoundQualification(
    importlib.reload(test_equipment_hp_chance).EquipmentHpChancePostgresTests
):
    pass
