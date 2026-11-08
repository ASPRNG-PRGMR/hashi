import unittest

from hashi_framing import FramingError, jpeg_baseline_size, parse_records


class FramingTests(unittest.TestCase):
    def test_observed_boundary_shape(self):
        jpeg = bytes.fromhex("ffd8ffc000110803c0050003011100021100031100ffda0008010100003f00d9ffd9")
        stream = b"\x04\x00\x00\x00" + b"\x06" + len(jpeg).to_bytes(3, "big") + jpeg
        records = parse_records(stream)
        self.assertEqual([(r.offset, r.tag) for r in records], [(0, 4), (4, 6)])
        self.assertEqual(jpeg_baseline_size(records[1].payload), (1280, 960))

    def test_truncation(self):
        for stream in (b"\x04", b"\x06\x00\x00\x03\xff"):
            with self.assertRaises(FramingError):
                parse_records(stream)

    def test_jpeg_boundary(self):
        with self.assertRaises(FramingError):
            jpeg_baseline_size(b"\xff\xd8\xff\xd9")


if __name__ == "__main__":
    unittest.main()
