from __future__ import annotations

import unittest

from pipeline.keyform import manifest as mf
from tests import keyform_fixtures as fx


def _one_mesh(**extra: object) -> dict:
    return fx.manifest("target", [fx.eye_mesh("EyeL", (100.0, 100.0), 20.0, **extra)])


class ManifestTest(unittest.TestCase):
    def test_reference_form_is_found_by_parameter_default_not_by_position(self) -> None:
        document = mf.parse(_one_mesh())
        mesh = document.meshes[0]
        self.assertEqual(mesh.forms[0].coordinate, ((fx.EYE_OPEN, 0.0),))
        reference = document.reference_form(mesh)
        self.assertEqual(reference.coordinate, ((fx.EYE_OPEN, 1.0),))
        self.assertIs(reference, mesh.forms[1])

    def test_a_mesh_without_parameters_uses_its_single_form(self) -> None:
        document = mf.parse(
            fx.manifest(
                "target",
                [fx.mesh("Body", [({}, fx.quad(0.0, 0.0, 5.0))], parameters=())],
            )
        )
        mesh = document.meshes[0]
        self.assertEqual(document.reference_key(mesh), "")
        self.assertEqual(document.reference_form(mesh), mesh.forms[0])

    def test_a_mesh_with_no_form_at_the_defaults_is_refused(self) -> None:
        document = mf.parse(
            fx.manifest(
                "target",
                [fx.mesh("EyeL", [({fx.EYE_OPEN: 0.0}, fx.quad(0.0, 0.0, 5.0))])],
            )
        )
        with self.assertRaises(mf.ReferenceFormError) as caught:
            document.reference_form(document.meshes[0])
        self.assertIn("no keyform sits at the parameter defaults", str(caught.exception))

    def test_two_forms_claiming_the_defaults_are_refused(self) -> None:
        document = mf.parse(_one_mesh())
        reference = document.reference_form(document.meshes[0])
        ambiguous = mf.Mesh(
            id="EyeL",
            name="EyeL",
            vertex_count=len(reference.vertices),
            parameters=(fx.EYE_OPEN,),
            forms=(reference, reference),
            triangles=document.meshes[0].triangles,
        )
        with self.assertRaises(mf.ReferenceFormError) as caught:
            document.reference_form(ambiguous)
        self.assertIn("2 keyforms claim the parameter defaults", str(caught.exception))

    def test_the_loader_refuses_two_forms_at_the_same_coordinate(self) -> None:
        document = _one_mesh()
        forms = document["meshes"][0]["forms"]
        forms.append(dict(forms[1]))
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(document)
        self.assertIn("must identify exactly one form", str(caught.exception))

    def test_an_unsupported_schema_is_refused(self) -> None:
        document = _one_mesh() | {"schema": "mugi-live2d/keyform-manifest@99"}
        with self.assertRaises(mf.ManifestError):
            mf.parse(document)

    def test_duplicate_artmesh_ids_are_refused(self) -> None:
        document = fx.manifest(
            "target",
            [
                fx.eye_mesh("EyeL", (100.0, 100.0), 20.0),
                fx.eye_mesh("EyeL", (200.0, 100.0), 20.0),
            ],
        )
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(document)
        self.assertIn("duplicate ArtMesh id", str(caught.exception))

    def test_a_form_that_disagrees_with_the_declared_vertex_count_is_refused(self) -> None:
        document = _one_mesh()
        document["meshes"][0]["forms"][0]["vertices"].pop()
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(document)
        self.assertIn("3 vertices but the mesh declares 4", str(caught.exception))

    def test_non_finite_coordinates_are_refused(self) -> None:
        for bad in (float("nan"), float("inf")):
            with self.subTest(value=bad):
                document = _one_mesh()
                document["meshes"][0]["forms"][1]["vertices"][2][0] = bad
                with self.assertRaises(mf.ManifestError) as caught:
                    mf.parse(document)
                self.assertIn("must be finite", str(caught.exception))

    def test_a_coordinate_that_does_not_match_the_mesh_parameters_is_refused(self) -> None:
        document = _one_mesh()
        document["meshes"][0]["forms"][0]["coordinate"] = {"ParamMouthOpenY": 0.0}
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(document)
        self.assertIn("do not match", str(caught.exception))

    def test_a_keyform_outside_the_parameter_range_is_refused(self) -> None:
        document = _one_mesh()
        document["meshes"][0]["forms"][0]["coordinate"][fx.EYE_OPEN] = 4.0
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(document)
        self.assertIn("outside", str(caught.exception))

    def test_a_default_outside_its_own_range_is_refused(self) -> None:
        document = fx.manifest(
            "target",
            [fx.eye_mesh("EyeL", (0.0, 0.0), 5.0)],
            parameters=[fx.parameter(minimum=0.0, maximum=1.0, default=7.0)],
        )
        with self.assertRaises(mf.ManifestError):
            mf.parse(document)

    def test_triangles_are_required_and_checked(self) -> None:
        without = _one_mesh()
        del without["meshes"][0]["triangles"]
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(without)
        self.assertIn("triangles are required", str(caught.exception))

        out_of_range = _one_mesh()
        out_of_range["meshes"][0]["triangles"][0] = [0, 1, 9]
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(out_of_range)
        self.assertIn("index out of range", str(caught.exception))

        degenerate = _one_mesh()
        degenerate["meshes"][0]["triangles"][0] = [0, 1, 1]
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(degenerate)
        self.assertIn("three distinct corners", str(caught.exception))

    def test_uvs_must_cover_every_vertex(self) -> None:
        document = _one_mesh(uvs=[[0.0, 0.0], [1.0, 0.0]])
        with self.assertRaises(mf.ManifestError) as caught:
            mf.parse(document)
        self.assertIn("2 uvs but the mesh declares 4", str(caught.exception))

    def test_an_undeclared_role_is_refused(self) -> None:
        document = _one_mesh()
        document["model"]["role"] = "reference"
        with self.assertRaises(mf.ManifestError):
            mf.parse(document)

    def test_coordinate_keys_ignore_ordering_and_signed_zero(self) -> None:
        self.assertEqual(
            mf.coordinate_key([("B", 1.0), ("A", -0.0)]),
            mf.coordinate_key([("A", 0.0), ("B", 1.0)]),
        )

    def test_invariant_digest_covers_what_a_transfer_must_not_change(self) -> None:
        base = mf.parse(
            _one_mesh(uvs=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], draw_order=500,
                      clipped_by=["EyeLMask"], opacity=1.0)
        ).meshes[0]
        same = mf.parse(
            _one_mesh(uvs=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], draw_order=500,
                      clipped_by=["EyeLMask"], opacity=1.0)
        ).meshes[0]
        self.assertEqual(mf.invariant_digest(base), mf.invariant_digest(same))

        for change in (
            {"uvs": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]], "draw_order": 500,
             "clipped_by": ["EyeLMask"], "opacity": 1.0},
            {"uvs": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "draw_order": 501,
             "clipped_by": ["EyeLMask"], "opacity": 1.0},
            {"uvs": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "draw_order": 500,
             "clipped_by": [], "opacity": 1.0},
            {"uvs": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "draw_order": 500,
             "clipped_by": ["EyeLMask"], "opacity": 0.5},
        ):
            with self.subTest(change=sorted(change)):
                other = mf.parse(_one_mesh(**change)).meshes[0]
                self.assertNotEqual(mf.invariant_digest(base), mf.invariant_digest(other))

    def test_invariant_digest_ignores_the_keyforms_themselves(self) -> None:
        moved = _one_mesh()
        moved["meshes"][0]["forms"][0]["vertices"][0][0] += 3.0
        self.assertEqual(
            mf.invariant_digest(mf.parse(_one_mesh()).meshes[0]),
            mf.invariant_digest(mf.parse(moved).meshes[0]),
        )


if __name__ == "__main__":
    unittest.main()
