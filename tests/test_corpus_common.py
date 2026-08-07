from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from corpus_common import control_tokens, stable_cell_id, structural_signature, validate_relative_path
from repair_fc_linebreaks import repair_value


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

    def test_parentheses_in_colored_visible_text_are_not_part_of_opcode(self) -> None:
        self.assertEqual(control_tokens("{fc(ff635b)* SNAP* (English)}"), ("{fc(ff635b)}",))

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

    def test_fc_repair_restores_source_crlf_structure(self) -> None:
        source = "{fc(ff0000)Boosted!}{fc(67ffe0)\r\n・Special Attack +1\r\n・Voltage +10%}"
        target = "{fc(ff0000)Aufgewertet!}{fc(67ffe0)\r\nSpezialattacke +1 Spannung +10%}"
        repaired = repair_value(source, target)
        self.assertEqual(structural_signature(source), structural_signature(repaired))
        self.assertIn("\r\nSpezialattacke +1\r\nSpannung +10%", repaired)


if __name__ == "__main__":
    unittest.main()
