"""Tests for the host composition layer.

The whole point of this module's shape is that the loop can be exercised with a
fake socket and a solid-colour source, so these tests open no socket, create no
D-Bus session and contact no device.

The inbound reassembly tests are built from the record shape FED-LIVE-E001
actually observed: a 4-byte ``07 00 00 0c`` header followed by three big-endian
32-bit fields.
"""

import unittest

import hashi_gnome as gnome
import hashi_host as host
import hashi_stream as stream


def tlv7(field0: int, x: int, y: int) -> bytes:
    """One inbound record in the observed 16-byte shape."""
    return (
        bytes([stream.TLV_TYPE_7, 0x00, 0x00, 0x0C])
        + field0.to_bytes(4, "big")
        + x.to_bytes(4, "big")
        + y.to_bytes(4, "big")
    )


class FakeSocket:
    """Records what was sent and replays a queued inbound stream."""

    def __init__(self, inbound: bytes = b""):
        self.sent = bytearray()
        self.inbound = bytearray(inbound)
        self.closed = False

    def sendall(self, data):
        self.sent.extend(data)

    def recv(self, count):
        chunk = bytes(self.inbound[:count])
        del self.inbound[:count]
        return chunk

    def close(self):
        self.closed = True


class FakeDisplay:
    """Stands in for VirtualDisplaySession, recording the planned calls."""

    def __init__(self, stream_path="/stream/0", stream_consumed=True):
        self.stream_path = stream_path
        # Real injection is a silent no-op for motion until the PipeWire
        # stream has a consumer, so the session guards on this.
        self.stream_consumed = stream_consumed
        self.calls = []

    def inject(self, field0, x, y):
        planned = gnome.plan_injection(field0, x, y, stream_path=self.stream_path)
        self.calls.extend(planned)
        return planned


class TestCapturePipeline(unittest.TestCase):
    def test_node_id_becomes_the_pipewiresrc_path(self):
        description = host.capture_pipeline_description(42)
        self.assertIn("pipewiresrc path=42", description)

    def test_caps_pin_the_target_geometry(self):
        description = host.capture_pipeline_description(1)
        self.assertIn("width=1280", description)
        self.assertIn("height=960", description)
        self.assertIn("format=RGB", description)

    def test_appsink_is_named_and_drops_stale_frames(self):
        description = host.capture_pipeline_description(1)
        self.assertIn("appsink name=sink", description)
        self.assertIn("max-buffers=1", description)
        self.assertIn("drop=true", description)

    def test_videoconvert_is_present(self):
        # The compositor's buffers are typically BGRx; Pillow needs RGB.
        self.assertIn("videoconvert", host.capture_pipeline_description(1))

    def test_custom_geometry_is_honoured(self):
        description = host.capture_pipeline_description(1, 1920, 1080, 60)
        self.assertIn("width=1920", description)
        self.assertIn("height=1080", description)

    def test_invalid_arguments_rejected(self):
        with self.assertRaises(host.HostError):
            host.capture_pipeline_description(-1)
        with self.assertRaises(host.HostError):
            host.capture_pipeline_description(1, 0, 960)
        with self.assertRaises(host.HostError):
            host.capture_pipeline_description(1, fps=0)


class TestFrameGeometryValidation(unittest.TestCase):
    def test_the_target_size_passes(self):
        self.assertIsNone(host.validate_frame_geometry(1280, 960))

    def test_any_other_size_is_refused(self):
        for width, height in ((1920, 1080), (1280, 961), (640, 480), (960, 1280)):
            with self.subTest(size=(width, height)):
                with self.assertRaises(host.HostError):
                    host.validate_frame_geometry(width, height)

    def test_the_error_names_the_likely_cause(self):
        with self.assertRaises(host.HostError) as caught:
            host.validate_frame_geometry(2560, 1920)
        self.assertIn("scale", str(caught.exception))

    def test_an_explicit_expectation_overrides_the_default(self):
        self.assertIsNone(
            host.validate_frame_geometry(1920, 1080, expected=(1920, 1080))
        )


