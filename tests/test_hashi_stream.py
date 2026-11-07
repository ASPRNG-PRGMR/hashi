"""FED-STREAM-E001 tests.

The outbound assertions are tied to captured values. The inbound TLV assertions
describe statically decoded behaviour that has never been observed on the wire,
and are labelled as such so nobody later mistakes them for validated protocol.
"""

import unittest

from hashi_framing import parse_records
from hashi_startup import decode_header
from hashi_stream import (
    PACING_WRAP_MS,
    TIMEOUT_RECV_MS,
    TLV_HANDLED_TYPES,
    TLV_PAYLOAD_CLAMP,
    TLV_RING_SLOTS,
    TLV_SUBTYPE_70,
    TLV_SUBTYPE_VIDEO,
    TYPE_IMAGE,
    StreamError,
    encode_image_record,
    frame_interval_ms,
    pacing_sleep_ms,
    parse_tlv_record,
    tlv_payload_is_network_order,
    tlv_ring_slot,
)


class OutboundRecordTests(unittest.TestCase):
    def test_reproduces_the_first_captured_image_header(self):
        # docs/windows-startup-framing.md: first image header 06 00 4d 73,
        # followed by 19,827 payload bytes.
        record = encode_image_record(b"\xff" * 19827)
        self.assertEqual(record[:4], bytes.fromhex("06004d73"))
        self.assertEqual(len(record), 4 + 19827)

    def test_reproduces_the_captured_white_and_black_sample_sizes(self):
        # Selected white payloads were 26,568 bytes; black 26,408 and 26,180.
        for size in (26568, 26408, 26180):
            record = encode_image_record(b"\x00" * size)
            self.assertEqual(decode_header(record[:4]), (TYPE_IMAGE, size))

    def test_records_round_trip_through_the_existing_framing_parser(self):
        payloads = [b"\xff" * 19827, b"\x01" * 26568, b"\x02" * 26180]
        stream = b"".join(encode_image_record(p) for p in payloads)
        records = parse_records(stream)
        self.assertEqual([r.tag for r in records], [TYPE_IMAGE] * 3)
        self.assertEqual([r.payload for r in records], payloads)

    def test_empty_payload_is_refused(self):
        with self.assertRaises(StreamError):
            encode_image_record(b"")


class PacingTests(unittest.TestCase):
    def test_interval_truncates(self):
        self.assertEqual(frame_interval_ms(30), 33)   # 1000 // 30
        self.assertEqual(frame_interval_ms(60), 16)   # 1000 // 60
        self.assertEqual(frame_interval_ms(1), 1000)

    def test_sleeps_only_the_remainder(self):
        # 30 fps -> 33 ms target; 10 ms elapsed -> sleep 23 ms.
        self.assertEqual(pacing_sleep_ms(100, 110, 30), 23)

    def test_no_sleep_when_already_late(self):
        # Observed inter-frame intervals reached 51 ms, beyond a 33 ms target.
        self.assertEqual(pacing_sleep_ms(100, 151, 30), 0)
        self.assertEqual(pacing_sleep_ms(100, 133, 30), 0)

    def test_wraps_across_the_one_second_boundary(self):
        # 990 -> 10 ms is a 20 ms elapsed, not a negative one.
        self.assertEqual(pacing_sleep_ms(990, 10, 30), 13)
        self.assertEqual(PACING_WRAP_MS, 1000)

    def test_rejects_values_outside_a_wmilliseconds_field(self):
        for bad in ((1000, 10), (10, 1000), (-1, 10)):
            with self.assertRaises(StreamError):
                pacing_sleep_ms(bad[0], bad[1], 30)
        with self.assertRaises(StreamError):
            frame_interval_ms(0)


