#!/usr/bin/env python3
"""Check that the ports emit exactly the bytes the Python reference does.

The Python modules are the reference: they reproduced the captured
130,375,177-byte outgoing stream byte-for-byte and they are what drove the
device in FED-LIVE-E001 and FED-HOST-E001. A port is only correct if it
agrees with them on the wire, so this compares bytes rather than trusting
that several test suites assert similar things.

There are two ports: the C++17 core in `native/` and the Rust core in
`rust/`. Three implementations agreeing on bytes is worth far more than three
test suites, because a test asserts what its author believed while an
independent implementation landing on the same bytes is evidence the decode
itself is right. The Rust core is checked against the same vector set; it is
skipped with a message, not a failure, if it has not been built.

Two kinds of check run here:

* **Vectors** -- fixed byte strings both implementations build from the same
  inputs: the startup handshake, record framing, the usbmux header and the
  JPEG frame prelude. The Mutter D-Bus arguments and injection plans are
  compared here too, as a canonical text form: GLib builds the actual message,
  so what has to agree is the signatures, keys, defaults and values. That is
  where a port degrades quietly -- a uint32 cursor mode sent as an int32, or a
  default that drifts away from the verified contract.
* **Variants** -- the actual GVariant payloads, printed by GLib itself. The
  canonical vectors check that both implementations *decide* on the same
  signatures and values; these check the decision survives contact with GLib,
  so a difference is a real difference in the message that would go on the bus.
  Building a variant creates no session and makes no D-Bus call.
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

import hashi_gnome as gnome  # noqa: E402
import hashi_host as host  # noqa: E402
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

    # --- Mutter D-Bus arguments -------------------------------------------
    # Not named `stream`: that is the hashi_stream module in this scope.
    stream_path = "/org/gnome/Mutter/ScreenCast/Stream/u0"
    out["gnome_mode_default"] = _canonical_dict(gnome.virtual_monitor_mode())
    out["gnome_mode_no_refresh"] = _canonical_dict(
        gnome.virtual_monitor_mode(1280, 960, None))
    out["gnome_mode_custom"] = _canonical_dict(
        gnome.virtual_monitor_mode(640, 480, 59.94, is_preferred=False))

    out["gnome_record_virtual_default"] = _canonical_dict(
        gnome.record_virtual_properties())
    out["gnome_record_virtual_cursor_hidden"] = _canonical_dict(
        gnome.record_virtual_properties(cursor_mode=gnome.CURSOR_MODE_HIDDEN))
    out["gnome_record_virtual_platform_true"] = _canonical_dict(
        gnome.record_virtual_properties(is_platform=True))
    out["gnome_record_virtual_platform_false"] = _canonical_dict(
        gnome.record_virtual_properties(is_platform=False))

    out["gnome_session_props_empty"] = _canonical_dict(
        gnome.screen_cast_session_properties())
    out["gnome_session_props_id"] = _canonical_dict(
        gnome.screen_cast_session_properties("17"))
    out["gnome_session_props_both"] = _canonical_dict(
        gnome.screen_cast_session_properties("17", disable_animations=True))

    def plan(name: str, field0: int, x: int, y: int) -> None:
        out[name] = _canonical_plan(
            gnome.plan_injection(field0, x, y, stream_path=stream_path))

    plan("gnome_inject_down", 5, 100, 200)
    plan("gnome_inject_up", 6, 100, 200)
    plan("gnome_inject_motion", 10, 640, 480)
    plan("gnome_inject_right_down", 8, 1, 2)
    plan("gnome_inject_right_up", 9, 1, 2)
    plan("gnome_inject_middle_down", 14, 3, 4)
    plan("gnome_inject_middle_up", 15, 3, 4)
    plan("gnome_inject_move_only_4", 4, 5, 6)
    plan("gnome_inject_move_only_7", 7, 5, 6)
    plan("gnome_inject_origin", 10, 0, 0)
    plan("gnome_inject_corner", 10, 1280, 960)
    plan("gnome_inject_keyboard_1", 1, 10, 10)
    plan("gnome_inject_keyboard_2", 2, 10, 10)
    plan("gnome_inject_control_16", 16, 10, 10)
    plan("gnome_inject_control_17", 17, 10, 10)
    plan("gnome_inject_unseen_11", 11, 10, 10)

    # --- Capture pipeline -------------------------------------------------
    out["pipeline_default"] = host.capture_pipeline_description(42)
    out["pipeline_custom"] = host.capture_pipeline_description(0, 640, 480, 60)

    # --- Frame pacing -----------------------------------------------------
    # A scripted clock on both sides, so the schedule arithmetic is what is
    # compared rather than wall-clock behaviour.
    script = [0.0, 0.010, 0.033, 0.040, 1.0, 1.0, 1.033, 1.040]
    for fps in (30, 60):
        ticks = iter(script)
        last = [script[-1]]

        def clock(ticks=ticks, last=last):
            try:
                return next(ticks)
            except StopIteration:
                return last[0]

        pacer = host.Pacer(fps, now=clock)
        out[f"pacer_schedule_{fps}"] = ",".join(
            f"{pacer.sleep_s():.6f}" for _ in script)
    return out


# ---------------------------------------------------------------------------
# Canonical rendering of D-Bus arguments
# ---------------------------------------------------------------------------
#
# Must match hashi::gnome::canonical exactly. Doubles use %.6f because Python
# and C++ disagree about how to print a float, and that disagreement would
# otherwise read as a protocol difference.


def _canonical_value(signature: str, value: object) -> str:
    if signature == "b":
        return "b:" + ("true" if value else "false")
    if signature == "u":
        return f"u:{value}"
    if signature == "i":
        return f"i:{value}"
    if signature == "d":
        return f"d:{float(value):.6f}"
    if signature == "s":
        return f's:"{value}"'
    if signature == "(uu)":
        width, height = value  # type: ignore[misc]
        return f"(uu):({width},{height})"
    if signature == "aa{sv}":
        inner = ",".join(_canonical_dict(d) for d in value)  # type: ignore
        return f"aa{{sv}}:[{inner}]"
    raise AssertionError(f"no canonical form for signature {signature}")


def _canonical_dict(dictionary: dict[str, tuple[str, object]]) -> str:
    body = ",".join(f"{key}={_canonical_value(*dictionary[key])}"
                    for key in sorted(dictionary))
    return "{" + body + "}"


def _signature_of(value: object) -> str:
    """The signature the C++ side carries for an injection argument.

    bool is checked before int because in Python it is a subclass of one, and
    the two are different D-Bus types.
    """
    if isinstance(value, bool):
        return "b"
    if isinstance(value, int):
        return "i"
    if isinstance(value, float):
        return "d"
    if isinstance(value, str):
        return "s"
    raise AssertionError(f"no signature for {value!r}")


def _canonical_call(call: gnome.InjectionCall) -> str:
    args = ",".join(_canonical_value(_signature_of(a), a) for a in call.args)
    return f"{call.method}({args})"


def _canonical_plan(calls: list[gnome.InjectionCall]) -> str:
    return "[" + ",".join(_canonical_call(c) for c in calls) + "]"


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


def variant_reference() -> dict[str, str]:
    """The same payloads dump_variants.cpp emits, built with PyGObject.

    Printed with GLib's own formatter on both sides, so presentation cannot be
    the difference.
    """
    modes_two = [gnome.virtual_monitor_mode(),
                 gnome.virtual_monitor_mode(640, 480, 60.0, is_preferred=False)]
    cases = {
        "variant_mode_default": gnome.virtual_monitor_mode(),
        "variant_mode_no_refresh": gnome.virtual_monitor_mode(1280, 960, None),
        "variant_record_virtual_default": gnome.record_virtual_properties(),
        "variant_record_virtual_platform_true":
            gnome.record_virtual_properties(is_platform=True),
        "variant_record_virtual_cursor_hidden":
            gnome.record_virtual_properties(
                cursor_mode=gnome.CURSOR_MODE_HIDDEN),
        "variant_session_props_empty":
            gnome.screen_cast_session_properties(),
        "variant_session_props_id":
            gnome.screen_cast_session_properties("17"),
        "variant_session_props_both":
            gnome.screen_cast_session_properties("17",
                                                 disable_animations=True),
        "variant_record_virtual_two_modes":
            gnome.record_virtual_properties(modes_two),
    }
    return {name: gnome.to_glib_variant_dict(properties).print_(True)
            for name, properties in cases.items()}


def compare_variants(
        dump_variants: pathlib.Path) -> tuple[list[str], int]:
    """Diff the GVariant payloads both implementations would send."""
    try:
        import gi  # noqa: F401
        from gi.repository import GLib  # noqa: F401
    except ImportError:
        return (["variants: PyGObject is unavailable, so the reference "
                 "cannot build a GVariant"], 0)

    result = subprocess.run([str(dump_variants)], capture_output=True,
                            text=True, check=True)
    native: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, _, value = line.partition(" ")
        native[name] = value

    expected = variant_reference()
    failures = []
    for name, want in sorted(expected.items()):
        got = native.get(name)
        if got is None:
            failures.append(f"{name}: missing from the C++ output")
        elif got != want:
            failures.append(f"{name}:\n    python {want}\n    c++    {got}")
    for name in sorted(set(native) - set(expected)):
        failures.append(f"{name}: emitted by C++ but not by the reference")
    return failures, len(expected)


def read_emitted(binary: pathlib.Path) -> dict[str, str]:
    """Run a dump binary and parse its `name value` lines."""
    result = subprocess.run([str(binary)], capture_output=True, text=True,
                            check=True)
    out: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, _, value = line.partition(" ")
        out[name] = value
    return out


def diff_against(expected: dict[str, str], got: dict[str, str],
                 label: str) -> list[str]:
    """Compare one implementation's vectors against the reference's."""
    failures = []
    for name, want in sorted(expected.items()):
        have = got.get(name)
        if have is None:
            failures.append(f"{name}: missing from the {label} output")
        elif have != want:
            failures.append(f"{name}:\n    python {want}\n    {label:6s} {have}")
    for name in sorted(set(got) - set(expected)):
        failures.append(f"{name}: emitted by {label} but not by the reference")
    return failures


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

    variant_binary = binary.parent / "dump_variants"
    frame_binary = binary.parent / "dump_frame"
    for needed in (variant_binary, frame_binary):
        if not needed.exists():
            print(f"{needed.name} not found at {needed}\n"
                  f"build it:  cmake -S native -B native/build && "
                  f"cmake --build native/build")
            return 2
    expected = reference()
    failures = diff_against(expected, read_emitted(binary), "c++")

    # The Rust core is the third implementation. Not having built it is a skip
    # rather than a failure, so the harness still works in a C++-only checkout.
    rust_binary = ROOT / "rust" / "target" / "release" / "dump_vectors"
    rust_failures: list[str] = []
    rust_compared = 0
    if rust_binary.exists():
        rust_failures = diff_against(expected, read_emitted(rust_binary), "rust")
        rust_compared = len(expected)
    else:
        print(f"note: the Rust core is not built, so it was not compared.\n"
              f"      build it:  cd rust && cargo build --release")

    variant_failures, variant_count = compare_variants(variant_binary)
    frame_failures = compare_frames(frame_binary)

    for line in failures + rust_failures + variant_failures + frame_failures:
        print("MISMATCH " + line)
    print(f"\n{len(expected)} vectors compared against C++, "
          f"{len(failures)} mismatches")
    if rust_compared:
        print(f"{rust_compared} vectors compared against Rust, "
              f"{len(rust_failures)} mismatches")
    print(f"{variant_count} variants compared, "
          f"{len(variant_failures)} mismatches")
    print(f"{len(FRAME_FIXTURES)} frames compared, "
          f"{len(frame_failures)} mismatches")
    return 1 if (failures or rust_failures or variant_failures
                 or frame_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
