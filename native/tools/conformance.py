#!/usr/bin/env python3
"""Check that the C++ core emits exactly the bytes the Python one does.

The Python modules are the reference: they reproduced the captured
130,375,177-byte outgoing stream byte-for-byte and they are what drove the
device in FED-LIVE-E001 and FED-HOST-E001. A port is only correct if it
agrees with them on the wire, so this compares bytes rather than trusting
that two test suites assert similar things.

Two kinds of check run here:

* **Vectors** -- fixed byte strings both implementations build from the same
  inputs: the startup handshake, record framing, the usbmux header and the
  JPEG frame prelude.
* **Frames** -- whole JPEG frames, scan data included, encoded from identical
  pixel buffers. The Python side reaches libjpeg-turbo through Pillow and the
  C++ side through the TurboJPEG API, so this is the check that the entropy
  coder agrees and not merely that both link the same library. The fixtures are
  chosen to cover where two configurations of libjpeg *would* diverge: flat DC
  content, luma AC, heavy AC in all three components, chroma edges at
  single-pixel pitch, and sizes that are not a multiple of the 16-pixel MCU.

Usage:  python3 native/tools/conformance.py [path-to-dump_vectors]
Exits non-zero on any mismatch.
"""

from __future__ import annotations

import pathlib
import random
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
# The Python reference implementation lives in python/.
sys.path.insert(0, str(ROOT / "python"))

import hashi_jpeg as jpeg  # noqa: E402
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

    # --- JPEG frame prelude ------------------------------------------------
    put("jpeg_app0", jpeg.build_app0())
    put("jpeg_app0_density_72", jpeg.build_app0(72))
    put("jpeg_dqt_luma_q80", jpeg.build_dqt(jpeg.BASE_LUMA_QTABLE, 0, 80))
    put("jpeg_dqt_chroma_q80", jpeg.build_dqt(jpeg.BASE_CHROMA_QTABLE, 1, 80))
    put("jpeg_dqt_luma_q25", jpeg.build_dqt(jpeg.BASE_LUMA_QTABLE, 0, 25))
    put("jpeg_dqt_luma_q100", jpeg.build_dqt(jpeg.BASE_LUMA_QTABLE, 0, 100))
    put("jpeg_dqt_luma_q1", jpeg.build_dqt(jpeg.BASE_LUMA_QTABLE, 0, 1))
    put("jpeg_sof0_1280x960", jpeg.build_sof0(1280, 960))
    put("jpeg_sof0_odd", jpeg.build_sof0(17, 5))
    put("jpeg_dht_dc_luma",
        jpeg.build_dht(0, 0, jpeg.DC_LUMA_COUNTS, jpeg.DC_LUMA_VALUES))
    put("jpeg_dht_ac_luma",
        jpeg.build_dht(1, 0, jpeg.AC_LUMA_COUNTS, jpeg.AC_LUMA_VALUES))
    put("jpeg_dht_dc_chroma",
        jpeg.build_dht(0, 1, jpeg.DC_CHROMA_COUNTS, jpeg.DC_CHROMA_VALUES))
    put("jpeg_dht_ac_chroma",
        jpeg.build_dht(1, 1, jpeg.AC_CHROMA_COUNTS, jpeg.AC_CHROMA_VALUES))
    put("jpeg_sos", jpeg.build_sos())
    put("jpeg_prelude_observed", jpeg.build_prelude())
    put("jpeg_prelude_odd", jpeg.build_prelude(17, 5, 25, 72))
    return out


# ---------------------------------------------------------------------------
# Whole-frame fixtures
# ---------------------------------------------------------------------------
#
# Built here rather than stored, so nothing binary enters the repository. The
# pixels come from random.Random, whose Mersenne Twister sequence is
# reproducible for a given seed, so a fixture is the same on every machine.

W, H = jpeg.OBSERVED_WIDTH, jpeg.OBSERVED_HEIGHT