class TestInboundDemuxer(unittest.TestCase):
    """Stream reassembly — where a framing bug would hide."""

    def test_one_whole_record(self):
        demuxer = host.InboundDemuxer()
        records = demuxer.feed(tlv7(5, 100, 200))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].tlv_type, 7)
        self.assertEqual(records[0].field0, 5)
        self.assertEqual((records[0].field1, records[0].field2), (100, 200))

    def test_several_records_in_one_chunk(self):
        demuxer = host.InboundDemuxer()
        blob = tlv7(5, 1, 2) + tlv7(10, 3, 4) + tlv7(6, 5, 6)
        records = demuxer.feed(blob)
        self.assertEqual([r.field0 for r in records], [5, 10, 6])
        self.assertEqual(demuxer.pending_bytes, 0)

    def test_a_record_split_across_chunks(self):
        demuxer = host.InboundDemuxer()
        whole = tlv7(10, 640, 480)
        for cut in range(1, len(whole)):
            with self.subTest(cut=cut):
                demuxer = host.InboundDemuxer()
                self.assertEqual(demuxer.feed(whole[:cut]), [])
                records = demuxer.feed(whole[cut:])
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0].field0, 10)

    def test_byte_at_a_time_delivery(self):
        demuxer = host.InboundDemuxer()
        blob = tlv7(5, 7, 8) + tlv7(6, 7, 8)
        produced = []
        for byte in blob:
            produced.extend(demuxer.feed(bytes([byte])))
        self.assertEqual([r.field0 for r in produced], [5, 6])

    def test_a_trailing_partial_record_is_held(self):
        demuxer = host.InboundDemuxer()
        blob = tlv7(5, 1, 2) + tlv7(6, 3, 4)[:9]
        records = demuxer.feed(blob)
        self.assertEqual(len(records), 1)
        self.assertEqual(demuxer.pending_bytes, 9)

    def test_counters_track_the_stream(self):
        demuxer = host.InboundDemuxer()
        blob = tlv7(5, 1, 2) + tlv7(6, 1, 2)
        demuxer.feed(blob)
        self.assertEqual(demuxer.records_seen, 2)
        self.assertEqual(demuxer.bytes_seen, len(blob))

    def test_a_zero_length_record_is_rejected(self):
        demuxer = host.InboundDemuxer()
        with self.assertRaises(stream.StreamError):
            demuxer.feed(bytes([7, 0, 0, 0]))

    def test_an_absurd_length_is_rejected_rather_than_buffered(self):
        demuxer = host.InboundDemuxer()
        with self.assertRaises(stream.StreamError):
            demuxer.feed(bytes([7, 0xFF, 0xFF, 0xFF]))

    def test_an_overlong_record_is_consumed_whole_not_desynchronised(self):
        # The agent clamps what it keeps to 12 bytes but consumes what was
        # announced. If this class kept only 12, the next record would start
        # mid-stream and every following one would be garbage.
        overlong = bytes([7, 0, 0, 20]) + bytes(range(20))
        demuxer = host.InboundDemuxer()
        records = demuxer.feed(overlong + tlv7(6, 9, 9))
        self.assertEqual(len(records), 2)
        self.assertTrue(records[0].truncated)
        self.assertEqual(records[1].field0, 6)
        self.assertEqual(demuxer.pending_bytes, 0)

    def test_the_observed_record_size_is_sixteen_bytes(self):
        self.assertEqual(len(tlv7(5, 0, 0)), 16)

    def test_a_full_observed_drag_reassembles(self):
        records = [tlv7(5, 100, 100)]
        records += [tlv7(10, 100 + i, 100 + i) for i in range(20)]
        records += [tlv7(6, 120, 120)]
        demuxer = host.InboundDemuxer()
        parsed = demuxer.feed(b"".join(records))
        self.assertEqual(len(parsed), 22)
        self.assertEqual(parsed[0].field0, 5)
        self.assertEqual(parsed[-1].field0, 6)
        self.assertTrue(all(r.field0 == 10 for r in parsed[1:-1]))


