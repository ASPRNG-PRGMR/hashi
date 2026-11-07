"""FED-USBMUX-E001 tests. Values are those observed in the captured exchange."""

import socket
import unittest

from hashi_usbmux import (
    APPLICATION_PORT,
    LINUX_USBMUXD_SOCKET,
    OBSERVED_CLIENT_VERSION_STRING,
    OBSERVED_LIBUSBMUX_VERSION,
    OBSERVED_PROG_NAME,
    USBMUX_HEADER_LEN,
    USBMUX_MESSAGE_PLIST,
    USBMUX_VERSION_PLIST,
    UsbmuxError,
    build_connect,
    build_list_devices,
    decode_header,
    decode_message,
    encode_message,
    htons_port,
    parse_result,
    result_is_success,
)


class PortSwapTests(unittest.TestCase):
    def test_application_port_becomes_the_captured_value(self):
        # The capture carried PortNumber 34074 for application port 6789.
        self.assertEqual(APPLICATION_PORT, 6789)
        self.assertEqual(htons_port(6789), 34074)
        self.assertEqual(0x1A85, 6789)
        self.assertEqual(0x851A, 34074)

    def test_swap_is_its_own_inverse(self):
        for p in (1, 80, 6789, 27015, 65535):
            self.assertEqual(socket.ntohs(htons_port(p)), p)

    def test_rejects_out_of_range_ports(self):
        for p in (0, -1, 65536):
            with self.assertRaises(UsbmuxError):
                htons_port(p)


class HeaderTests(unittest.TestCase):
    def test_header_fields_match_the_observed_shape(self):
        msg = encode_message({"MessageType": "ListDevices"}, 7)
        length, version, message, tag = decode_header(msg[:USBMUX_HEADER_LEN])
        self.assertEqual(length, len(msg))        # length includes the header
        self.assertEqual(version, USBMUX_VERSION_PLIST)
        self.assertEqual(message, USBMUX_MESSAGE_PLIST)
        self.assertEqual(tag, 7)
        self.assertEqual((USBMUX_VERSION_PLIST, USBMUX_MESSAGE_PLIST), (1, 8))

    def test_header_is_little_endian(self):
        msg = encode_message({"MessageType": "ListDevices"}, 0x0E)
        self.assertEqual(msg[4:8], (1).to_bytes(4, "little"))
        self.assertEqual(msg[8:12], (8).to_bytes(4, "little"))
        self.assertEqual(msg[12:16], (0x0E).to_bytes(4, "little"))

    def test_rejects_malformed_headers(self):
        for bad in (b"", b"\x00" * 15, b"\x00" * 17):
            with self.assertRaises(UsbmuxError):
                decode_header(bad)
        # A length shorter than the header itself.
        with self.assertRaises(UsbmuxError):
            decode_header((4).to_bytes(4, "little") + b"\x00" * 12)


class MessageTests(unittest.TestCase):
    def test_connect_round_trips_with_the_swapped_port(self):
        msg = build_connect(1, APPLICATION_PORT, bundle_id="com.example.app")
        tag, payload = decode_message(msg)
        self.assertEqual(tag, 14)
        self.assertEqual(payload["MessageType"], "Connect")
        self.assertEqual(payload["DeviceID"], 1)
        self.assertEqual(payload["PortNumber"], 34074)
        self.assertEqual(payload["BundleID"], "com.example.app")

    def test_connect_identifies_the_client_as_observed(self):
        _, payload = decode_message(build_connect(1))
        self.assertEqual(payload["ClientVersionString"], OBSERVED_CLIENT_VERSION_STRING)
        self.assertEqual(payload["ProgName"], OBSERVED_PROG_NAME)
        self.assertEqual(payload["kLibUSBMuxVersion"], OBSERVED_LIBUSBMUX_VERSION)
        self.assertEqual(OBSERVED_PROG_NAME, "libusbmuxd")
        self.assertEqual(OBSERVED_LIBUSBMUX_VERSION, 3)

    def test_bundle_id_is_optional(self):
        _, payload = decode_message(build_connect(1))
        self.assertNotIn("BundleID", payload)

    def test_list_devices_round_trips(self):
        tag, payload = decode_message(build_list_devices(3))
        self.assertEqual(tag, 3)
        self.assertEqual(payload["MessageType"], "ListDevices")

    def test_rejects_wrong_version_or_message_type(self):
        good = build_list_devices(1)
        bad_version = good[:4] + (2).to_bytes(4, "little") + good[8:]
        with self.assertRaises(UsbmuxError):
            decode_message(bad_version)
        bad_message = good[:8] + (1).to_bytes(4, "little") + good[12:]
        with self.assertRaises(UsbmuxError):
            decode_message(bad_message)

    def test_rejects_truncated_message(self):
        good = build_list_devices(1)
        with self.assertRaises(UsbmuxError):
            decode_message(good[:-10])

    def test_rejects_bad_tag_and_device_id(self):
        with self.assertRaises(UsbmuxError):
            encode_message({"MessageType": "ListDevices"}, 1 << 33)
        with self.assertRaises(UsbmuxError):
            build_connect(-1)


class ResultTests(unittest.TestCase):
    def test_zero_is_success(self):
        self.assertEqual(parse_result({"MessageType": "Result", "Number": 0}), 0)
        self.assertTrue(result_is_success({"MessageType": "Result", "Number": 0}))

    def test_nonzero_parses_but_is_not_success(self):
        self.assertEqual(parse_result({"MessageType": "Result", "Number": 3}), 3)
        self.assertFalse(result_is_success({"MessageType": "Result", "Number": 3}))

    def test_rejects_non_result_and_missing_number(self):
        with self.assertRaises(UsbmuxError):
            parse_result({"MessageType": "Connect"})
        with self.assertRaises(UsbmuxError):
            parse_result({"MessageType": "Result"})
        with self.assertRaises(UsbmuxError):
            parse_result({"MessageType": "Result", "Number": "0"})


class SafetyTests(unittest.TestCase):
    def test_socket_path_is_recorded_but_unused(self):
        # The module must not connect to anything; it only names the path.
        self.assertEqual(LINUX_USBMUXD_SOCKET, "/var/run/usbmuxd")
        import hashi_usbmux
        with open(hashi_usbmux.__file__, encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in (".connect(", "socket.socket(", "socket.create_connection"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
