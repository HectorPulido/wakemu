import importlib

for name in (
    "tools.import_native_catalogs",
    "test_native_catalog_identity",
    "test_export_installation_seed",
):
    importlib.reload(importlib.import_module(name))
