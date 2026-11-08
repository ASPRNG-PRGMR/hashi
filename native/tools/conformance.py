#!/usr/bin/env python3
"""Check that the C++ core emits exactly the bytes the Python one does.

The Python modules are the reference: they reproduced the captured
130,375,177-byte outgoing stream byte-for-byte and they are what drove the
device in FED-LIVE-E001 and FED-HOST-E001. A port is only correct if it
agrees with them on the wire, so this compares bytes rather than trusting
that two test suites assert similar things.

Usage:  python3 native/tools/conformance.py [path-to-dump_vectors]
Exits non-zero on any mismatch.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
# The Python reference implementation lives in python/.
sys.path.insert(0, str(ROOT / "python"))

import hashi_startup as startup  # noqa: E402
import hashi_stream as stream  # noqa: E402
import hashi_usbmux as usbmux  # noqa: E402


def reference() -> dict[str, str]:
    """The same vectors dump_vectors.cpp emits, built with the Python core."""
    out: dict[str, str] = {}

    def put(name: str, data: bytes) -> None:
        out[name] = data.hex()

    put("probe", startup.encode_byte_order_probe())
    put("hello", startup.encode_control(startup.MSG_HELLO))
    put("ready", startup.encode_control(startup.MSG_READY))
    put("extra_request",
        startup.encode_control(startup.MSG_EXTRA_REQUEST, 5, raw_field1=True))
    put("hello_ack_2048x1536",
        startup.encode_control(startup.MSG_HELLO_ACK, 2048, 1536))
    put("ready_ack", startup.encode_control(startup.MSG_READY_ACK))
    put("legacy_hello",
        startup.encode_control(startup.MSG_HELLO, network_order=False))
    put("header_5_12", startup.encode_header(5, 12))
    put("header_6_19827", startup.encode_header(6, 19827))
    put("header_6_max", startup.encode_header(6, 0xFFFFFF))

    put("image_record_small",
        stream.encode_image_record(bytes([0xFF, 0xD8, 0xFF, 0xD9])))
    put("image_record_1000_head",
        stream.encode_image_record(bytes([0xAB]) * 1000)[:8])

    put("connect_header_tail", usbmux.build_connect(1)[4:16])

    out["port_swapped"] = str(usbmux.htons_port(usbmux.APPLICATION_PORT))
    out["align_2048"] = str(startup.align_client_dimension(2048))
    out["align_1"] = str(startup.align_client_dimension(1))
    out["align_5"] = str(startup.align_client_dimension(5))
    out["interval_30"] = str(stream.frame_interval_ms(30))
    out["interval_60"] = str(stream.frame_interval_ms(60))
    return out


def main() -> int:
    binary = (
        pathlib.Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "native" / "build" / "dump_vectors"
    )
    if not binary.exists():
        print(f"dump_vectors not found at {binary}\n"
              f"build it:  cmake -S native -B native/build && "
              f"cmake --build native/build")
        return 2

    result = subprocess.run([str(binary)], capture_output=True, text=True,
                            check=True)
    native: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, _, value = line.partition(" ")
        native[name] = value

    expected = reference()
    failures = []
    for name, want in sorted(expected.items()):
        got = native.get(name)
        if got is None:
            failures.append(f"{name}: missing from the C++ output")
        elif got != want:
            failures.append(f"{name}:\n    python {want}\n    c++    {got}")

    extra = sorted(set(native) - set(expected))
    for name in extra:
        failures.append(f"{name}: emitted by C++ but not by the reference")

    for line in failures:
        print("MISMATCH " + line)
    print(f"\n{len(expected)} vectors compared, {len(failures)} mismatches")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
