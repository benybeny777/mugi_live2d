from __future__ import annotations

import unittest

from scripts.validate_live2d_exports import EXPECTED_PHYSICS, close


class ValidateLive2DExportsTests(unittest.TestCase):
    def test_all_four_hair_groups_are_part_of_the_contract(self) -> None:
        self.assertEqual(set(EXPECTED_PHYSICS), {"後ろ髪", "横髪", "前髪", "アホ毛"})

    def test_float_comparison_is_strict_but_tolerates_json_round_trip(self) -> None:
        self.assertTrue(close(0.8500000001, 0.85))
        self.assertFalse(close(0.86, 0.85))


if __name__ == "__main__":
    unittest.main()
