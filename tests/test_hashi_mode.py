"""Tests for FED-MODE-E001 rules, using the actually observed values as fixtures."""

import unittest

from hashi_mode import (
    CUSTOMIZE_RESOLUTION_PIXEL_LIMIT,
    ModeError,
    MonitorRecord,
    best_resolution_score,
    customize_resolution_would_apply,
    monitor_extent,
    select_best_resolution,
    select_monitor_dimensions,
)

# The ten modes \\.\DISPLAY7 (LuminonCore IDDCX Adapter) enumerated in both
# captured snapshots, in enumeration order.
LCI_MODES = [
    (800, 600), (1024, 768), (1280, 720), (1280, 800), (1280, 960),
    (1400, 1050), (1440, 900), (1600, 900), (1600, 1200), (1920, 1080),
]

# Monitor rectangles from the post-reconnect snapshot, in EnumDisplayMonitors order.
OBSERVED_MONITORS = [
    MonitorRecord(0, 0, 1536, 960, r"\\.\DISPLAY1"),
    MonitorRecord(1920, 0, 3200, 960, r"\\.\DISPLAY7"),
]


class MonitorExtentTests(unittest.TestCase):
    def test_observed_lci_rectangle_gives_observed_encoder_size(self):
        # rcMonitor [1920,0,3200,960] is what WIN-BACKEND-E004 recorded, and
        # 1280x960 is what ordinary JPEG initialization actually received.
        self.assertEqual(monitor_extent((1920, 0, 3200, 960)), (1280, 960))

    def test_observed_primary_rectangle(self):
        self.assertEqual(monitor_extent((0, 0, 1536, 960)), (1536, 960))

    def test_record_fields_match_the_derivation(self):
        record = OBSERVED_MONITORS[1]
        self.assertEqual((record.width, record.height), (1280, 960))

    def test_rejects_degenerate_and_malformed_rectangles(self):
        for rect in ((0, 0, 0, 960), (0, 0, 1280, 0), (3200, 0, 1920, 960)):
            with self.assertRaises(ModeError):
                monitor_extent(rect)
        with self.assertRaises(ModeError):
            monitor_extent((0, 0, 1280))


class SelectedMonitorTests(unittest.TestCase):
    def test_observed_index_one_selects_the_lci_display(self):
        # Shared state +0x70 was 1 in the observed session.
        self.assertEqual(select_monitor_dimensions(OBSERVED_MONITORS, 1), (1280, 960))

    def test_index_zero_selects_the_primary(self):
        self.assertEqual(select_monitor_dimensions(OBSERVED_MONITORS, 0), (1536, 960))

    def test_out_of_range_index_clamps_to_last_record(self):
        # The getters replace an index >= count with count - 1 rather than failing.
        self.assertEqual(select_monitor_dimensions(OBSERVED_MONITORS, 7), (1280, 960))

    def test_empty_and_negative_are_errors(self):
        with self.assertRaises(ModeError):
            select_monitor_dimensions([], 0)
        with self.assertRaises(ModeError):
            select_monitor_dimensions(OBSERVED_MONITORS, -1)


class ReconstructedScorerTests(unittest.TestCase):
    """These assert the reconstruction's own predictions, not observed values."""

    def test_client_request_selects_1600x1200_not_1280x960(self):
        # The observed client size was 2048x1536. The reconstruction picks the
        # best available 4:3 mode, which is also what the sizing helper returned.
        self.assertEqual(select_best_resolution((2048, 1536), LCI_MODES), (1600, 1200))

    def test_exact_available_mode_scores_zero_and_wins(self):
        self.assertEqual(best_resolution_score((1600, 1200), (1600, 1200)), 0)
        self.assertEqual(select_best_resolution((1600, 1200), LCI_MODES), (1600, 1200))

    def test_observed_mode_is_not_the_reconstructed_choice(self):
        # The point of FED-MODE-E001: 1280x960 is not what this rule would pick.
        for request in ((2048, 1536), (1600, 1200)):
            self.assertNotEqual(select_best_resolution(request, LCI_MODES), (1280, 960))

    def test_expected_scores_for_the_observed_mode_list(self):
        scores = {m: best_resolution_score((2048, 1536), m) for m in LCI_MODES}
        self.assertEqual(scores[(1600, 1200)], 257)
        self.assertEqual(scores[(1400, 1050)], 372)
        self.assertEqual(scores[(1280, 960)], 441)
        self.assertEqual(min(scores.values()), 257)

    def test_matching_aspect_ratio_is_preferred_over_closer_pixels(self):
        # 1920x1080 is nearer 2048x1536 in width but loses on the aspect bonus.
        self.assertLess(
            best_resolution_score((2048, 1536), (1600, 1200)),
            best_resolution_score((2048, 1536), (1920, 1080)),
        )

    def test_odd_dimension_modes_are_discarded(self):
        self.assertEqual(
            select_best_resolution((1280, 960), [(1281, 960), (1280, 960)]),
            (1280, 960),
        )
        with self.assertRaises(ModeError):
            select_best_resolution((1280, 960), [(1281, 961)])

    def test_rejects_non_positive_resolutions(self):
        with self.assertRaises(ModeError):
            best_resolution_score((0, 1536), (1280, 960))


class CustomizeResolutionGateTests(unittest.TestCase):
    def test_lci_configuration_can_never_apply(self):
        # MirrorMode 0 selects the LCI rung and is checked before ForceResW/H.
        self.assertFalse(customize_resolution_would_apply(0, 1280, 960))
        self.assertFalse(customize_resolution_would_apply(0, 0, 0))

    def test_mirror_mode_needs_a_usable_forced_pair(self):
        self.assertTrue(customize_resolution_would_apply(1, 1280, 960))
        self.assertFalse(customize_resolution_would_apply(1, 0, 960))
        self.assertFalse(customize_resolution_would_apply(1, 1280, 0))

    def test_pixel_limit_boundary(self):
        self.assertTrue(customize_resolution_would_apply(1, 3840, 2160))
        self.assertEqual(3840 * 2160, CUSTOMIZE_RESOLUTION_PIXEL_LIMIT)
        self.assertFalse(customize_resolution_would_apply(1, 3840, 2162))


if __name__ == "__main__":
    unittest.main()