def _fixture_pixels(name: str, width: int, height: int) -> bytes:
    """Deterministic tightly packed 8-bit RGB for one fixture."""
    if name == "black":
        return bytes(width * height * 3)
    if name == "grey":
        return bytes([128]) * (width * height * 3)
    if name == "gradient":
        row = bytearray()
        for x in range(width):
            value = (x * 255) // max(width - 1, 1)
            row += bytes((value, value, value))
        return bytes(row) * height
    if name == "noise":
        return random.Random(1234).randbytes(width * height * 3)
    if name == "bars":
        # Eight colour bars, every other pixel halved: chroma edges at
        # single-pixel pitch, which is what 4:2:0 downsampling has to resolve.
        colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                   (0, 255, 255), (255, 0, 255), (255, 255, 255), (0, 0, 0)]
        rows = []
        for y in range(2):
            row = bytearray()
            for x in range(width):
                r, g, b = colours[(x * 8) // width]
                if (y + x) % 2 == 0:
                    r, g, b = r // 2, g // 2, b // 2
                row += bytes((r, g, b))
            rows.append(bytes(row))
        out = bytearray()
        for y in range(height):
            out += rows[y % 2]
        return bytes(out)
    raise AssertionError(f"unknown fixture {name}")


#: name, width, height, quality, density
FRAME_FIXTURES = [
    ("black", W, H, 80, 120),
    ("grey", W, H, 80, 120),
    ("gradient", W, H, 80, 120),
    ("noise", W, H, 80, 120),
    ("bars", W, H, 80, 120),
    # Not a multiple of the 16-pixel MCU in either axis: the two encoders must
    # pad the final block the same way.
    ("bars", 17, 5, 80, 120),
    ("gradient", 1, 1, 80, 120),
    # Proves quality and density are plumbed through, not just defaulted.
    ("gradient", W, H, 25, 72),
]


def compare_frames(dump_frame: pathlib.Path) -> list[str]:
    """Encode each fixture both ways and diff the bytes. Returns failures."""
    try:
        from PIL import Image
    except ImportError:
        return ["frames: Pillow is unavailable, so the reference cannot encode"]

    failures = []
    with tempfile.TemporaryDirectory() as workdir:
        raw = pathlib.Path(workdir) / "fixture.rgb"
        for name, width, height, quality, density in FRAME_FIXTURES:
            label = f"frame_{name}_{width}x{height}_q{quality}_d{density}"
            pixels = _fixture_pixels(name, width, height)
            raw.write_bytes(pixels)

            image = Image.frombytes("RGB", (width, height), pixels)
            if (quality, density) == (jpeg.OBSERVED_QUALITY,
                                      jpeg.OBSERVED_DENSITY):
                want = jpeg.encode_frame(image)
            else:
                import io
                buf = io.BytesIO()
                image.save(buf, "JPEG", quality=quality,
                           subsampling=jpeg.PILLOW_SUBSAMPLING_420,
                           dpi=(density, density))
                want = buf.getvalue()

            result = subprocess.run(
                [str(dump_frame), str(raw), str(width), str(height),
                 str(quality), str(density)],
                capture_output=True)
            if result.returncode != 0:
                failures.append(
                    f"{label}: dump_frame exited {result.returncode}: "
                    f"{result.stderr.decode(errors='replace').strip()}")
                continue
            got = result.stdout
            if got == want:
                continue
            if len(got) != len(want):
                failures.append(f"{label}: python {len(want)} bytes, "
                                f"c++ {len(got)} bytes")
            else:
                at = next(i for i, (a, b) in enumerate(zip(want, got))
                          if a != b)
                failures.append(f"{label}: {len(want)} bytes, first "
                                f"difference at offset {at}")
    return failures


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

    frame_binary = binary.parent / "dump_frame"
    if not frame_binary.exists():
        print(f"dump_frame not found at {frame_binary}\n"
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

    frame_failures = compare_frames(frame_binary)

    for line in failures + frame_failures:
        print("MISMATCH " + line)
    print(f"\n{len(expected)} vectors compared, {len(failures)} mismatches")
    print(f"{len(FRAME_FIXTURES)} frames compared, "
          f"{len(frame_failures)} mismatches")
    return 1 if (failures or frame_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
