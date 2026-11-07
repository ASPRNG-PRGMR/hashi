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
