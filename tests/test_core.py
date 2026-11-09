import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO
import pandas as pd
from energy_manager.core import Tariff, add_energy, analyze, synthetic_readings, validate_frame

class EnergyTests(unittest.TestCase):
    def setUp(self): self.frame = synthetic_readings(8, 4)
    def test_integrates_power_over_quarter_hour(self):
        x = self.frame.iloc[:2].copy()
        self.assertAlmostEqual(add_energy(x).energy_kwh.sum(), (x.power_w.iloc[0]+x.power_w.iloc[1])/2 * .25/1000)
    def test_tariff_cost(self): self.assertAlmostEqual(Tariff(.3, 2).cost(10), 5)
    def test_invalid_power_factor(self):
        x=self.frame.copy(); x.loc[0,"power_factor"]=1.2
        with self.assertRaises(ValueError): validate_frame(x)
    def test_anomaly_and_metrics(self):
        x=synthetic_readings(96,7); result=analyze(x,Tariff(.3))
        self.assertEqual(result["samples"],96); self.assertGreater(result["energy_kwh"],0); self.assertGreaterEqual(result["anomaly_count"],1)
    def test_duplicate_timestamps_rejected(self):
        x=self.frame.copy(); x.loc[1,"timestamp"]=x.loc[0,"timestamp"]
        with self.assertRaises(ValueError): validate_frame(x)
    def test_cli_smoke(self):
        from energy_manager.cli import main
        with patch("sys.argv",["energy"]),redirect_stdout(StringIO()) as output: main()
        self.assertIn("energy_kwh",output.getvalue())
