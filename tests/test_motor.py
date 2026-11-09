import math
import unittest

from accessshift.modules.steadyhand.controller import SteadyHandController


class MotorTests(unittest.TestCase):
    def test_frequency_and_export_source(self):
        c = SteadyHandController()
        c.new_tremor_pattern(seed=42)
        c.tremor_intensity = 80
        c.simulate_tremor = True
        for i in range(320):
            c.stabilize(20, 10, i / 60)
        row = c.telemetry.latest
        # Irregular sim still concentrates energy in the Parkinsonian band.
        self.assertIsNotNone(row["dominant_hz"])
        self.assertGreaterEqual(row["dominant_hz"], 4.0)
        self.assertLessEqual(row["dominant_hz"], 7.0)
        self.assertGreater(row["tremor_index"], 40)
        self.assertTrue(row["simulated"])
        c.simulate_tremor = False
        self.assertIsNone(c.telemetry.latest)

    def test_slow_motion_and_short_window(self):
        c = SteadyHandController()
        for i in range(240):
            c.stabilize(math.sin(2 * math.pi * i / 60), 0, i / 60)
            if i < 120:
                self.assertIsNone(c.telemetry.latest)
        self.assertLess(c.telemetry.latest["tremor_index"], 5)

    def test_oscillation_and_release(self):
        c = SteadyHandController()
        hold = c.hold
        hold.press((2, 3), (0, 0), 0)
        for i in range(1, 61):
            raw = (20 * math.sin(i * 2 * math.pi * 5.5 / 60), 0)
            self.assertEqual(hold.move(raw, raw, i / 60), (2, 3))
        self.assertEqual(hold.release((50, 0), True), (2, 3))
        self.assertEqual(c.telemetry.spastic_drags_prevented, 1)
        self.assertEqual(c.telemetry.slip_clicks_rescued, 1)

    def test_drag_requires_sustained_motion(self):
        c = SteadyHandController()
        hold = c.hold
        hold.press((0, 0), (0, 0), 0)
        for i in range(1, 26):
            raw = (3*i, 0)
            point = hold.move(raw, raw, i / 60)
            if i <= 18:
                self.assertEqual(point, (0, 0))
        self.assertTrue(hold.dragging)
        self.assertEqual(c.telemetry.spastic_drags_prevented, 0)
        self.assertEqual(hold.release(raw, True), raw)
        self.assertEqual(c.telemetry.slip_clicks_rescued, 0)