class TestPacer(unittest.TestCase):
    def test_interval_comes_from_the_decoded_rule(self):
        # 1000 // 30 = 33 ms, truncated as the agent truncates.
        pacer = host.Pacer(30)
        self.assertAlmostEqual(pacer.interval_s, 0.033, places=6)

    def test_the_first_frame_does_not_wait(self):
        clock = [0.0]
        pacer = host.Pacer(30, now=lambda: clock[0])
        self.assertEqual(pacer.sleep_s(), 0.0)

    def test_a_prompt_caller_waits_the_remainder(self):
        clock = [0.0]
        pacer = host.Pacer(30, now=lambda: clock[0])
        pacer.sleep_s()
        clock[0] = 0.010
        self.assertAlmostEqual(pacer.sleep_s(), 0.023, places=6)

    def test_a_late_caller_does_not_wait(self):
        clock = [0.0]
        pacer = host.Pacer(30, now=lambda: clock[0])
        pacer.sleep_s()
        clock[0] = 1.0
        self.assertEqual(pacer.sleep_s(), 0.0)

    def test_schedule_does_not_drift_against_the_target(self):
        # Scheduling against the previous target, not the previous wakeup, is
        # what stops one late frame making every later frame late.
        clock = [0.0]
        pacer = host.Pacer(30, now=lambda: clock[0])
        pacer.sleep_s()
        waits = []
        for _ in range(3):
            clock[0] += 0.005
            waits.append(pacer.sleep_s())
        self.assertAlmostEqual(waits[0], 0.028, places=6)
        self.assertAlmostEqual(waits[1], 0.056, places=6)

    def test_a_long_stall_resets_rather_than_bursting(self):
        clock = [0.0]
        pacer = host.Pacer(30, now=lambda: clock[0])
        pacer.sleep_s()
        clock[0] = 5.0
        self.assertEqual(pacer.sleep_s(), 0.0)
        clock[0] = 5.001
        self.assertGreater(pacer.sleep_s(), 0.0)

    def test_an_invalid_rate_is_rejected(self):
        with self.assertRaises(stream.StreamError):
            host.Pacer(0)


class TestSolidColourSource(unittest.TestCase):
    def setUp(self):
        try:
            import PIL  # noqa: F401
        except ImportError:  # pragma: no cover
            self.skipTest("Pillow not available")

    def test_frames_are_valid_jpeg_records(self):
        source = host.SolidColourSource([(0, 0, 0)])
        payload = source.next_payload()
        self.assertTrue(payload.startswith(b"\xff\xd8"))
        self.assertTrue(payload.endswith(b"\xff\xd9"))

    def test_the_black_frame_is_the_known_good_one(self):
        # Byte-identical to the first captured record (FED-JPEG-E001).
        import hashlib

        import hashi_jpeg as jpeg

        payload = host.SolidColourSource([(0, 0, 0)]).next_payload()
        self.assertEqual(payload, jpeg.solid_frame(1280, 960, (0, 0, 0)))
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "317955d8383feb8b7e0e47b753c01b725373c1d35673a61adea31406a01d961d",
        )

    def test_colours_cycle(self):
        source = host.SolidColourSource([(0, 0, 0), (255, 255, 255)])
        first, second, third = (source.next_payload() for _ in range(3))
        self.assertNotEqual(first, second)
        self.assertEqual(first, third)

    def test_hold_frames_repeats_each_colour(self):
        source = host.SolidColourSource([(0, 0, 0), (255, 255, 255)], hold_frames=2)
        payloads = [source.next_payload() for _ in range(4)]
        self.assertEqual(payloads[0], payloads[1])
        self.assertEqual(payloads[2], payloads[3])
        self.assertNotEqual(payloads[0], payloads[2])

    def test_empty_colour_list_rejected(self):
        with self.assertRaises(host.HostError):
            host.SolidColourSource([])

    def test_bad_hold_frames_rejected(self):
        with self.assertRaises(host.HostError):
            host.SolidColourSource([(0, 0, 0)], hold_frames=0)


