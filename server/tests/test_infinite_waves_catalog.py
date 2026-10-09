import importlib.util
from pathlib import Path
import unittest


class InfiniteWavesCatalogTests(unittest.TestCase):
    def test_native_raw_catalog_validation_without_inventing_composition(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "tools/extract_native_infinite_waves.py"
        )
        spec = importlib.util.spec_from_file_location("rift_extract_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        row = dict(
            id=3,
            raw_cpb=1314,
            raw_cpc=4160,
            raw_rI=21,
            raw_cpf=527,
            raw_cnn=5,
            raw_cpd_cpi=[4, 1],
            raw_cpe=[{"raw_arM": 527, "raw_cnn": 5}],
        )
        self.assertEqual(module.validate_rows([row]), [row])
        for rows in (
            [],
            [row, row],
            [dict(row, raw_rI=True)],
            [dict(row, raw_cpd_cpi=[-1])],
            [dict(row, raw_cpe=[{}])],
        ):
            with self.assertRaises(ValueError):
                module.validate_rows(rows)
