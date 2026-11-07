"""FED-START-E001 tests.

The fixtures are the exact application bytes of the captured WIN-START-E002
startup exchange, already published in docs/windows-startup-framing.md. The
decisive tests are the two round-trips: the codec must reproduce the captured
outgoing stream byte-for-byte and parse the captured incoming stream.
"""

import unittest

from hashi_startup import (
    CONTROL_RECORD_LEN,
    MSG_EXTRA_ACK,
    MSG_EXTRA_REQUEST,
    MSG_HELLO,
    MSG_HELLO_ACK,
    MSG_READY,
    MSG_READY_ACK,
    TYPE_CONTROL,
    TYPE_CONTROL_LEGACY,
    StartupError,
    align_client_dimension,
    decode_control,
    decode_header,
    encode_byte_order_probe,
    encode_control,
    encode_header,
    extra_data_length,
    host_startup_sequence,
    parse_hello_ack,
    parse_ready_ack,
    probe_reply_accepted,
)

# Captured host -> device application bytes, offset 592 of the generation-3
# outgoing stream (SHA-256 a49231917dd16a7a08c0bbf2e09adf23464740c91a1379e22befa08c7710da64).
CAPTURED_OUT = bytes.fromhex(
    "04000000"
    "0500000c" "00000001" "00000000" "00000000"
    "0500000c" "000000fe" "00000000" "00000000"
    "0500000c" "000000fc" "05000000" "00000000"
)

# Captured device -> host application bytes, offset 294 of the generation-3
# incoming stream (SHA-256 6bd0d76200a1e893f2604866b0c7d611f868494eb9b0df9eead2010b31108c51).
CAPTURED_IN = bytes.fromhex(
    "04000000"
    "0500000c" "00000002" "00000800" "00000600"
    "0500000c" "000000ff" "00000000" "00000000"
    "0500000c" "000000fd" "00000000" "00000000"
)


class ByteExactRoundTripTests(unittest.TestCase):
    """The reason this module exists: reproduce the capture without a device."""

    def test_host_sequence_reproduces_captured_outgoing_stream(self):
        self.assertEqual(b"".join(host_startup_sequence()), CAPTURED_OUT)

    def test_each_outgoing_message_matches_its_captured_slice(self):
        expected = [
            CAPTURED_OUT[0:4],
            CAPTURED_OUT[4:20],
            CAPTURED_OUT[20:36],
            CAPTURED_OUT[36:52],
        ]
        self.assertEqual(host_startup_sequence(), expected)

    def test_captured_incoming_stream_parses_exactly(self):
        probe, rest = CAPTURED_IN[:4], CAPTURED_IN[4:]
        self.assertTrue(probe_reply_accepted(probe))
        records = [rest[i:i + CONTROL_RECORD_LEN]
                   for i in range(0, len(rest), CONTROL_RECORD_LEN)]
        self.assertEqual(len(records), 3)
        # Reply 1 is the HELLO ACK and carries the client dimensions.
        self.assertEqual(parse_hello_ack(records[0]), (2048, 1536))
        # Reply 2 is the READY ACK.
        self.assertIsNone(parse_ready_ack(records[1]))
        # Reply 3 closes the exchange.
        self.assertEqual(decode_control(records[2]).field0, MSG_EXTRA_ACK)

    def test_no_bytes_are_left_over_in_either_direction(self):
        self.assertEqual(len(CAPTURED_OUT), 4 + 3 * CONTROL_RECORD_LEN)
        self.assertEqual(len(CAPTURED_IN), 4 + 3 * CONTROL_RECORD_LEN)


class HeaderTests(unittest.TestCase):
    def test_header_is_type_byte_then_be24_length(self):
        self.assertEqual(encode_header(TYPE_CONTROL, 12), bytes.fromhex("0500000c"))
        self.assertEqual(decode_header(bytes.fromhex("0500000c")), (TYPE_CONTROL, 12))

    def test_matches_the_first_captured_image_header(self):
        # docs/windows-startup-framing.md records the first image header as
        # 06 00 4d 73 followed by 19,827 payload bytes.
        self.assertEqual(decode_header(bytes.fromhex("06004d73")), (6, 19827))
        self.assertEqual(encode_header(6, 19827), bytes.fromhex("06004d73"))

    def test_round_trip_over_the_full_24_bit_range(self):
        for length in (0, 1, 12, 19827, 0xFFFF, 0xFFFFFF):
            self.assertEqual(decode_header(encode_header(5, length)), (5, length))

    def test_rejects_out_of_range_and_malformed(self):
        with self.assertRaises(StartupError):
            encode_header(0x100, 0)
        with self.assertRaises(StartupError):
            encode_header(5, 0x1000000)
        for bad in (b"", b"\x05", b"\x05\x00\x00\x0c\x00"):
            with self.assertRaises(StartupError):
                decode_header(bad)


