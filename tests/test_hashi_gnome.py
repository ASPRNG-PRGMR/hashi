"""Tests for the GNOME/Mutter virtual monitor and input injection layer.

These assert the contracts verified as FED-DBUS-E001 and the input mapping
against the records observed live as FED-LIVE-E001. Nothing here creates a
D-Bus session, so the suite runs with no compositor and no device.
"""

import unittest

import hashi_gnome as g


class TestVerifiedContractSurface(unittest.TestCase):
    """The names and versions FED-DBUS-E001 actually verified."""

    def test_bus_names_and_paths(self):
        self.assertEqual(g.SCREEN_CAST_BUS_NAME, "org.gnome.Mutter.ScreenCast")
        self.assertEqual(g.SCREEN_CAST_OBJECT_PATH, "/org/gnome/Mutter/ScreenCast")
        self.assertEqual(
            g.SCREEN_CAST_SESSION_IFACE, "org.gnome.Mutter.ScreenCast.Session"
        )
        self.assertEqual(
            g.SCREEN_CAST_STREAM_IFACE, "org.gnome.Mutter.ScreenCast.Stream"
        )
        self.assertEqual(g.REMOTE_DESKTOP_BUS_NAME, "org.gnome.Mutter.RemoteDesktop")
        self.assertEqual(
            g.REMOTE_DESKTOP_OBJECT_PATH, "/org/gnome/Mutter/RemoteDesktop"
        )
        self.assertEqual(
            g.REMOTE_DESKTOP_SESSION_IFACE, "org.gnome.Mutter.RemoteDesktop.Session"
        )

    def test_verified_versions_are_the_measured_ones(self):
        self.assertEqual(g.VERIFIED_VERSIONS, {"ScreenCast": 4, "RemoteDesktop": 1})

    def test_check_versions_accepts_the_verified_pair(self):
        self.assertIsNone(g.check_versions(4, 1))

    def test_check_versions_rejects_an_unverified_screen_cast(self):
        for version in (3, 5):
            with self.subTest(version=version):
                with self.assertRaises(g.GnomeError):
                    g.check_versions(version, 1)

    def test_check_versions_rejects_an_unverified_remote_desktop(self):
        with self.assertRaises(g.GnomeError):
            g.check_versions(4, 2)

    def test_supported_device_types(self):
        # The installed build reports 7 = keyboard | pointer | touchscreen.
        self.assertTrue(g.supports_device_types(7, g.DEVICE_TYPE_POINTER))
        self.assertTrue(
            g.supports_device_types(7, g.DEVICE_TYPE_POINTER | g.DEVICE_TYPE_TOUCHSCREEN)
        )
        self.assertFalse(g.supports_device_types(1, g.DEVICE_TYPE_POINTER))
        self.assertFalse(
            g.supports_device_types(3, g.DEVICE_TYPE_TOUCHSCREEN)
        )

    def test_cursor_mode_values_match_the_documented_enum(self):
        self.assertEqual(
            (g.CURSOR_MODE_HIDDEN, g.CURSOR_MODE_EMBEDDED, g.CURSOR_MODE_METADATA),
            (0, 1, 2),
        )


class TestVirtualMonitorMode(unittest.TestCase):
    """``modes`` entries, per create_mode_infos' own validation."""

    def test_default_mode_is_the_target_size(self):
        mode = g.virtual_monitor_mode()
        self.assertEqual(mode["size"], ("(uu)", (1280, 960)))
        self.assertEqual(mode["refresh-rate"], ("d", 30.0))
        self.assertEqual(mode["is-preferred"], ("b", True))

    def test_size_is_required_and_unsigned(self):
        # "size" ((uu)): Width and height. Required.
        self.assertEqual(g.virtual_monitor_mode(640, 480)["size"][0], "(uu)")

    def test_refresh_rate_can_be_omitted(self):
        mode = g.virtual_monitor_mode(refresh_rate=None)
        self.assertNotIn("refresh-rate", mode)
        self.assertIn("size", mode)

    def test_zero_dimension_is_rejected(self):
        for width, height in ((0, 960), (1280, 0)):
            with self.subTest(size=(width, height)):
                with self.assertRaises(g.GnomeError):
                    g.virtual_monitor_mode(width, height)

    def test_non_positive_refresh_rate_is_rejected(self):
        with self.assertRaises(g.GnomeError):
            g.virtual_monitor_mode(refresh_rate=0)

    def test_non_preferred_mode(self):
        self.assertEqual(
            g.virtual_monitor_mode(is_preferred=False)["is-preferred"], ("b", False)
        )