class TestReplayFrameSource(unittest.TestCase):
    def test_replays_in_order_and_loops(self):
        source = host.ReplayFrameSource([b"a", b"b"])
        self.assertEqual(
            [source.next_payload() for _ in range(5)],
            [b"a", b"b", b"a", b"b", b"a"],
        )

    def test_without_looping_it_stops(self):
        source = host.ReplayFrameSource([b"a"], loop=False)
        self.assertEqual(source.next_payload(), b"a")
        with self.assertRaises(StopIteration):
            source.next_payload()

    def test_empty_replay_rejected(self):
        with self.assertRaises(host.HostError):
            host.ReplayFrameSource([])


class TestSessionLoop(unittest.TestCase):
    """The outbound loop and inbound dispatch, over a fake socket."""

    def make_session(self, inbound=b"", **kwargs):
        session = host.HostSession(
            source=host.ReplayFrameSource([b"\xff\xd8frame\xff\xd9"]),
            display=FakeDisplay(),
            **kwargs,
        )
        session._socket = FakeSocket(inbound)
        return session

    def test_frames_are_sent_as_encoded_records(self):
        session = self.make_session()
        session.run(frames=3)
        self.assertEqual(session.stats.frames_sent, 3)
        expected = stream.encode_image_record(b"\xff\xd8frame\xff\xd9")
        self.assertEqual(bytes(session._socket.sent), expected * 3)

    def test_records_carry_the_image_tag(self):
        session = self.make_session()
        session.run(frames=1)
        self.assertEqual(session._socket.sent[0], stream.TYPE_IMAGE)

    def test_bytes_sent_is_tracked(self):
        session = self.make_session()
        session.run(frames=2)
        self.assertEqual(session.stats.bytes_sent, len(session._socket.sent))

    def test_inbound_input_is_injected(self):
        session = self.make_session(inbound=tlv7(5, 400, 300) + tlv7(6, 400, 300))
        session.run(frames=2)
        self.assertEqual(session.stats.records_received, 2)
        self.assertEqual(session.stats.events_injected, 2)
        methods = [c.method for c in session.display.calls]
        self.assertEqual(
            methods,
            [
                "NotifyPointerMotionAbsolute",
                "NotifyPointerButton",
                "NotifyPointerMotionAbsolute",
                "NotifyPointerButton",
            ],
        )

    def test_coordinates_reach_injection_from_fields_one_and_two(self):
        session = self.make_session(inbound=tlv7(10, 640, 480))
        session.run(frames=1)
        motion = session.display.calls[0]
        self.assertEqual(motion.args[1:], (640.0, 480.0))

    def test_a_non_type_seven_record_is_ignored_not_interpreted(self):
        other = bytes([3, 0, 0, 0x0C]) + bytes(12)
        session = self.make_session(inbound=other)
        session.run(frames=1)
        self.assertEqual(session.stats.records_received, 1)
        self.assertEqual(session.stats.events_injected, 0)
        self.assertEqual(session.stats.records_ignored, 1)
        self.assertEqual(session.display.calls, [])

    def test_a_meaningless_field0_injects_nothing(self):
        session = self.make_session(inbound=tlv7(1, 10, 10))
        session.run(frames=1)
        self.assertEqual(session.stats.records_received, 1)
        self.assertEqual(session.stats.events_injected, 0)
        self.assertEqual(session.stats.records_ignored, 1)

    def test_injection_can_be_disabled(self):
        session = self.make_session(inbound=tlv7(5, 1, 1), inject=False)
        session.run(frames=1)
        self.assertEqual(session.stats.records_received, 1)
        self.assertEqual(session.display.calls, [])
        self.assertEqual(session.stats.records_ignored, 1)

    def test_injection_is_withheld_until_the_stream_has_a_consumer(self):
        # Measured 2026-11-08: with no consumer, Mutter drops absolute motion
        # and still returns success, while buttons land at a stale pointer
        # position. Injecting anyway produces selected text and odd window
        # behaviour with a motionless pointer, so the host withholds instead.
        session = host.HostSession(
            source=host.ReplayFrameSource([b"x"]),
            display=FakeDisplay(stream_consumed=False),
        )
        session._socket = FakeSocket(tlv7(5, 100, 100))
        session.run(frames=1)
        self.assertEqual(session.stats.records_received, 1)
        self.assertEqual(session.stats.events_injected, 0)
        self.assertEqual(session.stats.records_dropped_no_consumer, 1)
        self.assertEqual(session.display.calls, [])

    def test_a_captured_frame_proves_a_consumer_and_enables_injection(self):
        class FakePipeWire(host.PipeWireFrameSource):
            def __init__(self):
                super().__init__(1)
                self.frames_captured = 1

            def next_payload(self):
                return b"\xff\xd8x\xff\xd9"

        display = FakeDisplay(stream_consumed=False)
        session = host.HostSession(source=FakePipeWire(), display=display)
        session._socket = FakeSocket(tlv7(10, 50, 60))
        session.run(frames=1)
        self.assertTrue(display.stream_consumed)
        self.assertEqual(session.stats.events_injected, 1)

    def test_running_without_a_connection_is_an_error(self):
        session = host.HostSession(source=host.ReplayFrameSource([b"x"]))
        with self.assertRaises(host.HostError):
            session.run(frames=1)

    def test_running_without_a_source_is_an_error(self):
        session = host.HostSession()
        session._socket = FakeSocket()
        with self.assertRaises(host.HostError):
            session.run(frames=1)

    def test_close_closes_the_socket(self):
        session = self.make_session()
        sock = session._socket
        session.close()
        self.assertTrue(sock.closed)
        self.assertIsNone(session._socket)


