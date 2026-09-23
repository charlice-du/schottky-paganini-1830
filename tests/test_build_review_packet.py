"""Focused tests for conservative OCR comparison (no scan or gold text needed)."""

import unittest

from scripts.build_review_packet import (
    align_lines,
    alignment_key,
    comparison_text,
    numbered_lines,
    segment_flags,
)


class ReviewPacketTests(unittest.TestCase):
    def test_comparison_normalization_keeps_original_ocr_untouched(self):
        original = "Die ſchöne ﬂöte  \n"
        self.assertEqual(comparison_text(original), "die schöne flöte")
        self.assertEqual(original, "Die ſchöne ﬂöte  \n")
        self.assertEqual(alignment_key("unwürd:gen"), "unwürdgen")

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


if __name__ == "__main__":
    unittest.main()