class TestRecordVirtualProperties(unittest.TestCase):
    def test_default_properties(self):
        props = g.record_virtual_properties()
        self.assertEqual(props["modes"][0], "aa{sv}")
        self.assertEqual(len(props["modes"][1]), 1)
        self.assertEqual(props["modes"][1][0]["size"], ("(uu)", (1280, 960)))
        # Embedded, not Mutter's default of hidden: the iPad has no other way
        # to be shown a cursor.
        self.assertEqual(props["cursor-mode"], ("u", g.CURSOR_MODE_EMBEDDED))

    def test_is_platform_is_omitted_unless_asked_for(self):
        self.assertNotIn("is-platform", g.record_virtual_properties())
        self.assertEqual(
            g.record_virtual_properties(is_platform=True)["is-platform"], ("b", True)
        )
        self.assertEqual(
            g.record_virtual_properties(is_platform=False)["is-platform"], ("b", False)
        )

    def test_exactly_one_preferred_mode_is_required(self):
        # Mutter: "Multiple preferred modes" / "No preferred modes".
        two_preferred = [
            g.virtual_monitor_mode(1280, 960),
            g.virtual_monitor_mode(640, 480),
        ]
        with self.assertRaises(g.GnomeError):
            g.record_virtual_properties(two_preferred)

        none_preferred = [g.virtual_monitor_mode(1280, 960, is_preferred=False)]
        with self.assertRaises(g.GnomeError):
            g.record_virtual_properties(none_preferred)

    def test_a_valid_multi_mode_list_is_accepted(self):
        modes = [
            g.virtual_monitor_mode(1280, 960),
            g.virtual_monitor_mode(640, 480, is_preferred=False),
        ]
        self.assertEqual(len(g.record_virtual_properties(modes)["modes"][1]), 2)

    def test_empty_modes_rejected(self):
        with self.assertRaises(g.GnomeError):
            g.record_virtual_properties([])

    def test_unknown_cursor_mode_rejected(self):
        with self.assertRaises(g.GnomeError):
            g.record_virtual_properties(cursor_mode=3)


class TestScreenCastSessionProperties(unittest.TestCase):
    def test_remote_desktop_session_id_binds_the_sessions(self):
        props = g.screen_cast_session_properties("abc123")
        self.assertEqual(props["remote-desktop-session-id"], ("s", "abc123"))

    def test_empty_dict_without_an_id(self):
        self.assertEqual(g.screen_cast_session_properties(), {})

    def test_empty_id_rejected(self):
        with self.assertRaises(g.GnomeError):
            g.screen_cast_session_properties("")

    def test_disable_animations(self):
        props = g.screen_cast_session_properties("x", disable_animations=True)
        self.assertEqual(props["disable-animations"], ("b", True))


class TestGlibVariantConversion(unittest.TestCase):
    """The dictionaries must actually build the variants Mutter expects."""

    def setUp(self):
        try:
            from gi.repository import GLib  # noqa: F401
        except ImportError:  # pragma: no cover
            self.skipTest("PyGObject not available")

    def test_record_virtual_properties_build_an_asv(self):
        variant = g.to_glib_variant_dict(g.record_virtual_properties())
        self.assertEqual(variant.get_type_string(), "a{sv}")

    def test_modes_nest_as_aa_sv_with_a_uu_size(self):
        variant = g.to_glib_variant_dict(g.record_virtual_properties())
        modes = variant.unpack()["modes"]
        self.assertEqual(len(modes), 1)
        self.assertEqual(modes[0]["size"], (1280, 960))
        self.assertEqual(modes[0]["refresh-rate"], 30.0)
        self.assertIs(modes[0]["is-preferred"], True)

    def test_modes_variant_type_is_exactly_what_mutter_looks_up(self):
        # create_mode_infos does g_variant_lookup_value(.., "modes",
        # G_VARIANT_TYPE ("aa{sv}")), which returns NULL on any other type.
        variant = g.to_glib_variant_dict(g.record_virtual_properties())
        self.assertEqual(variant.lookup_value("modes", None).get_type_string(), "aa{sv}")

    def test_size_child_type_is_uu(self):
        variant = g.to_glib_variant_dict(g.record_virtual_properties())
        mode = variant.lookup_value("modes", None).get_child_value(0)
        self.assertEqual(mode.lookup_value("size", None).get_type_string(), "(uu)")

    def test_cursor_mode_is_u_not_i(self):
        variant = g.to_glib_variant_dict(g.record_virtual_properties())
        self.assertEqual(
            variant.lookup_value("cursor-mode", None).get_type_string(), "u"
        )

    def test_session_properties_id_is_a_string(self):
        variant = g.to_glib_variant_dict(g.screen_cast_session_properties("sid"))
        self.assertEqual(
            variant.lookup_value("remote-desktop-session-id", None).get_type_string(),
            "s",
        )


