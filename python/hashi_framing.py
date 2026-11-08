"""Parser for the application record boundary observed in WIN-START-E005.

This module assigns no meaning to non-JPEG tags or to record payloads.
"""

from dataclasses import dataclass


class FramingError(ValueError):
    pass


@dataclass(frozen=True)
class Record:
    offset: int
    tag: int
    payload: bytes


def parse_records(data: bytes) -> list[Record]:
    records = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 4:
            raise FramingError(f"truncated header at offset {offset}")
        length = int.from_bytes(data[offset + 1:offset + 4], "big")
        end = offset + 4 + length
        if end > len(data):
            raise FramingError(f"truncated payload at offset {offset}")
        records.append(Record(offset, data[offset], data[offset + 4:end]))
        offset = end
    return records


def jpeg_baseline_size(payload: bytes) -> tuple[int, int]:
    """Check SOI, EOI and an 8-bit, three-component SOF0 boundary."""
    if len(payload) < 8 or payload[:2] != b"\xff\xd8" or payload[-2:] != b"\xff\xd9":
        raise FramingError("missing JPEG SOI or EOI")
    pos = 2
    dimensions = None
    while pos < len(payload) - 2:
        if payload[pos] != 0xff:
            raise FramingError("invalid JPEG marker boundary")
        while pos < len(payload) and payload[pos] == 0xff:
            pos += 1
        if pos >= len(payload):
            break
        marker = payload[pos]
        pos += 1
        if marker == 0xda:  # Entropy-coded data; EOI is checked above.
            break
        if marker in (0x01, *range(0xd0, 0xd8)):
            continue
        if pos + 2 > len(payload) - 2:
            raise FramingError("truncated JPEG segment length")
        size = int.from_bytes(payload[pos:pos + 2], "big")
        if size < 2 or pos + size > len(payload) - 2:
            raise FramingError("invalid JPEG segment length")
        if marker == 0xc0:
            segment = payload[pos + 2:pos + size]
            if len(segment) < 6 or segment[0] != 8 or segment[5] != 3 or size != 17:
                raise FramingError("unexpected SOF0 structure")
            dimensions = (int.from_bytes(segment[3:5], "big"),
                          int.from_bytes(segment[1:3], "big"))
        pos += size
    if dimensions is None or min(dimensions) <= 0:
        raise FramingError("missing valid SOF0")
    return dimensions
