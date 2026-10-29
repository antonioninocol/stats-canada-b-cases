import json
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from statcan_lab.cli import main

ROOT = Path(__file__).resolve().parents[1]


class PublishAndAppTest(unittest.TestCase):
    def test_demo_publish_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["demo", "--published-dir", str(Path(tmp) / "pub")]), 0)
            names = {p.name for p in (Path(tmp) / "pub").iterdir()}
            self.assertTrue({"province_panel.csv", "immigrant_gap.csv", "degree_ratio.csv", "meta.json", "lag_correlation_canada.csv"} <= names)
            meta = json.loads((Path(tmp) / "pub" / "meta.json").read_text())
            self.assertTrue(meta["synthetic"])

    def test_app_runs_on_demo_and_flags_synthetic(self):
        demo = ROOT / "published_demo"
        self.assertTrue((demo / "province_panel.csv").exists(), "genera published_demo con: python -m statcan_lab demo")
        at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertTrue(any("SINTÉTICOS" in e.value for e in at.error))
        self.assertEqual(len(at.tabs), 4)


if __name__ == "__main__":
    unittest.main()