class InboundTlvTests(unittest.TestCase):
    """Statically decoded. Zero wire observations exist for any of this."""

    def test_only_types_3_and_7_are_handled(self):
        self.assertEqual(TLV_HANDLED_TYPES, (3, 7))
        for t in (3, 7):
            rec = parse_tlv_record(bytes([t, 0, 0, 12]), b"\x00" * 12)
            self.assertTrue(rec.handled)
        for t in (0, 1, 2, 4, 5, 6, 8, 255):
            rec = parse_tlv_record(bytes([t, 0, 0, 12]), b"\x00" * 12)
            self.assertFalse(rec.handled)

    def test_type_7_payload_is_big_endian_and_type_3_is_native(self):
        self.assertTrue(tlv_payload_is_network_order(7))
        self.assertFalse(tlv_payload_is_network_order(3))
        body = bytes.fromhex("00000071") + bytes.fromhex("00000500") + bytes.fromhex("000003c0")
        seven = parse_tlv_record(bytes([7, 0, 0, 12]), body)
        self.assertEqual((seven.field0, seven.field1, seven.field2), (0x71, 0x500, 0x3C0))
        three = parse_tlv_record(bytes([3, 0, 0, 12]), body)
        self.assertEqual(three.field0, 0x71000000)  # same bytes, native order

    def test_payload_is_clamped_to_twelve_bytes_not_rejected(self):
        rec = parse_tlv_record(bytes([7, 0, 0, 64]), b"\xaa" * 64)
        self.assertTrue(rec.truncated)
        self.assertEqual(rec.field0, 0xAAAAAAAA)
        short = parse_tlv_record(bytes([7, 0, 0, 4]), b"\x00\x00\x00\x71")
        self.assertFalse(short.truncated)
        self.assertEqual((short.field0, short.field1, short.field2), (0x71, 0, 0))

    def test_recognised_subtypes(self):
        self.assertEqual(TLV_SUBTYPE_VIDEO, 0x71)
        self.assertEqual(TLV_SUBTYPE_70, 0x70)

    def test_zero_length_and_short_payloads_are_errors(self):
        with self.assertRaises(StreamError):
            parse_tlv_record(bytes([7, 0, 0, 0]), b"")
        with self.assertRaises(StreamError):
            parse_tlv_record(bytes([7, 0, 0, 12]), b"\x00" * 8)

    def test_ring_is_sixty_four_slots(self):
        self.assertEqual(TLV_RING_SLOTS, 64)
        self.assertEqual(tlv_ring_slot(0), 0)
        self.assertEqual(tlv_ring_slot(63), 63)
        self.assertEqual(tlv_ring_slot(64), 0)
        self.assertEqual(tlv_ring_slot(130), 2)
        with self.assertRaises(StreamError):
            tlv_ring_slot(-1)

    def test_recv_timeout_constant(self):
        self.assertEqual(TIMEOUT_RECV_MS, 3000)

    def test_payload_clamp_constant(self):
        self.assertEqual(TLV_PAYLOAD_CLAMP, 12)


if __name__ == "__main__":
    unittest.main()


class InputDispatchTests(unittest.TestCase):
    """Statically decoded from the jump table at VA 0x4404f8. Never observed."""

    def test_table_covers_field0_one_through_seventeen(self):
        from hashi_stream import INPUT_DISPATCH_MAX, input_dispatch_target
        self.assertEqual(INPUT_DISPATCH_MAX, 17)
        for f in range(1, 18):
            self.assertIsNotNone(input_dispatch_target(f))
        for f in (0, 18, 0x70, 0x71, 255):
            self.assertIsNone(input_dispatch_target(f))

    def test_keyboard_pair_shares_one_target(self):
        from hashi_stream import input_dispatch_target
        self.assertEqual(input_dispatch_target(1), input_dispatch_target(2))
        self.assertEqual(input_dispatch_target(1), 0x40132)

    def test_in_range_but_ignored_values_reach_the_epilogue(self):
        from hashi_stream import (
            INPUT_DISPATCH_EPILOGUE,
            INPUT_IGNORED,
            input_dispatch_target,
            input_is_acted_on,
        )
        self.assertEqual(INPUT_IGNORED, (3, 11, 12, 13))
        for f in INPUT_IGNORED:
            self.assertEqual(input_dispatch_target(f), INPUT_DISPATCH_EPILOGUE)
            self.assertFalse(input_is_acted_on(f))

    def test_six_adjacent_stubs_are_seven_bytes_apart(self):
        # 5, 6, 8, 9, 14, 15 land on consecutive 7-byte stubs that feed a
        # shared path, consistent with button down/up pairs. Which button is
        # which is NOT established.
        from hashi_stream import input_dispatch_target
        stubs = [input_dispatch_target(f) for f in (5, 6, 8, 9, 14, 15)]
        self.assertEqual(stubs, sorted(stubs))
        self.assertEqual({b - a for a, b in zip(stubs, stubs[1:])}, {7})

    def test_pairs_sharing_a_target(self):
        from hashi_stream import input_dispatch_target
        self.assertEqual(input_dispatch_target(4), input_dispatch_target(7))
        self.assertEqual(input_dispatch_target(16), input_dispatch_target(17))

    def test_win32_input_size(self):
        from hashi_stream import WIN32_INPUT_SIZE
        self.assertEqual(WIN32_INPUT_SIZE, 28)


class ReconfigVideoTests(unittest.TestCase):
    """Decoded from instructions; never observed on the wire."""

    def test_carries_the_output_dimensions_big_endian(self):
        from hashi_stream import encode_reconfig_video
        record = encode_reconfig_video(1280, 960)
        self.assertEqual(record, bytes.fromhex("0500000c" "00000001" "00000500" "000003c0"))

    def test_transpose_flag_swaps_the_pair(self):
        from hashi_stream import encode_reconfig_video
        self.assertEqual(
            encode_reconfig_video(1280, 960, transposed=True),
            bytes.fromhex("0500000c" "00000001" "000003c0" "00000500"),
        )

    def test_shares_field0_with_the_startup_hello(self):
        # HELLO is the same record shape with zero dimensions, which is why
        # field0 = 1 reads as "host video config" and 2 as "client".
        from hashi_startup import MSG_HELLO, encode_control
        from hashi_stream import MSG_VIDEO_CONFIG, encode_reconfig_video
        self.assertEqual(MSG_VIDEO_CONFIG, MSG_HELLO)
        hello = encode_control(MSG_HELLO)
        reconfig = encode_reconfig_video(1280, 960)
        self.assertEqual(hello[:8], reconfig[:8])  # header + field0 identical

    def test_rejects_non_positive_dimensions(self):
        from hashi_stream import encode_reconfig_video
        for w, h in ((0, 960), (1280, 0), (-1280, 960)):
            with self.assertRaises(StreamError):
                encode_reconfig_video(w, h)