class TestEvdevButtonMapping(unittest.TestCase):
    def test_published_uapi_values(self):
        # <linux/input-event-codes.h>
        self.assertEqual((g.BTN_LEFT, g.BTN_RIGHT, g.BTN_MIDDLE), (0x110, 0x111, 0x112))

    def test_observed_values_map_to_the_left_button(self):
        # FED-LIVE-E001: field0 5 = down, 6 = up, both left.
        self.assertEqual(g.EVDEV_BUTTON_FOR_FIELD0[5], g.BTN_LEFT)
        self.assertEqual(g.EVDEV_BUTTON_FOR_FIELD0[6], g.BTN_LEFT)

    def test_statically_decoded_values_map_to_right_and_middle(self):
        self.assertEqual(g.EVDEV_BUTTON_FOR_FIELD0[8], g.BTN_RIGHT)
        self.assertEqual(g.EVDEV_BUTTON_FOR_FIELD0[9], g.BTN_RIGHT)
        self.assertEqual(g.EVDEV_BUTTON_FOR_FIELD0[14], g.BTN_MIDDLE)
        self.assertEqual(g.EVDEV_BUTTON_FOR_FIELD0[15], g.BTN_MIDDLE)

    def test_button_codes_are_not_win32_flags(self):
        # The regression this guards: MOUSEEVENTF_LEFTDOWN is 2, and passing
        # that to NotifyPointerButton would be meaningless.
        self.assertNotIn(2, g.EVDEV_BUTTON_FOR_FIELD0.values())
        self.assertNotIn(1, g.EVDEV_BUTTON_FOR_FIELD0.values())


class TestPlanInjection(unittest.TestCase):
    STREAM = "/org/gnome/Mutter/ScreenCast/Stream/u0"

    def plan(self, field0, x=100, y=200):
        return g.plan_injection(field0, x, y, stream_path=self.STREAM)

    def test_motion_is_a_single_absolute_call(self):
        calls = self.plan(10, 640, 480)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].method, "NotifyPointerMotionAbsolute")
        self.assertEqual(calls[0].args, (self.STREAM, 640.0, 480.0))

    def test_coordinates_pass_through_unscaled(self):
        # The whole point of FED-DBUS-E001's transform finding: no 65535
        # normalisation, no scaling, no desktop offset.
        calls = self.plan(10, 3, 951)
        self.assertEqual(calls[0].args[1:], (3.0, 951.0))

    def test_coordinates_are_doubles(self):
        calls = self.plan(10, 5, 6)
        for value in calls[0].args[1:]:
            self.assertIsInstance(value, float)

    def test_down_moves_before_pressing(self):
        calls = self.plan(5, 10, 20)
        self.assertEqual(
            [c.method for c in calls],
            ["NotifyPointerMotionAbsolute", "NotifyPointerButton"],
        )
        self.assertEqual(calls[0].args, (self.STREAM, 10.0, 20.0))
        self.assertEqual(calls[1].args, (g.BTN_LEFT, True))

    def test_up_moves_before_releasing(self):
        calls = self.plan(6, 10, 20)
        self.assertEqual(calls[1].args, (g.BTN_LEFT, False))

    def test_button_call_carries_no_stream_argument(self):
        # NotifyPointerButton(in i button, in b state) — verified signature.
        calls = self.plan(5)
        self.assertEqual(len(calls[1].args), 2)
        self.assertNotIn(self.STREAM, calls[1].args)

    def test_movement_only_values_are_motion(self):
        for field0 in (4, 7):
            with self.subTest(field0=field0):
                calls = self.plan(field0)
                self.assertEqual([c.method for c in calls],
                                 ["NotifyPointerMotionAbsolute"])

    def test_keyboard_and_control_values_produce_nothing(self):
        # Decoded but unexercised: this host invents no behaviour for them.
        for field0 in (1, 2, 16, 17):
            with self.subTest(field0=field0):
                self.assertEqual(self.plan(field0), [])

    def test_unobserved_values_produce_nothing(self):
        for field0 in (3, 11, 12, 13):
            with self.subTest(field0=field0):
                self.assertEqual(self.plan(field0), [])

    def test_boundary_coordinates_accepted(self):
        for x, y in ((0, 0), (1280, 960), (0, 960), (1280, 0)):
            with self.subTest(coord=(x, y)):
                self.assertEqual(len(self.plan(10, x, y)), 1)

    def test_out_of_range_coordinates_rejected(self):
        for x, y in ((-1, 0), (0, -1), (1281, 0), (0, 961)):
            with self.subTest(coord=(x, y)):
                with self.assertRaises(g.GnomeError):
                    self.plan(10, x, y)

    def test_a_custom_display_size_moves_the_bounds(self):
        calls = g.plan_injection(
            10, 1900, 1000, stream_path=self.STREAM, width=1920, height=1080
        )
        self.assertEqual(calls[0].args[1:], (1900.0, 1000.0))
        with self.assertRaises(g.GnomeError):
            g.plan_injection(
                10, 1900, 1000, stream_path=self.STREAM, width=1280, height=960
            )

    def test_stream_path_is_required(self):
        with self.assertRaises(g.GnomeError):
            g.plan_injection(10, 0, 0, stream_path="")


