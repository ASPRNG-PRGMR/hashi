"""FED-JPEG-E001 tests.

The decisive assertion is that a prelude constructed purely from published
ISO/IEC 10918-1 Annex K tables, at quality 80 and 1280x960, reproduces the
prelude every one of the 1,903 captured records carries — byte for byte.
"""

import hashlib
import unittest

from hashi_framing import jpeg_baseline_size
from hashi_jpeg import (
    AC_CHROMA_COUNTS,
    AC_CHROMA_VALUES,
    AC_LUMA_COUNTS,
    AC_LUMA_VALUES,
    BASE_CHROMA_QTABLE,
    BASE_LUMA_QTABLE,
    DC_CHROMA_COUNTS,
    DC_CHROMA_VALUES,
    DC_LUMA_COUNTS,
    DC_LUMA_VALUES,
    OBSERVED_HEADER_LEN,
    OBSERVED_HEADER_SHA256,
    OBSERVED_PRELUDE_LEN,
    OBSERVED_QUALITY,
    ZIGZAG,
    JpegError,
    build_dht,
    build_prelude,
    build_sof0,
    parse_segments,
    scale_qtable,
)


class PreludeReproductionTests(unittest.TestCase):
    def test_constructed_prelude_matches_the_captured_header_hash(self):
        prelude = build_prelude()
        self.assertEqual(len(prelude), OBSERVED_PRELUDE_LEN)
        header = prelude[:OBSERVED_HEADER_LEN]
        self.assertEqual(hashlib.sha256(header).hexdigest(), OBSERVED_HEADER_SHA256)

    def test_segment_order_is_the_observed_one(self):
        markers = [s.marker for s in parse_segments(build_prelude())]
        self.assertEqual(
            markers,
            [0xD8, 0xE0, 0xDB, 0xDB, 0xC0, 0xC4, 0xC4, 0xC4, 0xC4, 0xDA],
        )

    def test_segment_offsets_match_the_captured_layout(self):
        offsets = [s.offset for s in parse_segments(build_prelude())]
        # Read off the captured sample: APP0 at 2, DQTs at 20 and 89, SOF0 at
        # 158, DHTs at 177/210/393/426, SOS at 609.
        self.assertEqual(offsets, [0, 2, 20, 89, 158, 177, 210, 393, 426, 609])

    def test_sof0_declares_1280x960_and_420(self):
        prelude = build_prelude()
        self.assertEqual(jpeg_baseline_size(prelude + b"\xff\xd9"), (1280, 960))
        sof = build_sof0(1280, 960)
        # precision 8, then height, width, 3 components with 0x22/0x11/0x11.
        self.assertEqual(sof[4], 8)
        self.assertEqual(sof[5:7], (960).to_bytes(2, "big"))
        self.assertEqual(sof[7:9], (1280).to_bytes(2, "big"))
        self.assertEqual(sof[9], 3)
        self.assertEqual([sof[11], sof[14], sof[17]], [0x22, 0x11, 0x11])


class QuantizationTests(unittest.TestCase):
    def test_quality_80_is_what_the_capture_used(self):
        self.assertEqual(OBSERVED_QUALITY, 80)
        luma = scale_qtable(BASE_LUMA_QTABLE, 80)
        # First eight coefficients in natural order, as observed in the capture
        # after un-zigzagging: 6, 4, 5, 6, 5, 4, 6, 6 are the first eight in
        # zig-zag order, so check the stored order instead.
        stored = [luma[ZIGZAG[i]] for i in range(8)]
        self.assertEqual(stored, [6, 4, 5, 6, 5, 4, 6, 6])

    def test_a_different_quality_does_not_reproduce_the_capture(self):
        # Guards against someone "tidying" the quality constant.
        self.assertNotEqual(
            hashlib.sha256(build_prelude(quality=79)[:OBSERVED_HEADER_LEN]).hexdigest(),
            OBSERVED_HEADER_SHA256,
        )
        self.assertNotEqual(
            hashlib.sha256(build_prelude(quality=81)[:OBSERVED_HEADER_LEN]).hexdigest(),
            OBSERVED_HEADER_SHA256,
        )

    def test_scaling_clamps_into_byte_range(self):
        for q in (1, 50, 100):
            for base in (BASE_LUMA_QTABLE, BASE_CHROMA_QTABLE):
                self.assertTrue(all(1 <= v <= 255 for v in scale_qtable(base, q)))

    def test_rejects_invalid_quality(self):
        for q in (0, 101, -1):
            with self.assertRaises(JpegError):
                scale_qtable(BASE_LUMA_QTABLE, q)

    def test_base_tables_are_sixty_four_coefficients(self):
        self.assertEqual(len(BASE_LUMA_QTABLE), 64)
        self.assertEqual(len(BASE_CHROMA_QTABLE), 64)
        self.assertEqual(sorted(ZIGZAG), list(range(64)))


class HuffmanTableTests(unittest.TestCase):
    def test_counts_are_the_published_annex_k_values(self):
        self.assertEqual(DC_LUMA_COUNTS, [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(DC_CHROMA_COUNTS, [0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
        self.assertEqual(AC_LUMA_COUNTS, [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 125])
        self.assertEqual(AC_CHROMA_COUNTS, [0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 119])

    def test_dc_tables_are_the_trivial_zero_to_eleven_values(self):
        self.assertEqual(list(DC_LUMA_VALUES), list(range(12)))
        self.assertEqual(list(DC_CHROMA_VALUES), list(range(12)))

    def test_value_counts_agree_with_the_bit_counts(self):
        for counts, values in (
            (DC_LUMA_COUNTS, DC_LUMA_VALUES),
            (DC_CHROMA_COUNTS, DC_CHROMA_VALUES),
            (AC_LUMA_COUNTS, AC_LUMA_VALUES),
            (AC_CHROMA_COUNTS, AC_CHROMA_VALUES),
        ):
            self.assertEqual(sum(counts), len(values))

    def test_ac_tables_have_the_standard_162_values(self):
        self.assertEqual(len(AC_LUMA_VALUES), 162)
        self.assertEqual(len(AC_CHROMA_VALUES), 162)

    def test_mismatched_counts_are_rejected(self):
        with self.assertRaises(JpegError):
            build_dht(0, 0, [1] + [0] * 15, (0x00, 0x01))


class SegmentParseTests(unittest.TestCase):
    def test_rejects_missing_soi(self):
        with self.assertRaises(JpegError):
            parse_segments(b"\x00\x00\xff\xda\x00\x0c")

    def test_rejects_truncated_and_unterminated(self):
        with self.assertRaises(JpegError):
            parse_segments(b"\xff\xd8\xff\xc0\x00\xff")
        with self.assertRaises(JpegError):
            parse_segments(b"\xff\xd8")  # no SOS

    def test_rejects_bad_dimensions(self):
        for w, h in ((0, 960), (1280, 0), (0x10000, 960)):
            with self.assertRaises(JpegError):
                build_sof0(w, h)


if __name__ == "__main__":
    unittest.main()
