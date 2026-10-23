import importlib


def inspect():
    return importlib.reload(
        importlib.import_module("_qualification_nox_prelude_endpoint_readonly")
    ).survivors()
