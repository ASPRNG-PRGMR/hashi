# The C++ core — milestone 1 of the native port

2026-11-08. `native/` holds a C++17 implementation of HASHI's protocol and
transport layer: usbmux framing, the startup handshake, record framing and the
inbound input decode. It is byte-identical to the Python implementation on
every vector checked.

**The Python modules remain the reference**, and that is a deliberate ordering.
They are what reproduced the captured 130,375,177-byte outgoing stream
byte-for-byte, and what drove the device in FED-LIVE-E001 and FED-HOST-E001.
A port is correct when it agrees with them, not when its own tests pass.

## Why a native port, honestly

**A native port does not make HASHI faster.** Measured on the captured frame:

| Stage | Median |
| --- | --- |
| PipeWire buffer → image | 0.63 ms |
| JPEG encode (libjpeg-turbo) | 4.23 ms |
| Record framing | 0.008 ms |
| **Total** | **4.9 ms of a 33.3 ms budget** |

That is roughly 206 fps of headroom, and the encode is already native C —
Python only orchestrates it. The measured 26.5 fps was bound by the wire, at
~372 KB per frame, which is why *not re-sending unchanged frames* was done
first and cut bandwidth by about 91%.

The real reasons to port are different and worth stating plainly: a single
binary with no Python, Pillow or PyGObject runtime; a smaller dependency
surface; and a base for the Rust implementation. Speed is not one of them.

## What is here

```
native/
  include/hashi/{bytes,plist,usbmux,startup,stream}.hpp
  src/{plist,usbmux,startup,stream}.cpp
  tests/{testing.hpp,test_protocol.cpp}     56 tests
  tools/{dump_vectors.cpp,conformance.py}
```

Build and check:

```sh
cmake -S native -B native/build
cmake --build native/build -j
./native/build/test_protocol          # 56 tests
python3 native/tools/conformance.py   # 19 vectors against Python
```

The library compiles clean under `-Wall -Wextra -Wpedantic -Wconversion
-Wshadow`.

## Dependencies: none, on purpose

The core links nothing beyond the standard library. usbmuxd speaks XML
plists and `libplist`'s development package is not installed on this machine,
so the subset the protocol actually uses — dictionaries of strings, integers
and booleans, plus one array of dictionaries in a `ListDevices` reply — is
implemented in `plist.cpp` and tested against real reply shapes. The reader is
strict: an unsupported element raises rather than being skipped, so a reply
shaped differently from the decoded protocol fails visibly.

The same applies to the `diff_jpeg` capability gate. It needs a JSON document,
so `startup.cpp` carries a small JSON scanner rather than a string match: the
agent genuinely parses, and a malformed document must fail the gate rather
than appear to contain a key. Only a **top-level** `diff_jpeg` counts, and it
must be a boolean and true — the same three-step chain the agent applies.

Later milestones will link GIO for Mutter's D-Bus, GStreamer for capture and
libjpeg-turbo for encoding. Of those, `gio-2.0` and `libjpeg` development
packages are present; `gstreamer-1.0`, `gstreamer-app-1.0` and `libturbojpeg`
are not and will need installing.

## Conformance, not parallel test suites

`tools/dump_vectors.cpp` prints the C++ core's bytes for 19 vectors;
`tools/conformance.py` builds the same vectors with the Python modules and
diffs them. Result: **19 vectors compared, 0 mismatches.**

The vectors cover the whole startup sequence, both byte orders, record headers
at the 24-bit boundary, image-record framing, the usbmux header and the
derived values (the swapped port, dimension alignment, the frame interval).

The usbmux **plist body** is deliberately not compared. usbmuxd parses XML, so
two writers may legitimately differ in whitespace and key order; the protocol
pins the 16-byte header, so that is what is checked. The Python tests round-trip
the body rather than asserting exact XML for the same reason.

## Quirks the port had to preserve

A port is where fidelity quietly degrades, so the deliberate oddities are
called out in the code and tested:

- **The `0xfc` record's field 1 is little-endian.** The agent stores the
  literal 5 with no `htonl` (RVA 0x30829) while its siblings are big-endian.
  `encode_control`'s `raw_field1` reproduces it. Do not fix it.
- **Only type 7 inbound payloads are byte-swapped**, and unconditionally —
  the decode does not consult the negotiated byte-order flag the way the
  header decode does.
- **An overlong inbound record is consumed in full** while only the 12 bytes
  the agent keeps are parsed. Keeping and consuming 12 would desynchronise
  every later record.
- **`NotifyPointerButton` takes evdev codes**, so `BTN_LEFT` is 272, not a
  Win32 `MOUSEEVENTF_*` flag. The mapping lives in `stream.hpp`.
- **Only byte 0 of the byte-order probe reply is checked.**

`swap16` is written out rather than calling `htons`, so the value is right on
a big-endian host too — where `htons` would be a no-op and would produce the
wrong bytes for this protocol.

## Two bugs the build found

Worth recording because both were in the *test harness*, where they would have
quietly weakened everything it asserts:

1. `CHECK_EQ` bound its arguments with `const auto&`, so comparing
   `*optional` captured a reference to a temporary that had already died. It
   read 7 instead of 272 — a plausible-looking wrong answer rather than a
   crash. `-Wdangling-pointer` caught it; the macro now binds by value.
2. `testing.hpp` was missing `<cstdint>`, which made an `is_same_v` condition
   invalid and caused every branch of an `if constexpr` to be compiled.

## Limitations

- **This is the protocol core only.** No D-Bus, no capture, no JPEG encoding,
  no main loop, and no I/O of any kind — it builds and parses byte strings.
  Nothing in `native/` has ever touched the device.
- **Conformance is vector-based, not exhaustive.** 19 vectors agree; that is
  strong evidence of a faithful port, not proof. The Python side additionally
  reproduces a full captured stream, which the C++ side does not yet do.
- **The plist and JSON readers implement subsets.** They are adequate for this
  protocol and are not general-purpose parsers.
- The Rust implementation the user intends is not started. When it is, the
  same conformance harness should be pointed at it: a third implementation
  agreeing on bytes is worth far more than a third test suite.
