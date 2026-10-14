import unittest

from main import API_MOVE_THRESHOLD_DEG, target_offset_deg


class TargetOffsetTests(unittest.TestCase):
    def test_small_combined_change_waits(self):
        offset = target_offset_deg(10.0, 20.0, 11.0, 21.0)

        self.assertLess(offset, API_MOVE_THRESHOLD_DEG)

    def test_accumulated_change_reaches_threshold(self):
        offset = target_offset_deg(10.0, 20.0, 11.5, 21.5)

        self.assertGreaterEqual(offset, API_MOVE_THRESHOLD_DEG)

    def test_azimuth_uses_short_distance_across_zero(self):
        offset = target_offset_deg(10.0, 359.0, 10.0, 1.0)

        self.assertAlmostEqual(offset, 2.0)

    def test_negative_physical_azimuth_wraps_correctly(self):
        offset = target_offset_deg(10.0, -179.0, 10.0, 179.0)

        self.assertAlmostEqual(offset, 2.0)


if __name__ == "__main__":
    unittest.main()