from __future__ import annotations

import unittest

from scripts.validate_live2d_exports import (
    EXPECTED_PHYSICS,
    EXPECTED_TEXTURE_COUNT,
    EXPECTED_TEXTURE_SIZE,
    MIN_ALPHA_PERCENT,
    close,
    topology_metric,
    validate_topology,
)


def topology(counts: list[int], parameters: int = 29) -> dict:
    return {
        "parameters": {"count": parameters},
        "drawables": [
            {"id": f"ArtMesh{index}", "vertexCount": count} for index, count in enumerate(counts)
        ],
    }


class ValidateLive2DExportsTests(unittest.TestCase):
    def test_release_uses_one_8192_texture_sheet(self) -> None:
        self.assertEqual(EXPECTED_TEXTURE_COUNT, 1)
        self.assertEqual(EXPECTED_TEXTURE_SIZE, (8192, 8192))
        self.assertEqual(MIN_ALPHA_PERCENT, 6.0)

    def test_all_four_hair_groups_are_part_of_the_contract(self) -> None:
        self.assertEqual(set(EXPECTED_PHYSICS), {"後ろ髪", "横髪", "前髪", "アホ毛"})

    def test_float_comparison_is_strict_but_tolerates_json_round_trip(self) -> None:
        self.assertTrue(close(0.8500000001, 0.85))
        self.assertFalse(close(0.86, 0.85))


class TopologyGateTests(unittest.TestCase):
    def test_a_rigged_model_passes(self) -> None:
        errors: list[str] = []
        metric = validate_topology(topology([64] * 41 + [4] * 7), errors, "sdk5")
        self.assertEqual(errors, [])
        self.assertEqual(metric.real_meshes, 41)
        self.assertEqual(metric.drawables, 48)

    def test_empty_artmeshes_beyond_the_limit_fail(self) -> None:
        errors: list[str] = []
        validate_topology(topology([0] * 6 + [64] * 40), errors, "sdk5")
        self.assertEqual(len(errors), 1)
        self.assertIn("6 ArtMeshes have no vertices", errors[0])

    def test_the_limit_itself_is_allowed(self) -> None:
        errors: list[str] = []
        validate_topology(topology([0] * 5 + [4] * 20 + [64] * 30), errors, "sdk5")
        self.assertEqual(errors, [])

    def test_a_psd_stacked_as_static_plates_fails(self) -> None:
        errors: list[str] = []
        validate_topology(topology([4] * 21 + [64] * 30), errors, "sdk5")
        self.assertEqual(len(errors), 1)
        self.assertIn("undeformable 4-vertex plates", errors[0])

    def test_the_regressed_export_is_rejected_on_both_counts(self) -> None:
        # The shape actually found in exports/: 94 drawables, only 18 real meshes.
        errors: list[str] = []
        metric = validate_topology(topology([0] * 27 + [4] * 47 + [64] * 18, 28), errors, "sdk5")
        self.assertEqual(len(errors), 2)
        self.assertEqual(metric.real_meshes, 18)
        self.assertEqual(metric.parameters, 28)

    def test_a_moc_without_drawables_is_reported_once(self) -> None:
        errors: list[str] = []
        validate_topology(topology([]), errors, "sdk5")
        self.assertEqual(errors, ["sdk5: the MOC reports no drawables"])

    def test_metric_separates_real_meshes_from_plates(self) -> None:
        metric = topology_metric(topology([0, 4, 5, 64]))
        self.assertEqual(metric.zero_vertex_meshes, ["ArtMesh0"])
        self.assertEqual(metric.flat_meshes, ["ArtMesh1"])
        self.assertEqual(metric.real_meshes, 2)


if __name__ == "__main__":
    unittest.main()