class TestSessionIsInert(unittest.TestCase):
    def test_construction_opens_nothing(self):
        session = host.HostSession()
        self.assertIsNone(session._socket)
        self.assertIsNone(session.client_dimensions)
        self.assertFalse(session.diff_jpeg)
        self.assertEqual(session.stats.frames_sent, 0)

    def test_the_device_id_is_discovered_not_assumed(self):
        # usbmuxd reassigns DeviceID on every attach, so hard-coding it works
        # for one session and fails with BADDEV on the next. Met live.
        session = host.HostSession()
        self.assertIsNone(session.device_id)
        self.assertEqual(session.devices_seen, [])
        self.assertEqual(session.fps, host.TARGET_FPS)

    def test_target_geometry_agrees_with_the_gnome_layer(self):
        self.assertEqual(
            (host.TARGET_WIDTH, host.TARGET_HEIGHT),
            (gnome.TARGET_WIDTH, gnome.TARGET_HEIGHT),
        )


class TestHandshakeRefusesDiffJpeg(unittest.TestCase):
    """The one protocol path the host must refuse rather than guess."""

    def test_diff_jpeg_would_be_refused(self):
        # The observed block (000000fd + zeros) is not valid JSON, so the gate
        # cannot pass and ordinary JPEG is selected. If a device ever did
        # enable it, guessing the differential format would be worse than
        # failing, since nothing is known about what it transmits.
        import hashi_startup as startup

        observed = (0xFD).to_bytes(4, "big") + bytes(8)
        self.assertFalse(startup.diff_jpeg_enabled(observed))
        self.assertTrue(startup.diff_jpeg_enabled(b'{"diff_jpeg": true}'))


if __name__ == "__main__":
    unittest.main()
