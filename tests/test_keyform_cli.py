from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from pipeline.keyform import cli
from tests import keyform_fixtures as fx
from tests.test_keyform_transfer import SOURCE_CENTRE, source_eye, target_eye


def run(argv: list[str]) -> tuple[int, str, str]:
    """Run the command line and capture what it printed."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class KeyformCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="keyform-cli-"))
        self.addCleanup(self._clean)

    def _clean(self) -> None:
        for path in sorted(self.root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        self.root.rmdir()

    def write(self, name: str, document: dict[str, Any]) -> Path:
        """Write one fixture document into the temporary directory."""
        path = self.root / name
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path

    def documents(self, **overrides: Any) -> tuple[Path, Path, Path]:
        """Write a working source, target and mapping."""
        source = self.write(
            "source.json", overrides.get("source", fx.manifest("source", [source_eye()]))
        )
        target = self.write(
            "target.json", overrides.get("target", fx.manifest("target", [target_eye()]))
        )
        mapping = self.write(
            "map.json", overrides.get("map", fx.mesh_map([("MugiEyeL", "HiyoriEyeL")]))
        )
        return source, target, mapping

    def test_validate_accepts_a_well_formed_manifest(self) -> None:
        source, _, _ = self.documents()
        code, out, _ = run(["validate", str(source)])
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["artmesh_count"], 1)
        self.assertEqual(report["keyform_count"], 2)
        self.assertEqual(report["meshes"][0]["reference_key"], f"{fx.EYE_OPEN}=1.000000")

    def test_validate_reports_a_mesh_with_no_reference_form(self) -> None:
        broken = fx.manifest(
            "source",
            [fx.mesh("HiyoriEyeL", [({fx.EYE_OPEN: 0.0}, fx.quad(*SOURCE_CENTRE, 40.0))])],
        )
        path = self.write("broken.json", broken)
        code, out, _ = run(["validate", str(path)])
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["problems"][0]["code"], "reference_form")

    def test_a_malformed_manifest_exits_two_without_a_traceback(self) -> None:
        path = self.write("bad.json", {"schema": "something-else"})
        code, out, err = run(["validate", str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ManifestError", err)

    def test_plan_writes_a_ready_document(self) -> None:
        source, target, mapping = self.documents()
        out_path = self.root / "plan.json"
        code, out, _ = run(
            ["plan", "--source", str(source), "--target", str(target),
             "--map", str(mapping), "--out", str(out_path)]
        )
        self.assertEqual(code, 0)
        document = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(document["status"], "ready")
        self.assertEqual(document["summary"]["planned_forms"], 2)
        self.assertEqual(json.loads(out)["status"], "ready")
        self.assertEqual(
            document["generated_from"]["source"]["path"],
            str(source).replace("\\", "/"),
        )
        self.assertEqual(len(document["generated_from"]["map"]["sha256"]), 64)

    def test_plan_exits_one_when_the_mapping_is_incomplete(self) -> None:
        source, target, mapping = self.documents(
            target=fx.manifest(
                "target", [target_eye(), fx.eye_mesh("MugiMouth", (1300.0, 1000.0), 15.0)]
            )
        )
        out_path = self.root / "plan.json"
        code, _, _ = run(
            ["plan", "--source", str(source), "--target", str(target),
             "--map", str(mapping), "--out", str(out_path)]
        )
        self.assertEqual(code, 1)
        document = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(document["status"], "rejected")
        self.assertEqual(document["diagnostics"][0]["code"], "unmapped_target")

    def test_plan_is_byte_identical_when_rerun(self) -> None:
        source, target, mapping = self.documents()
        first, second = self.root / "a.json", self.root / "b.json"
        for out_path in (first, second):
            run(["plan", "--source", str(source), "--target", str(target),
                 "--map", str(mapping), "--out", str(out_path)])
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_plan_honours_the_displacement_ceiling(self) -> None:
        source, target, mapping = self.documents()
        out_path = self.root / "plan.json"
        code, _, _ = run(
            ["plan", "--source", str(source), "--target", str(target), "--map", str(mapping),
             "--max-displacement", "5", "--out", str(out_path)]
        )
        self.assertEqual(code, 1)
        document = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(document["diagnostics"][0]["code"], "displacement_over_limit")

    def test_verify_accepts_the_exact_planned_output(self) -> None:
        source, target, mapping = self.documents()
        plan_path = self.root / "plan.json"
        run(["plan", "--source", str(source), "--target", str(target),
             "--map", str(mapping), "--out", str(plan_path)])
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        applied = json.loads(target.read_text(encoding="utf-8"))
        applied["meshes"][0]["forms"] = [
            {"coordinate": form["coordinate"], "vertices": form["vertices"]}
            for form in plan["meshes"][0]["forms"]
        ]
        actual = self.write("actual.json", applied)
        code, out, _ = run(["verify", "--plan", str(plan_path), "--actual", str(actual)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "ready")

    def test_verify_rejects_one_changed_vertex(self) -> None:
        source, target, mapping = self.documents()
        plan_path = self.root / "plan.json"
        run(["plan", "--source", str(source), "--target", str(target),
             "--map", str(mapping), "--out", str(plan_path)])
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        applied = json.loads(target.read_text(encoding="utf-8"))
        applied["meshes"][0]["forms"] = [
            {"coordinate": form["coordinate"], "vertices": form["vertices"]}
            for form in plan["meshes"][0]["forms"]
        ]
        applied["meshes"][0]["forms"][0]["vertices"][0][0] += 0.01
        actual = self.write("actual.json", applied)
        code, out, _ = run(["verify", "--plan", str(plan_path), "--actual", str(actual)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["problems"][0]["code"], "vertices_mismatch")

    def test_draft_map_pairs_only_unambiguous_topology(self) -> None:
        source = self.write(
            "source.json",
            fx.manifest(
                "source",
                [
                    source_eye(),
                    fx.eye_mesh("HiyoriEyeR", (500.0, 300.0), 40.0),
                    fx.mesh(
                        "HiyoriMouth",
                        [
                            ({fx.EYE_OPEN: 0.0}, [[0.0, 0.0], [9.0, 0.0], [4.0, 9.0]]),
                            ({fx.EYE_OPEN: 1.0}, [[0.0, 0.0], [9.0, 0.0], [4.0, 9.0]]),
                        ],
                        triangles=[[0, 1, 2]],
                    ),
                ],
            ),
        )
        target = self.write(
            "target.json",
            fx.manifest(
                "target",
                [
                    target_eye(),
                    fx.mesh(
                        "MugiMouth",
                        [
                            ({fx.EYE_OPEN: 0.0}, [[1.0, 1.0], [5.0, 1.0], [3.0, 6.0]]),
                            ({fx.EYE_OPEN: 1.0}, [[1.0, 1.0], [5.0, 1.0], [3.0, 6.0]]),
                        ],
                        triangles=[[0, 1, 2]],
                    ),
                ],
            ),
        )
        code, out, _ = run(["draft-map", "--source", str(source), "--target", str(target)])
        draft = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(draft["pairs"], [
            {
                "target": "MugiMouth",
                "source": "HiyoriMouth",
                "note": "one source mesh shares this topology; confirm it is the same part",
            }
        ])
        self.assertEqual(draft["unassigned"][0]["target"], "MugiEyeL")
        self.assertEqual(
            sorted(draft["unassigned"][0]["candidates"]), ["HiyoriEyeL", "HiyoriEyeR"]
        )

    def test_a_draft_is_still_rejected_until_a_human_finishes_it(self) -> None:
        source, target, _ = self.documents()
        draft_path = self.root / "draft.json"
        run(["draft-map", "--source", str(source), "--target", str(target),
             "--out", str(draft_path)])
        plan_path = self.root / "plan.json"
        code, _, _ = run(
            ["plan", "--source", str(source), "--target", str(target),
             "--map", str(draft_path), "--out", str(plan_path)]
        )
        self.assertEqual(code, 0)  # a single unambiguous pair is complete on its own

        crowded = self.write(
            "crowded.json",
            fx.manifest(
                "target",
                [target_eye(), fx.eye_mesh("MugiEyeR", (1400.0, 900.0), 20.0)],
            ),
        )
        run(["draft-map", "--source", str(source), "--target", str(crowded),
             "--out", str(draft_path)])
        code, _, _ = run(
            ["plan", "--source", str(source), "--target", str(crowded),
             "--map", str(draft_path), "--out", str(plan_path)]
        )
        self.assertEqual(code, 1)
        document = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertIn("unmapped_target", [item["code"] for item in document["diagnostics"]])

    def test_a_malformed_mapping_exits_two(self) -> None:
        source, target, _ = self.documents()
        mapping = self.write("map.json", {"schema": "mugi-live2d/keyform-map@9"})
        code, _, err = run(
            ["plan", "--source", str(source), "--target", str(target), "--map", str(mapping)]
        )
        self.assertEqual(code, 2)
        self.assertIn("MeshMapError", err)


if __name__ == "__main__":
    unittest.main()