class InputEventKindTests(unittest.TestCase):
    """Statically decoded from CInput / handler 0x440110. Never observed."""

    def test_button_constants_match_documented_win32_values(self):
        # The decisive check: the six stubs set exactly the Win32 MOUSEEVENTF
        # button constants, in down/up order. That is why this is Fact and not
        # a guess.
        from hashi_stream import (
            MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
            MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP,
            MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
            MOUSE_BUTTON_FLAGS,
        )
        self.assertEqual(MOUSE_BUTTON_FLAGS, {
            5: MOUSEEVENTF_LEFTDOWN,    # 0x02
            6: MOUSEEVENTF_LEFTUP,      # 0x04
            8: MOUSEEVENTF_RIGHTDOWN,   # 0x08
            9: MOUSEEVENTF_RIGHTUP,     # 0x10
            14: MOUSEEVENTF_MIDDLEDOWN, # 0x20
            15: MOUSEEVENTF_MIDDLEUP,   # 0x40
        })
        self.assertEqual(sorted(MOUSE_BUTTON_FLAGS.values()),
                         [0x02, 0x04, 0x08, 0x10, 0x20, 0x40])

    def test_stub_values_are_consecutive_powers_of_two(self):
        from hashi_stream import MOUSE_BUTTON_FLAGS
        vals = sorted(MOUSE_BUTTON_FLAGS.values())
        self.assertEqual([b // a for a, b in zip(vals, vals[1:])], [2, 2, 2, 2, 2])

    def test_move_flags_are_move_virtualdesk_absolute(self):
        from hashi_stream import (
            MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_MOVE, MOUSEEVENTF_VIRTUALDESK,
            MOUSE_MOVE_FLAGS,
        )
        self.assertEqual(MOUSE_MOVE_FLAGS, 0xC001)
        self.assertEqual(
            MOUSE_MOVE_FLAGS,
            MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE,
        )

    def test_movement_only_values_carry_no_button_flag(self):
        from hashi_stream import MOUSE_MOVE_ONLY, mouse_flags_for
        self.assertEqual(MOUSE_MOVE_ONLY, (4, 7))
        for f in MOUSE_MOVE_ONLY:
            self.assertEqual(mouse_flags_for(f), 0)

    def test_non_mouse_values_have_no_flags(self):
        from hashi_stream import mouse_flags_for
        for f in (1, 2, 3, 10, 11, 16, 17, 0x70, 0x71, 99):
            self.assertIsNone(mouse_flags_for(f))

    def test_every_field0_classifies(self):
        from hashi_stream import input_kind
        expected = {
            1: "keyboard", 2: "keyboard",
            3: "ignored", 11: "ignored", 12: "ignored", 13: "ignored",
            4: "mouse-move", 7: "mouse-move",
            5: "mouse-button", 6: "mouse-button", 8: "mouse-button",
            9: "mouse-button", 14: "mouse-button", 15: "mouse-button",
            10: "other",
            16: "control-message", 17: "control-message",
        }
        for f, kind in expected.items():
            self.assertEqual(input_kind(f), kind, f"field0={f}")
        for f in (0, 18, 0x70, 0x71):
            self.assertEqual(input_kind(f), "out-of-range")

    def test_absolute_range_is_the_decoded_constant(self):
        from hashi_stream import ABSOLUTE_COORD_MAX, normalise_absolute
        self.assertEqual(ABSOLUTE_COORD_MAX, 65535)
        self.assertEqual(normalise_absolute(0, 1280), 0)
        self.assertEqual(normalise_absolute(1280, 1280), 65535)
        self.assertEqual(normalise_absolute(640, 1280), 32767)

    def test_normalise_rejects_out_of_range(self):
        from hashi_stream import normalise_absolute
        with self.assertRaises(StreamError):
            normalise_absolute(-1, 1280)
        with self.assertRaises(StreamError):
            normalise_absolute(1281, 1280)
        with self.assertRaises(StreamError):
            normalise_absolute(0, 0)

    def test_touch_is_a_separate_api_not_sendinput(self):
        from hashi_stream import TOUCH_INJECTION_SYMBOLS
        self.assertEqual(
            TOUCH_INJECTION_SYMBOLS,
            ("InitializeTouchInjection", "InjectTouchInput"),
        )