class ControlRecordTests(unittest.TestCase):
    def test_fields_are_big_endian_in_network_order_mode(self):
        self.assertEqual(
            encode_control(MSG_HELLO), bytes.fromhex("0500000c000000010000000000000000")
        )

    def test_legacy_fallback_uses_type_1_and_native_order(self):
        # Reached when the byte-order probe fails: ebx = 1 at RVA 0x30539.
        record = encode_control(MSG_HELLO, network_order=False)
        self.assertEqual(record[0], TYPE_CONTROL_LEGACY)
        self.assertEqual(record[4:8], (1).to_bytes(4, "little"))

    def test_raw_field1_reproduces_the_agents_mixed_endianness(self):
        # This is the captured 0xfc record: field0 big-endian, field1 little.
        record = encode_control(MSG_EXTRA_REQUEST, 5, raw_field1=True)
        self.assertEqual(record, CAPTURED_OUT[36:52])
        self.assertEqual(record[4:8], (0xFC).to_bytes(4, "big"))
        self.assertEqual(record[8:12], (5).to_bytes(4, "little"))

    def test_without_raw_field1_the_bytes_would_not_match_the_capture(self):
        # Guards against "fixing" the vendor's inconsistency and silently
        # diverging from observed behaviour.
        self.assertNotEqual(
            encode_control(MSG_EXTRA_REQUEST, 5), CAPTURED_OUT[36:52]
        )

    def test_rejects_wrong_size_and_wrong_payload_length(self):
        with self.assertRaises(StartupError):
            decode_control(b"\x05\x00\x00\x0c" + b"\x00" * 8)
        with self.assertRaises(StartupError):
            decode_control(b"\x05\x00\x00\x08" + b"\x00" * 12)
        with self.assertRaises(StartupError):
            encode_control(0x1_0000_0000)


class ProbeAndAckTests(unittest.TestCase):
    def test_probe_is_a_little_endian_dword_four(self):
        self.assertEqual(encode_byte_order_probe(), bytes.fromhex("04000000"))

    def test_only_byte_zero_of_the_probe_reply_is_checked(self):
        # RVA 0x304d2 compares one byte; the other three are not examined.
        self.assertTrue(probe_reply_accepted(b"\x04\xde\xad\xbe"))
        self.assertFalse(probe_reply_accepted(b"\x05\x00\x00\x00"))
        self.assertFalse(probe_reply_accepted(b""))

    def test_wrong_ack_types_are_rejected_with_the_agents_wording(self):
        with self.assertRaises(StartupError) as cm:
            parse_hello_ack(encode_control(MSG_READY_ACK))
        self.assertIn("hello ack unknown type", str(cm.exception))
        with self.assertRaises(StartupError) as cm:
            parse_ready_ack(encode_control(MSG_HELLO_ACK))
        self.assertIn("ready ack unknown type", str(cm.exception))


class ClientDimensionAlignmentTests(unittest.TestCase):
    def test_observed_values_pass_through_unchanged(self):
        self.assertEqual(align_client_dimension(2048), 2048)
        self.assertEqual(align_client_dimension(1536), 1536)

    def test_formula_is_not_a_plain_round_up(self):
        # ((v-1) & ~3) + 4 leaves exact multiples of 4 alone and rounds the rest up.
        self.assertEqual(align_client_dimension(1), 4)
        self.assertEqual(align_client_dimension(4), 4)
        self.assertEqual(align_client_dimension(5), 8)
        self.assertEqual(align_client_dimension(1279), 1280)
        self.assertEqual(align_client_dimension(1280), 1280)

    def test_rejects_non_positive(self):
        for bad in (0, -4):
            with self.assertRaises(StartupError):
                align_client_dimension(bad)


class ExtraDataTests(unittest.TestCase):
    def test_length_comes_from_the_be24_field(self):
        self.assertEqual(extra_data_length(bytes.fromhex("0500000c")), 12)

    def test_zero_length_is_the_agents_failure_case(self):
        with self.assertRaises(StartupError) as cm:
            extra_data_length(bytes.fromhex("05000000"))
        self.assertIn("recv extra data length failed", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
