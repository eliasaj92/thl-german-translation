from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from corpus_common import control_tokens, stable_cell_id, structural_signature, validate_relative_path


class CorpusCommonTests(unittest.TestCase):
    def test_colored_visible_text_is_not_a_control_token(self) -> None:
        self.assertEqual(control_tokens("Use {fc(ff0000)Fatigue} now"), ("{fc(ff0000)}",))
        self.assertEqual(
            structural_signature("Use {fc(ff0000)Fatigue} now"),
            structural_signature("Nutze jetzt {fc(ff0000)Erschöpfung}"),
        )

    def test_changed_color_code_is_detected(self) -> None:
        self.assertNotEqual(
            structural_signature("{fc(ff0000)Danger}"),
            structural_signature("{fc(00ff00)Gefahr}"),
        )

    def test_line_break_count_and_kind_are_structural(self) -> None:
        self.assertNotEqual(structural_signature("one\ntwo"), structural_signature("eins zwei"))
        self.assertNotEqual(structural_signature("one\r\ntwo"), structural_signature("eins\ntwo"))

    def test_stable_cell_id_is_deterministic(self) -> None:
        value = stable_cell_id("app_text04.dx11.mvgl", "text/a.mbe/000.csv", 1, 2)
        self.assertEqual(value, stable_cell_id("app_text04.dx11.mvgl", "text/a.mbe/000.csv", 1, 2))
        self.assertEqual(len(value), 24)

    def test_parent_path_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_relative_path("../escape.csv")


if __name__ == "__main__":
    unittest.main()

