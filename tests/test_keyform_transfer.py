from __future__ import annotations

import json
import unittest
from typing import Any

from pipeline.keyform import manifest as mf
from pipeline.keyform import meshmap as mm
from pipeline.keyform import transfer
from tests import keyform_fixtures as fx

OPEN_KEY = f"{fx.EYE_OPEN}=1.000000"
SHUT_KEY = f"{fx.EYE_OPEN}=0.000000"

SOURCE_CENTRE = (400.0, 300.0)
TARGET_CENTRE = (1300.0, 900.0)


def source_eye(**extra: Any) -> dict[str, Any]:
    """A source eye far from the target, twice its size."""
    return fx.eye_mesh("HiyoriEyeL", SOURCE_CENTRE, 40.0, **extra)


def target_eye(**extra: Any) -> dict[str, Any]:
    """The target eye, with its own base shape."""
    return fx.eye_mesh("MugiEyeL", TARGET_CENTRE, 20.0, **extra)


def make_plan(
    source_meshes: list[dict[str, Any]],
    target_meshes: list[dict[str, Any]],
    mapping: dict[str, Any] | None = None,
    *,
    source_parameters: list[dict[str, Any]] | None = None,
    target_parameters: list[dict[str, Any]] | None = None,
    **options: Any,
) -> dict[str, Any]:
    """Plan a transfer from plain fixture documents."""
    return transfer.plan(
        mf.parse(fx.manifest("source", source_meshes, parameters=source_parameters)),
        mf.parse(fx.manifest("target", target_meshes, parameters=target_parameters)),
        mm.parse(mapping or fx.mesh_map([("MugiEyeL", "HiyoriEyeL")])),
        **options,
    )


def entry_for(document: dict[str, Any], target: str) -> dict[str, Any]:
    """Return the planned entry for one target mesh."""
    return next(item for item in document["meshes"] if item["target"] == target)


def form_at(entry: dict[str, Any], key: str) -> dict[str, Any]:
    """Return one planned keyform by coordinate key."""
    return next(item for item in entry["forms"] if item["key"] == key)


def codes(document: dict[str, Any]) -> list[str]:
    """Return the diagnostic codes a plan reported."""
    return [item["code"] for item in document["diagnostics"]]


