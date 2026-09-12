import unittest

from run_limits import capture_conductor_pressure, pressure_limit_breaches


class PressureLimitTests(unittest.TestCase):
    limits = {
        "conductor_frac_pressure": 10.0,
        "max_wellhead_pressure": 20.0,
        "max_pump_pressure": 30.0,
    }

    def test_conductor_fracture_pressure(self):
        breaches = pressure_limit_breaches(10.1, 20.0, 30.0, self.limits)
        self.assertEqual([item["code"] for item in breaches], ["conductor_fracture"])

    def test_wellhead_pressure(self):
        breaches = pressure_limit_breaches(10.0, 20.1, 30.0, self.limits)
        self.assertEqual([item["code"] for item in breaches], ["wellhead_pressure"])

    def test_pump_pressure(self):
        breaches = pressure_limit_breaches(10.0, 20.0, 30.1, self.limits)
        self.assertEqual([item["code"] for item in breaches], ["pump_pressure"])

    def test_equal_values_do_not_fail(self):
        self.assertEqual(pressure_limit_breaches(10.0, 20.0, 30.0, self.limits), [])

    def test_reports_all_breaches(self):
        breaches = pressure_limit_breaches(11.0, 21.0, 31.0, self.limits)
        self.assertEqual(len(breaches), 3)

    def test_solver_records_conductor_pressure(self):
        conductor_pressure = capture_conductor_pressure(-1, 1.6, 1.5, 120_000.0)
        self.assertEqual(conductor_pressure, 120_000.0)

    def test_conductor_pressure_is_captured_only_once(self):
        conductor_pressure = capture_conductor_pressure(120_000.0, 2.0, 1.5, 130_000.0)
        self.assertEqual(conductor_pressure, 120_000.0)


if __name__ == "__main__":
    unittest.main()
