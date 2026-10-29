import tempfile
import unittest
from pathlib import Path

from statcan_lab import analyses as A
from statcan_lab import config as C
from statcan_lab.cli import main
from statcan_lab.db import connect
from statcan_lab.series import SchemaError, select_series

from statcan_lab.demo_fixtures import build


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        build(root / "fixtures")
        args = ["--data-dir", str(root / "data"), "--out-dir", str(root / "out"), "--local-dir", str(root / "fixtures")]
        assert main([*args, "fetch"]) == 0
        cls.args = args
        cls.root = root
        cls.con = connect(root / "data" / "statcan.duckdb")

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls.tmp.cleanup()

    def test_scalar_and_bom(self):
        df = select_series(self.con, C.LFS_PROVINCE, C.F_LFS_UNEMPLOYED, geo="^Canada$")
        self.assertEqual(len(df), 45)  # 45 meses, una fila por periodo (filtros descartan ruido)
        self.assertGreater(df["value"].min(), 100_000)  # 'thousands' convertido a personas

    def test_ei_gap_join(self):
        df = A.ei_gap(self.con)
        self.assertTrue({"unemployed", "ei_regular", "ei_per_unemployed"} <= set(df.columns))
        self.assertNotIn("Yukon", set(df["geo"]))  # sin contraparte en LFS, el inner join lo descarta
        self.assertTrue(df["ei_per_unemployed"].between(0.1, 0.6).all())

    def test_immigrant_gap(self):
        df = A.immigrant_gap(self.con)
        vr = df[df["immigrant_status"].str.contains("Very recent")]
        self.assertAlmostEqual(vr["gap_pp"].mean(), 4.0, places=1)
        self.assertIn("Toronto, Ontario", set(df["geo"]))

    def test_degree_ratio(self):
        df = A.degree_ratio(self.con)
        latest = df[df["period"] == df["period"].max()].set_index("education_required")["unemployed_per_vacancy"]
        self.assertGreater(latest["Bachelor's degree or higher"], 4)
        self.assertLess(latest["Trade certificate or diploma"], 2)

    def test_lag_correlation_recovers_planted_lag(self):
        panel = A.province_panel(self.con)
        # EI en niveles vs desempleados: la senal sembrada (rezago de 2 meses) sale casi limpia
        clean = A.lag_correlation(panel, geo="Canada", a="unemployed", b="ei_regular")
        best = clean.loc[clean["corr"].idxmax()]
        self.assertEqual(int(best["lag_months"]), 2)
        self.assertGreater(best["corr"], 0.95)
        # el ratio EI/desempleados diluye la senal (tambien cambia el denominador), pero el pico sigue en 2
        ratio = A.lag_correlation(panel, geo="Canada")
        self.assertEqual(int(ratio.loc[ratio["corr"].idxmax()]["lag_months"]), 2)

    def test_cross_section_and_outliers(self):
        panel = A.province_panel(self.con)
        cs = A.cross_section(panel)
        self.assertEqual(len(cs), 10)
        self.assertIn("recent_immigrant_gap_pp", cs.columns)
        self.assertFalse(A.outliers(panel).empty)

    def test_missing_filter_raises_with_hint(self):
        with self.assertRaises(SchemaError) as ctx:  # sin filtro de sexo hay filas duplicadas
            select_series(self.con, C.EI_REGULAR, {"?^Age": r"^15 years and over$", "?^Declared": r"^Total"})
        self.assertIn("Sex", str(ctx.exception))

    def test_bad_value_filter_lists_options(self):
        with self.assertRaises(SchemaError) as ctx:
            select_series(self.con, C.LFS_PROVINCE, {"^Labour force char": r"^Nope$"})
        self.assertIn("Unemployment rate", str(ctx.exception))

    def test_cli_run_all(self):
        for name in ("ei_gap", "immigrant_gap", "degree_ratio", "explore"):
            self.assertEqual(main([*self.args, "run", name]), 0)
        self.assertTrue((self.root / "out" / "lag_correlation_canada.csv").exists())


if __name__ == "__main__":
    unittest.main()