class TestObservedSequences(unittest.TestCase):
    """Replay the shapes FED-LIVE-E001 actually recorded."""

    STREAM = "/org/gnome/Mutter/ScreenCast/Stream/u0"

    def plan_all(self, records):
        return [
            g.plan_injection(f, x, y, stream_path=self.STREAM) for f, x, y in records
        ]

    def test_a_tap_is_five_then_six(self):
        # Observed ten times: a bare 5 -> 6 with no motion record between.
        plans = self.plan_all([(5, 400, 300), (6, 400, 300)])
        self.assertEqual(
            [c.method for plan in plans for c in plan],
            [
                "NotifyPointerMotionAbsolute",
                "NotifyPointerButton",
                "NotifyPointerMotionAbsolute",
                "NotifyPointerButton",
            ],
        )
        presses = [c.args[1] for plan in plans for c in plan
                   if c.method == "NotifyPointerButton"]
        self.assertEqual(presses, [True, False])

    def test_a_tap_presses_at_its_own_coordinates(self):
        # The reason motion precedes the press: a tap carries its position and
        # nothing moved the pointer there beforehand.
        plans = self.plan_all([(5, 123, 456), (6, 123, 456)])
        self.assertEqual(plans[0][0].args, (self.STREAM, 123.0, 456.0))

    def test_a_drag_is_five_motion_six(self):
        records = [(5, 100, 100), (10, 110, 105), (10, 120, 110), (6, 120, 110)]
        plans = self.plan_all(records)
        self.assertEqual([len(p) for p in plans], [2, 1, 1, 2])
        self.assertEqual(
            [c.args[1:] for c in plans[1] + plans[2]],
            [(110.0, 105.0), (120.0, 110.0)],
        )

    def test_downs_and_ups_strictly_alternate(self):
        # The invariant observed across 41 downs and 40 ups.
        records = [(5, 1, 1), (6, 1, 1), (5, 2, 2), (6, 2, 2)]
        states = [
            c.args[1]
            for plan in self.plan_all(records)
            for c in plan
            if c.method == "NotifyPointerButton"
        ]
        self.assertEqual(states, [True, False, True, False])

    def test_the_observed_coordinate_extremes(self):
        # x spanned 3..1236 and y 2..951 across 1,449 records.
        for x, y in ((3, 2), (1236, 951)):
            with self.subTest(coord=(x, y)):
                calls = g.plan_injection(10, x, y, stream_path=self.STREAM)
                self.assertEqual(calls[0].args[1:], (float(x), float(y)))

    def test_only_three_field0_values_were_ever_seen(self):
        observed = {5, 6, 10}
        for field0 in observed:
            with self.subTest(field0=field0):
                self.assertTrue(
                    g.plan_injection(field0, 0, 0, stream_path=self.STREAM)
                )


class TestSessionIsInert(unittest.TestCase):
    """Constructing a session must not touch the bus."""

    def test_construction_creates_no_session(self):
        session = g.VirtualDisplaySession()
        self.assertIsNone(session.stream_path)
        self.assertIsNone(session.node_id)
        self.assertIsNone(session.session_id)

    def test_defaults_are_the_target_mode(self):
        session = g.VirtualDisplaySession()
        self.assertEqual((session.width, session.height), (1280, 960))
        self.assertEqual(session.refresh_rate, 30.0)
        self.assertEqual(session.cursor_mode, g.CURSOR_MODE_EMBEDDED)
        self.assertIsNone(session.is_platform)

    def test_inject_without_a_session_is_an_error(self):
        with self.assertRaises(g.GnomeError):
            g.VirtualDisplaySession().inject(10, 0, 0)

    def test_stream_parameters_without_a_session_is_an_error(self):
        with self.assertRaises(g.GnomeError):
            g.VirtualDisplaySession().stream_parameters()

    def test_close_without_a_session_is_harmless(self):
        self.assertIsNone(g.VirtualDisplaySession().close())


if __name__ == "__main__":
    unittest.main()