class TransferTest(unittest.TestCase):
    def test_a_clean_pair_produces_a_ready_plan(self) -> None:
        document = make_plan([source_eye()], [target_eye()])
        self.assertEqual(document["status"], "ready")
        self.assertEqual(document["diagnostics"], [])
        self.assertEqual(document["summary"]["planned_meshes"], 1)
        self.assertEqual(document["summary"]["planned_forms"], 2)

    def test_the_reference_form_reproduces_the_target_base_geometry_exactly(self) -> None:
        document = make_plan([source_eye()], [target_eye()])
        reference = form_at(entry_for(document, "MugiEyeL"), OPEN_KEY)
        self.assertTrue(reference["is_reference"])
        self.assertEqual(reference["vertices"], fx.quad(*TARGET_CENTRE, 20.0))
        self.assertEqual(reference["displacement"]["max_px"], 0.0)

    def test_a_transferred_form_is_the_targets_own_shape_deformed(self) -> None:
        document = make_plan([source_eye()], [target_eye()])
        shut = form_at(entry_for(document, "MugiEyeL"), SHUT_KEY)
        expected = [[x, TARGET_CENTRE[1]] for x, _ in fx.quad(*TARGET_CENTRE, 20.0)]
        for planned, wanted in zip(shut["vertices"], expected):
            self.assertAlmostEqual(planned[0], wanted[0], places=9)
            self.assertAlmostEqual(planned[1], wanted[1], places=9)
        self.assertAlmostEqual(shut["displacement"]["max_px"], 20.0, places=9)

    def test_no_source_coordinate_reaches_the_output(self) -> None:
        """The failure this pipeline exists to prevent: Hiyori's absolute positions."""
        document = make_plan([source_eye()], [target_eye()])
        for form in entry_for(document, "MugiEyeL")["forms"]:
            for x, y in form["vertices"]:
                self.assertLess(abs(x - TARGET_CENTRE[0]), 40.0)
                self.assertLess(abs(y - TARGET_CENTRE[1]), 40.0)

    def test_translating_the_whole_source_model_changes_nothing(self) -> None:
        moved = fx.eye_mesh(
            "HiyoriEyeL",
            (SOURCE_CENTRE[0] + 777.0, SOURCE_CENTRE[1] - 333.0),
            40.0,
        )
        self.assertPlansAgree(make_plan([source_eye()], [target_eye()]),
                              make_plan([moved], [target_eye()]))

    def test_scaling_the_whole_source_model_changes_nothing(self) -> None:
        base = source_eye()
        scaled = fx.mesh(
            "HiyoriEyeL",
            [
                (form["coordinate"], fx.scaled(form["vertices"], 7.0))
                for form in base["forms"]
            ],
        )
        self.assertPlansAgree(make_plan([base], [target_eye()]),
                              make_plan([scaled], [target_eye()]))

    def test_rotating_the_whole_source_model_changes_nothing(self) -> None:
        base = source_eye()
        turned = fx.mesh(
            "HiyoriEyeL",
            [
                (form["coordinate"], fx.rotated(form["vertices"], 37.0, SOURCE_CENTRE))
                for form in base["forms"]
            ],
        )
        self.assertPlansAgree(make_plan([base], [target_eye()]),
                              make_plan([turned], [target_eye()]))

    def test_an_asymmetric_deformation_stays_asymmetric(self) -> None:
        base = fx.quad(*SOURCE_CENTRE, 40.0)
        nudged = [list(vertex) for vertex in base]
        nudged[1] = [base[1][0] + 12.0, base[1][1] - 8.0]
        source = fx.mesh(
            "HiyoriEyeL",
            [({fx.EYE_OPEN: 0.0}, nudged), ({fx.EYE_OPEN: 1.0}, base)],
        )
        document = make_plan([source], [target_eye()])
        moved = form_at(entry_for(document, "MugiEyeL"), SHUT_KEY)["vertices"]
        anchor = fx.quad(*TARGET_CENTRE, 20.0)
        for index in (0, 2, 3):
            self.assertAlmostEqual(moved[index][0], anchor[index][0], places=9)
            self.assertAlmostEqual(moved[index][1], anchor[index][1], places=9)
        self.assertAlmostEqual(moved[1][0], anchor[1][0] + 6.0, places=9)
        self.assertAlmostEqual(moved[1][1], anchor[1][1] - 4.0, places=9)

    def test_a_zero_size_source_mesh_is_rejected(self) -> None:
        flat = [[7.0, 7.0]] * 4
        source = fx.mesh(
            "HiyoriEyeL", [({fx.EYE_OPEN: 0.0}, flat), ({fx.EYE_OPEN: 1.0}, flat)]
        )
        document = make_plan([source], [target_eye()])
        self.assertEqual(document["status"], "rejected")
        self.assertEqual(codes(document), ["degenerate_frame"])
        self.assertEqual(document["meshes"], [])

    def test_a_zero_size_target_mesh_is_rejected(self) -> None:
        flat = [[3.0, 4.0]] * 4
        target = fx.mesh(
            "MugiEyeL", [({fx.EYE_OPEN: 0.0}, flat), ({fx.EYE_OPEN: 1.0}, flat)]
        )
        document = make_plan([source_eye()], [target])
        self.assertEqual(codes(document), ["degenerate_frame"])

    def test_a_mismatched_vertex_count_is_rejected(self) -> None:
        source = fx.mesh(
            "HiyoriEyeL",
            [
                ({fx.EYE_OPEN: 0.0}, [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]),
                ({fx.EYE_OPEN: 1.0}, [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]),
            ],
            triangles=[[0, 1, 2]],
        )
        document = make_plan([source], [target_eye()])
        self.assertEqual(codes(document), ["vertex_count_mismatch"])
        self.assertIn("3 vertices", document["diagnostics"][0]["message"])

    def test_a_mismatched_triangle_list_is_rejected(self) -> None:
        document = make_plan(
            [source_eye(triangles=[[0, 1, 2], [1, 2, 3]])],
            [target_eye(triangles=[[0, 1, 2], [0, 2, 3]])],
        )
        self.assertEqual(codes(document), ["topology_mismatch"])

    def test_an_unmapped_target_is_rejected(self) -> None:
        document = make_plan(
            [source_eye()],
            [target_eye(), fx.eye_mesh("MugiMouth", (1300.0, 1000.0), 15.0)],
        )
        self.assertEqual(codes(document), ["unmapped_target"])
        self.assertEqual(document["diagnostics"][0]["scope"], "MugiMouth")

    def test_excluded_targets_are_recorded_and_left_alone(self) -> None:
        document = make_plan(
            [source_eye()],
            [target_eye(), fx.eye_mesh("MugiAccessory", (1600.0, 400.0), 30.0)],
            fx.mesh_map(
                [("MugiEyeL", "HiyoriEyeL")],
                excluded=[("MugiAccessory", "Mugi-only prop; the source rig has no counterpart")],
            ),
        )
        self.assertEqual(document["status"], "ready")
        self.assertEqual([item["target"] for item in document["excluded"]], ["MugiAccessory"])
        self.assertEqual([item["target"] for item in document["meshes"]], ["MugiEyeL"])
        self.assertEqual(document["summary"]["excluded"], 1)

    def test_an_exclusion_without_a_reason_is_refused(self) -> None:
        with self.assertRaises(mm.MeshMapError):
            mm.parse(fx.mesh_map([], excluded=[("MugiAccessory", "")]))

    def test_a_target_named_by_the_map_but_missing_from_the_model_is_rejected(self) -> None:
        document = make_plan(
            [source_eye(), fx.eye_mesh("HiyoriEyeR", (500.0, 300.0), 40.0)],
            [target_eye()],
            fx.mesh_map([("MugiEyeL", "HiyoriEyeL"), ("MugiGhost", "HiyoriEyeR")]),
        )
        self.assertEqual(codes(document), ["unknown_target"])

    def test_a_source_named_by_the_map_but_missing_from_the_model_is_rejected(self) -> None:
        document = make_plan(
            [source_eye()],
            [target_eye()],
            fx.mesh_map([("MugiEyeL", "HiyoriGhost")]),
        )
        self.assertEqual(codes(document), ["unknown_source"])

    def test_a_mesh_with_no_reference_form_is_rejected(self) -> None:
        source = fx.mesh("HiyoriEyeL", [({fx.EYE_OPEN: 0.0}, fx.quad(*SOURCE_CENTRE, 40.0))])
        document = make_plan([source], [target_eye()])
        self.assertEqual(codes(document), ["reference_form"])
        self.assertIn(
            "no keyform sits at the parameter defaults", document["diagnostics"][0]["message"]
        )

    def test_a_parameter_the_target_model_lacks_is_rejected(self) -> None:
        document = make_plan(
            [source_eye()],
            [fx.mesh("MugiEyeL", [({}, fx.quad(*TARGET_CENTRE, 20.0))], parameters=())],
            target_parameters=[fx.parameter("ParamMouthOpenY", 0.0, 1.0, 0.0)],
        )
        self.assertIn("unknown_target_parameter", codes(document))

    def test_a_parameter_that_rests_at_a_different_default_is_rejected(self) -> None:
        document = make_plan(
            [source_eye()],
            [
                fx.mesh(
                    "MugiEyeL",
                    [
                        ({fx.EYE_OPEN: 0.0}, fx.quad(*TARGET_CENTRE, 20.0)),
                        ({fx.EYE_OPEN: 1.0}, fx.quad(*TARGET_CENTRE, 20.0)),
                    ],
                )
            ],
            target_parameters=[fx.parameter(default=0.0)],
        )
        self.assertIn("default_mismatch", codes(document))

    def test_a_keyform_outside_the_target_parameter_range_is_rejected(self) -> None:
        source = fx.mesh(
            "HiyoriEyeL",
            [
                ({fx.EYE_OPEN: 2.0}, fx.quad(*SOURCE_CENTRE, 44.0)),
                ({fx.EYE_OPEN: 1.0}, fx.quad(*SOURCE_CENTRE, 40.0)),
            ],
        )
        document = make_plan(
            [source],
            [target_eye()],
            source_parameters=[fx.parameter(minimum=0.0, maximum=2.0, default=1.0)],
        )
        self.assertEqual(codes(document), ["parameter_range"])

    def test_the_displacement_ceiling_catches_motion_that_is_too_large(self) -> None:
        document = make_plan([source_eye()], [target_eye()], max_displacement=5.0)
        self.assertEqual(codes(document), ["displacement_over_limit"])
        self.assertIn("absolute-coordinate copy", document["diagnostics"][0]["message"])

    def test_the_ceiling_can_come_from_the_reviewed_mapping(self) -> None:
        mapping = fx.mesh_map(
            [("MugiEyeL", "HiyoriEyeL")], limits={"max_displacement_px": 5.0}
        )
        document = make_plan([source_eye()], [target_eye()], mapping)
        self.assertEqual(codes(document), ["displacement_over_limit"])
        self.assertEqual(document["policy"]["max_displacement_px"], 5.0)

    def test_a_generous_ceiling_lets_the_same_plan_through(self) -> None:
        document = make_plan([source_eye()], [target_eye()], max_displacement=25.0)
        self.assertEqual(document["status"], "ready")

    def test_manifests_used_in_the_wrong_role_are_rejected(self) -> None:
        document = transfer.plan(
            mf.parse(fx.manifest("target", [source_eye()])),
            mf.parse(fx.manifest("target", [target_eye()])),
            mm.parse(fx.mesh_map([("MugiEyeL", "HiyoriEyeL")])),
        )
        self.assertIn("role_mismatch", codes(document))

    def test_the_plan_records_the_target_invariants_and_touches_none_of_them(self) -> None:
        target = target_eye(
            uvs=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            draw_order=520,
            clipped_by=["MugiEyeLMask"],
            opacity=1.0,
        )
        model = mf.parse(fx.manifest("target", [target]))
        document = make_plan([source_eye()], [target])
        self.assertEqual(document["target_invariants"]["artmesh_count"], 1)
        self.assertEqual(
            document["target_invariants"]["meshes"]["MugiEyeL"],
            mf.invariant_digest(model.meshes[0]),
        )
        for form in entry_for(document, "MugiEyeL")["forms"]:
            self.assertEqual(set(form) & {"uvs", "triangles", "opacity", "draw_order"}, set())
        self.assertIn("texture_uv", document["policy"]["preserved"])

    def test_forms_the_target_already_has_are_marked_for_replacement(self) -> None:
        document = make_plan([source_eye()], [target_eye()])
        entry = entry_for(document, "MugiEyeL")
        self.assertEqual({form["action"] for form in entry["forms"]}, {"replace"})

        bare = fx.mesh("MugiEyeL", [({fx.EYE_OPEN: 1.0}, fx.quad(*TARGET_CENTRE, 20.0))])
        document = make_plan([source_eye()], [bare])
        actions = {form["key"]: form["action"] for form in entry_for(document, "MugiEyeL")["forms"]}
        self.assertEqual(actions, {OPEN_KEY: "replace", SHUT_KEY: "create"})

    def test_the_same_inputs_always_give_the_same_plan(self) -> None:
        first = make_plan([source_eye()], [target_eye()])
        second = make_plan([source_eye()], [target_eye()])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_a_pair_can_ask_for_an_affine_frame(self) -> None:
        stretched = fx.mesh(
            "MugiEyeL",
            [
                ({fx.EYE_OPEN: 0.0}, [[x, TARGET_CENTRE[1]] for x, _ in
                                      fx.quad(*TARGET_CENTRE, 20.0)]),
                ({fx.EYE_OPEN: 1.0}, [[TARGET_CENTRE[0] + (x - TARGET_CENTRE[0]) * 2.0, y]
                                      for x, y in fx.quad(*TARGET_CENTRE, 20.0)]),
            ],
        )
        mapping = fx.mesh_map([("MugiEyeL", "HiyoriEyeL")])
        mapping["pairs"][0]["frame"] = "affine"
        document = make_plan([source_eye()], [stretched], mapping)
        entry = entry_for(document, "MugiEyeL")
        self.assertEqual(entry["frame"]["mode"], "affine")
        self.assertLess(entry["frame"]["residual_rms_px"], 1e-9)

    def test_the_command_line_frame_override_leaves_reviewed_pairs_alone(self) -> None:
        mapping = fx.mesh_map([("MugiEyeL", "HiyoriEyeL")])
        mapping["pairs"][0]["frame"] = "similarity"
        document = make_plan([source_eye()], [target_eye()], mapping, frame_mode="affine")
        self.assertEqual(entry_for(document, "MugiEyeL")["frame"]["mode"], "similarity")
        self.assertEqual(document["policy"]["frame"], "affine")

    def test_one_source_mesh_cannot_drive_two_targets(self) -> None:
        with self.assertRaises(mm.MeshMapError) as caught:
            mm.parse(fx.mesh_map([("MugiEyeL", "HiyoriEyeL"), ("MugiEyeR", "HiyoriEyeL")]))
        self.assertIn("cannot be two parts", str(caught.exception))

    def test_a_target_cannot_be_mapped_and_excluded_at_once(self) -> None:
        with self.assertRaises(mm.MeshMapError):
            mm.parse(
                fx.mesh_map(
                    [("MugiEyeL", "HiyoriEyeL")],
                    excluded=[("MugiEyeL", "changed my mind")],
                )
            )

    def assertPlansAgree(self, first: dict[str, Any], second: dict[str, Any]) -> None:
        """Assert two plans place every vertex in the same place."""
        self.assertEqual(first["status"], "ready")
        self.assertEqual(second["status"], "ready")
        self.assertEqual(len(first["meshes"]), len(second["meshes"]))
        for left, right in zip(first["meshes"], second["meshes"]):
            self.assertEqual(left["target"], right["target"])
            for one, other in zip(left["forms"], right["forms"]):
                self.assertEqual(one["key"], other["key"])
                for a, b in zip(one["vertices"], other["vertices"]):
                    self.assertAlmostEqual(a[0], b[0], places=6)
                    self.assertAlmostEqual(a[1], b[1], places=6)


if __name__ == "__main__":
    unittest.main()
