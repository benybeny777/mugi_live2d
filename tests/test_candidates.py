from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.fixedtopo import calibrate, candidates
from tests.synthetic import draw


class CandidateTest(unittest.TestCase):
    def test_three_profiles_are_repeatable_and_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            draw().save(source)
            spec = Path("pipeline/contract-spec.mugi-hiyori-v2.json")
            palette = Path("pipeline/palette.mugi.json")
            contract_path = root / "contract.json"
            contract_path.write_text(
                __import__("json").dumps(calibrate.calibrate(spec, source, palette)),
                encoding="utf-8",
            )
            first = candidates.generate(source, contract_path, palette, root / "first")
            second = candidates.generate(source, contract_path, palette, root / "second")
            first_hashes = [entry["sha256"] for entry in first["candidates"]]
            second_hashes = [entry["sha256"] for entry in second["candidates"]]
            self.assertEqual(first_hashes, second_hashes)
            self.assertEqual(3, len(set(first_hashes)))


if __name__ == "__main__":
    unittest.main()
