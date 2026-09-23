"""Focused tests for conservative OCR comparison (no scan or gold text needed)."""

import tempfile
import unittest
from pathlib import Path

from scripts.build_review_packet import (
    align_lines,
    alignment_key,
    build_packet,
    comparison_text,
    numbered_lines,
    ordered_review_segments,
    review_priority,
    segment_flags,
    similarity,
)


class ReviewPacketTests(unittest.TestCase):
    @staticmethod
    def fixture_root(folder: str, candidates: dict[str, str | None]) -> Path:
        root = Path(folder)
        for relative, contents in {
            "data/page-map.csv": "pdf_page,ia_leaf,printed_label\n115,115,95\n",
            "pilot/selection.csv": "pdf_page,feature\n115,ordinary text\n",
            "pilot/ground_truth/review-log.csv": "pdf_page,status\n115,in_review\n",
        }.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        for name, contents in candidates.items():
            directory = root / "pilot" / "ocr" / name
            directory.mkdir(parents=True, exist_ok=True)
            if contents is not None:
                (directory / "page-115.txt").write_text(contents, encoding="utf-8")
        return root

    def test_comparison_normalization_keeps_original_ocr_untouched(self):
        original = "Die ſchöne ﬂöte  \n"
        self.assertEqual(comparison_text(original), "die schöne flöte")
        self.assertEqual(original, "Die ſchöne ﬂöte  \n")
        self.assertEqual(alignment_key("unwürd:gen"), "unwürdgen")

    def test_standalone_punctuation_does_not_change_alignment_key(self):
        punctuated = "foo . . . . . bar"
        self.assertEqual(alignment_key(punctuated), alignment_key("foo bar"))
        self.assertEqual(similarity(punctuated, "foo bar"), 1.0)

    def test_empty_candidate_is_excluded_from_anchor_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture_root(folder, {
                "aaa-empty": " \n\t",
                "zzz-valid": "Die Musik erklingt heute\n",
                "missing": None,
            })
            packet = build_packet(115, root)
        self.assertEqual(packet["alignment_anchor"], "zzz-valid")
        self.assertEqual(packet["available_candidates"], ["zzz-valid"])
        self.assertEqual(packet["empty_candidates"], ["aaa-empty"])
        self.assertEqual(packet["unavailable_candidates"], ["missing"])
        self.assertEqual(len(packet["segments"]), 1)

    def test_all_empty_candidates_fail_clearly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture_root(folder, {
                "blank": "",
                "punctuation-only": " . . . \n",
            })
            with self.assertRaisesRegex(ValueError, "No usable OCR candidates for PDF page 115"):
                build_packet(115, root)

    def test_insertion_does_not_shift_following_matches(self):
        anchor = numbered_lines("Erste Zeile des Absatzes\nZweite Zeile des Absatzes\n")
        other = numbered_lines(
            "Erste Zeile des Absatzes\n"
            "Völlig fremder eingeschobener Text\n"
            "Zweite Zeile des Absatzes\n"
        )
        matches, unmatched = align_lines(anchor, other)
        self.assertEqual([(m.anchor_start, m.other_start) for m in matches], [(0, 0), (1, 2)])
        self.assertEqual(unmatched, [1])

    def test_merged_lines_can_align_without_same_line_number(self):
        anchor = numbered_lines("Die erste Hälfte des Satzes\nund die zweite Hälfte folgt\n")
        other = numbered_lines("Die erste Hälfte des Satzes und die zweite Hälfte folgt\n")
        matches, unmatched = align_lines(anchor, other)
        self.assertEqual(len(matches), 1)
        self.assertEqual((matches[0].anchor_end, matches[0].other_end), (2, 1))
        self.assertEqual(unmatched, [])

    def test_split_line_can_align_as_one_to_two(self):
        anchor = numbered_lines("Die erste Hälfte des Satzes und die zweite Hälfte folgt\n")
        other = numbered_lines("Die erste Hälfte des Satzes\nund die zweite Hälfte folgt\n")
        matches, unmatched = align_lines(anchor, other)
        self.assertEqual(len(matches), 1)
        self.assertEqual((matches[0].anchor_end, matches[0].other_end), (1, 2))
        self.assertEqual(unmatched, [])

    def test_unrelated_lines_are_not_forced_into_alignment(self):
        anchor = numbered_lines("Paganini spielt die Violine\n")
        other = numbered_lines("12345 <> $%^ !!!\n")
        matches, unmatched = align_lines(anchor, other)
        self.assertEqual(matches, [])
        self.assertEqual(unmatched, [0])

    def test_flags_show_disagreement_without_choosing_correct_reading(self):
        readings = {
            "model_a": {
                "text": "unwürd:gen [823 182Z ho<hbe-",
                "alignment": "anchor",
            },
            "model_b": {
                "text": "unwürdigen 1823 1823 hochbe-",
                "alignment": "aligned",
            },
        }
        agreement, flags = segment_flags(readings)
        categories = {flag["category"] for flag in flags}
        self.assertEqual(agreement, "low")
        self.assertIn("candidate_disagreement", categories)
        self.assertIn("possible_ocr_artifact", categories)
        self.assertIn("suspicious_internal_symbol", categories)
        self.assertIn("possible_digit_letter_confusion", categories)

    def test_three_close_candidates_and_one_outlier_are_medium(self):
        readings = {
            f"model_{i}": {"text": "Die Musik erklingt heute sehr schön", "alignment": "aligned"}
            for i in range(3)
        }
        readings["model_3"] = {
            "text": "Ein völlig anderer Satz steht an dieser Stelle",
            "alignment": "aligned",
        }
        self.assertEqual(review_priority(readings)[0], "medium")

    def test_small_word_typo_against_exact_consensus_is_medium(self):
        readings = {
            "a": {"text": "zahlreiche kleinliche Anekdoten von ihm", "alignment": "anchor"},
            "b": {"text": "zahlreiche kleinliche Anekdoten von ihm", "alignment": "aligned"},
            "c": {"text": "zahlreiche kleinliche Anefdoten von ihm", "alignment": "aligned"},
        }
        self.assertEqual(review_priority(readings)[0], "medium")

    def test_punctuation_only_disagreement_is_low(self):
        readings = {
            "a": {"text": "Die Musik, und der Ton.", "alignment": "anchor"},
            "b": {"text": "Die Musik; und der Ton!", "alignment": "aligned"},
        }
        self.assertEqual(review_priority(readings)[0], "low")

    def test_line_end_hyphen_only_disagreement_is_low(self):
        readings = {
            "a": {"text": "Pagani-\nni spielt Violine", "alignment": "anchor"},
            "b": {"text": "Paganini spielt Violine", "alignment": "aligned"},
        }
        self.assertEqual(review_priority(readings)[0], "low")

    def test_substantial_lexical_conflict_is_high(self):
        readings = {
            "a": {"text": "Paganini spielte ein Konzert in Paris", "alignment": "anchor"},
            "b": {"text": "Mazas schrieb mehrere Briefe aus Berlin", "alignment": "aligned"},
        }
        self.assertEqual(review_priority(readings)[0], "high")

    def test_conflicting_numbers_are_high_despite_similar_surrounding_text(self):
        readings = {
            "a": {"text": "Prag den 4. Dezember 46253, Abends 10 Uhr", "alignment": "anchor"},
            "b": {"text": "Prag den 4. Dezember 4823, Abends 10 Uhr", "alignment": "aligned"},
            "c": {"text": "Prag den 4. Dezember 1328, Abends 10 Uhr", "alignment": "aligned"},
        }
        self.assertEqual(review_priority(readings)[0], "high")

    def test_single_digit_heading_difference_is_not_automatically_high(self):
        readings = {
            "a": {"text": "1. Zur Einleitung", "alignment": "anchor"},
            "b": {"text": "2. Zur Einleitung", "alignment": "aligned"},
        }
        self.assertNotEqual(review_priority(readings)[0], "high")

    def test_same_long_number_with_different_short_marker_is_not_numeric_high(self):
        readings = {
            "a": {"text": "Im Jahre 1823 stand Anmerkung 1 hier", "alignment": "anchor"},
            "b": {"text": "Im Jahre 1823 stand Anmerkung 2 hier", "alignment": "aligned"},
        }
        self.assertNotIn("competing_numeric_readings", review_priority(readings)[1])

    def test_uncertain_noisy_candidate_is_alignment_only(self):
        readings = {
            "a": {"text": "Die Musik erklingt heute", "alignment": "anchor"},
            "b": {"text": "Die Musik erklingt heute", "alignment": "aligned"},
            "c": {"text": "Die Musik erklingt heute", "alignment": "aligned"},
            "noisy": {"text": "3u$|# 99", "alignment": "uncertain"},
        }
        self.assertEqual(review_priority(readings)[0], "alignment_only")

    def test_repeated_artifact_in_aligned_readings_is_high(self):
        readings = {
            "a": {"text": "ho<hbe- heute", "alignment": "anchor"},
            "b": {"text": "ho<hbe- heute", "alignment": "aligned"},
            "c": {"text": "hochbe heute", "alignment": "aligned"},
        }
        self.assertEqual(review_priority(readings)[0], "high")

    def test_priority_order_is_deterministic(self):
        segments = [
            {"id": "S004", "review_priority": "low"},
            {"id": "S003", "review_priority": "high"},
            {"id": "S002", "review_priority": "alignment_only"},
            {"id": "S001", "review_priority": "high"},
            {"id": "S005", "review_priority": "medium"},
        ]
        expected = ["S001", "S003", "S005", "S004", "S002"]
        self.assertEqual(
            [segment["id"] for segment in ordered_review_segments(segments)],
            expected,
        )
        self.assertEqual(
            [segment["id"] for segment in ordered_review_segments(list(reversed(segments)))],
            expected,
        )


if __name__ == "__main__":
    unittest.main()
