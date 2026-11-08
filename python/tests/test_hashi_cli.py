"""Tests for the command-line entry point.

Nothing here contacts a device or creates a session. What is checked is the
part that can be: argument handling, the refusals, and that `plan` actually
describes the sequence the run performs — in particular that it names the
consumer ordering, which is the one piece of this file that exists because
getting it wrong produces no error at all.
"""

import io
import socket
import unittest
from unittest import mock

import hashi_cli as cli
import hashi_gnome as gnome
import hashi_host as host
import hashi_usbmux as usbmux


class ParserTests(unittest.TestCase):
    def test_defaults_match_the_observed_configuration(self):
        args = cli.build_parser().parse_args(["run"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.fps, host.TARGET_FPS)
        self.assertEqual(args.refresh, gnome.TARGET_REFRESH)
        self.assertEqual(args.keepalive, 1.0)
        # Discovery is the default: usbmuxd reassigns the id on every attach.
        self.assertIsNone(args.device_id)
        # Skipping unchanged frames is on, and the session is not permitted.
        self.assertTrue(args.skip_unchanged)
        self.assertFalse(args.allow_session)
        self.assertFalse(args.solid)

    def test_skipping_can_be_turned_off(self):
        args = cli.build_parser().parse_args(["run", "--no-skip-unchanged"])
        self.assertFalse(args.skip_unchanged)

    def test_an_unknown_command_is_rejected(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["frobnicate"])


class RefusalTests(unittest.TestCase):
    def test_run_refuses_without_allow_session(self):
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            self.assertEqual(cli.main(["run"]), 2)
        message = stderr.getvalue()
        self.assertIn("--allow-session", message)
        # The refusal must name the consequences, not just the flag.
        self.assertIn("screen-sharing indicator", message)
        self.assertIn("bytes to the iPad", message)

    def test_the_solid_refusal_does_not_claim_a_monitor_appears(self):
        # With --solid there is no virtual monitor, so promising one would be
        # wrong in the one message a user reads before deciding.
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            self.assertEqual(cli.main(["run", "--solid"]), 2)
        self.assertNotIn("monitor on your desktop", stderr.getvalue())

    def test_impossible_values_are_refused_before_anything_opens(self):
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            self.assertEqual(cli.main(["run", "--fps", "0"]), 2)
            self.assertEqual(cli.main(["run", "--keepalive", "0"]), 2)


class PlanTests(unittest.TestCase):
    def _plan(self, *extra):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            self.assertEqual(cli.main(["plan", *extra]), 0)
        return stdout.getvalue()

    def test_plan_touches_nothing_and_says_so(self):
        text = self._plan()
        self.assertIn("Nothing was done", text)

    def test_plan_names_the_pinned_geometry_and_the_swapped_port(self):
        text = self._plan()
        self.assertIn(f"{gnome.TARGET_WIDTH}x{gnome.TARGET_HEIGHT}", text)
        self.assertIn(str(usbmux.htons_port(usbmux.APPLICATION_PORT)), text)

    def test_plan_names_the_consumer_ordering(self):
        # The ordering is why this entry point exists: injecting before the
        # PipeWire stream has a consumer is silently discarded.
        text = self._plan()
        self.assertIn("first frame BEFORE injecting", text)

    def test_plan_describes_discovery_or_the_forced_id(self):
        self.assertIn("discover the device id", self._plan())
        self.assertIn("without discovery", self._plan("--device-id", "7"))

    def test_the_solid_plan_promises_no_monitor_and_no_injection(self):
        text = self._plan("--solid")
        self.assertIn("NO virtual monitor", text)
        self.assertIn("NO injection", text)
        self.assertNotIn("inject inbound", text)


class UsbmuxReadTests(unittest.TestCase):
    """The message reader, over a real socket pair rather than a mock."""

    def test_a_message_split_across_writes_is_reassembled(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            message = usbmux.build_list_devices()
            right.sendall(message[:9])
            right.sendall(message[9:])
            self.assertEqual(cli._recv_usbmux_message(left), message)
        finally:
            left.close()
            right.close()

    def test_a_peer_that_closes_early_is_reported(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            right.sendall(usbmux.build_list_devices()[:8])
            right.close()
            with self.assertRaises(host.HostError):
                cli._recv_usbmux_message(left)
        finally:
            left.close()

    def test_a_length_shorter_than_the_header_is_refused(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            # A header announcing 4 total bytes cannot be a real message. The
            # refusal lives in usbmux.decode_header, so that is the error that
            # surfaces; the CLI presents it like its own.
            right.sendall((4).to_bytes(4, "little") + bytes(12))
            right.close()
            with self.assertRaises(usbmux.UsbmuxError):
                cli._recv_usbmux_message(left)
        finally:
            left.close()

    def test_an_absent_daemon_is_reported_with_a_hint(self):
        with mock.patch("socket.socket") as factory:
            factory.return_value.connect.side_effect = FileNotFoundError(
                2, "No such file or directory")
            with self.assertRaises(host.HostError) as caught:
                cli.list_devices()
        self.assertIn("usbmuxd", str(caught.exception))


class DevicesTests(unittest.TestCase):
    def test_no_devices_is_a_nonzero_exit(self):
        stdout = io.StringIO()
        with mock.patch.object(cli, "list_devices", return_value=[]), \
                mock.patch("sys.stdout", stdout):
            self.assertEqual(cli.main(["devices"]), 1)
        self.assertIn("no attached devices", stdout.getvalue())

    def test_the_ipad_is_marked_in_a_listing(self):
        listing = [
            {"device_id": 3, "product_id": 0x1234, "connection_type": "USB",
             "serial": "other"},
            {"device_id": 4, "product_id": usbmux.IPAD_PRODUCT_ID,
             "connection_type": "USB", "serial": "theipad"},
        ]
        stdout = io.StringIO()
        with mock.patch.object(cli, "list_devices", return_value=listing), \
                mock.patch("sys.stdout", stdout):
            self.assertEqual(cli.main(["devices"]), 0)
        text = stdout.getvalue()
        self.assertIn("theipad", text)
        self.assertIn("<- iPad", text)
        # The marker belongs on the iPad's line only.
        ipad_line = [l for l in text.splitlines() if "theipad" in l][0]
        other_line = [l for l in text.splitlines() if "other" in l][0]
        self.assertIn("<- iPad", ipad_line)
        self.assertNotIn("<- iPad", other_line)


class OrderingTests(unittest.TestCase):
    """The sequence `run` performs, asserted without a device or a session."""

    def test_capture_starts_and_yields_a_frame_before_the_handshake(self):
        calls = []

        class FakeDisplay:
            def __init__(self, **_kwargs):
                pass

            def open(self):
                calls.append("display.open")
                return 42

            def close(self):
                calls.append("display.close")
                return []

        class FakeSource:
            frames_captured = 1
            frames_repeated = 0

            def __init__(self, node_id, **_kwargs):
                calls.append(f"source.init({node_id})")

            def start(self):
                calls.append("source.start")

            def next_payload(self):
                calls.append("source.first_frame")
                return b"\xff\xd8\xff\xd9"

            def close(self):
                calls.append("source.close")

        class FakeSession:
            def __init__(self, **_kwargs):
                self.stats = host.SessionStats()
                self.diff_jpeg = False

            def connect(self):
                calls.append("session.connect")
                return (2048, 1536)

            def run(self, frames=None, on_record=None):
                calls.append("session.run")
                cli._interrupted = True
                return self.stats

            def close(self):
                calls.append("session.close")

        with mock.patch.object(cli.gnome, "VirtualDisplaySession", FakeDisplay), \
                mock.patch.object(cli.host, "PipeWireFrameSource", FakeSource), \
                mock.patch.object(cli.host, "HostSession", FakeSession), \
                mock.patch.object(cli.signal, "signal"), \
                mock.patch("sys.stdout", io.StringIO()):
            cli._interrupted = False
            try:
                self.assertEqual(cli.main(["run", "--allow-session"]), 0)
            finally:
                cli._interrupted = False

        # The first frame must be pulled before the handshake, because
        # injection is silently discarded until the stream has a consumer.
        self.assertLess(calls.index("source.first_frame"),
                        calls.index("session.connect"))
        # And the monitor has to exist before capture can attach to its node.
        self.assertLess(calls.index("display.open"), calls.index("source.init(42)"))
        self.assertEqual(calls[:4],
                         ["display.open", "source.init(42)", "source.start",
                          "source.first_frame"])
        # Teardown happens, and the monitor is released last.
        self.assertIn("session.close", calls)
        self.assertEqual(calls[-1], "display.close")

    def test_the_solid_path_creates_no_session_at_all(self):
        created = []

        class FakeDisplay:
            def __init__(self, **_kwargs):
                created.append("display")

        class FakeSession:
            def __init__(self, **kwargs):
                self.stats = host.SessionStats()
                self.diff_jpeg = False
                created.append(("inject", kwargs.get("inject")))

            def connect(self):
                return (2048, 1536)

            def run(self, frames=None, on_record=None):
                cli._interrupted = True
                return self.stats

            def close(self):
                pass

        with mock.patch.object(cli.gnome, "VirtualDisplaySession", FakeDisplay), \
                mock.patch.object(cli.host, "HostSession", FakeSession), \
                mock.patch.object(cli.signal, "signal"), \
                mock.patch("sys.stdout", io.StringIO()):
            cli._interrupted = False
            try:
                cli.main(["run", "--solid", "--allow-session"])
            finally:
                cli._interrupted = False

        self.assertNotIn("display", created)
        # A solid source cannot prove a consumer exists, so injection is off.
        self.assertIn(("inject", False), created)

    def test_a_failure_opening_the_monitor_still_reports_and_tears_down(self):
        closed = []

        class FakeDisplay:
            def __init__(self, **_kwargs):
                pass

            def open(self):
                raise gnome.GnomeError("no compositor here")

            def close(self):
                closed.append("display")
                return ["Session not started"]

        stderr = io.StringIO()
        with mock.patch.object(cli.gnome, "VirtualDisplaySession", FakeDisplay), \
                mock.patch.object(cli.signal, "signal"), \
                mock.patch("sys.stdout", io.StringIO()), \
                mock.patch("sys.stderr", stderr):
            self.assertEqual(cli.main(["run", "--allow-session"]), 1)

        # The real cause is reported, and teardown's own complaint does not
        # replace it.
        self.assertIn("no compositor here", stderr.getvalue())
        self.assertEqual(closed, ["display"])


if __name__ == "__main__":
    unittest.main()
