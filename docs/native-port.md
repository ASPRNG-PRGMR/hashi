# The native port

**2026-11-09 — the port is complete in scope.** `native/` now holds a C++17
implementation of every subsystem the Python host has: usbmux framing and the
startup handshake, record framing and the inbound input decode, JPEG frame
generation, Mutter's D-Bus contracts, the live session over GIO, PipeWire
capture over GStreamer, and the composed loop behind a `hashi` binary. 4,040
lines, 129 tests, and agreement with the Python reference on 65 byte vectors,
9 GVariant payloads and 8 whole JPEG frames.

**It has never been run.** `hashi run` refuses without `--allow-session`, and
that flag has not been passed. Scope-complete is not working: see
*Limitations*.

*(Milestone 1, below, was the protocol and transport core on 2026-11-08.)*

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
  include/hashi/
    bytes.hpp plist.hpp usbmux.hpp startup.hpp stream.hpp   protocol core
    jpeg.hpp encoder.hpp                                    frame generation
    gnome.hpp glib_raii.hpp session.hpp                     Mutter
    capture.hpp host.hpp                                    capture and loop
  src/   plist usbmux startup stream jpeg encoder gnome session capture host
  tests/ testing.hpp test_protocol(83) test_encode(9) test_session(8)
         test_capture(8) test_host(21)
  tools/ dump_vectors dump_variants dump_frame conformance.py hashi
```

Five libraries, layered so that each dependency is confined to the layer that
needs it:

| Target | Links | Holds |
| --- | --- | --- |
| `hashi_protocol` | nothing | the protocol, and the JPEG prelude |
| `hashi_encode` | libjpeg-turbo | the entropy coder |
| `hashi_session` | GIO | the live D-Bus session |
| `hashi_capture` | GStreamer | PipeWire capture |
| `hashi_host` | the above | socket, pacing, the loop |

Build and check:

```sh
cmake -S native -B native/build
cmake --build native/build -j
ctest --test-dir native/build       # 5 binaries, 129 tests
python3 native/tools/conformance.py # 65 vectors, 9 variants, 8 frames
./native/build/hashi plan           # what a run would do; touches nothing
```

Everything compiles clean under `-Wall -Wextra -Wpedantic -Wconversion
-Wshadow`, with one pre-existing exception: `plist.hpp` warns twice under
`-Wshadow` because `Type`'s `Dict` and `Array` enumerators shadow the aliases
of the same name. They are scoped enumerators, so nothing can be confused;
the warning predates this work and is left for a separate decision.

## Dependencies, confined to the layer that needs them

**`hashi_protocol` still links nothing beyond the standard library**, and that
is now a deliberate property rather than a starting condition: the JPEG
prelude lives there because it is marker bytes from published tables, while the
entropy coder, the bus, and the capture pipeline each sit in their own target.
The practical payoff is that the protocol, the frame prelude, the D-Bus
arguments, the pipeline string and the pacer are all checkable with no
compositor, no bus and no device.

usbmuxd speaks XML plists and `libplist`'s development package was not
installed when this was written, so the subset the protocol actually uses — dictionaries of strings, integers
and booleans, plus one array of dictionaries in a `ListDevices` reply — is
implemented in `plist.cpp` and tested against real reply shapes. The reader is
strict: an unsupported element raises rather than being skipped, so a reply
shaped differently from the decoded protocol fails visibly.

The same applies to the `diff_jpeg` capability gate. It needs a JSON document,
so `startup.cpp` carries a small JSON scanner rather than a string match: the
agent genuinely parses, and a malformed document must fail the gate rather
than appear to contain a key. Only a **top-level** `diff_jpeg` counts, and it
must be a boolean and true — the same three-step chain the agent applies.

**Correction (2026-11-09): no packages needed installing.** This file
previously said `gstreamer-1.0`, `gstreamer-app-1.0` and `libturbojpeg` were
absent, and the session handoff repeated it as a `sudo dnf install` step. All
three are in fact present and link: libturbojpeg **3.1.4.1**, gstreamer-1.0
and gstreamer-app-1.0 **1.28.8**, gio-2.0 **2.90.1**. Checked with
`pkg-config --exists` for each `.pc`, then for the headers themselves, then by
compiling and running a program that calls `tj3Init` and `gst_init` — because
a `.pc` file without its header is exactly the trap `libjpeg-turbo-devel`
already set here. No `sudo` was used.

`libpipewire-0.3` is still absent and still not needed: capture goes through
GStreamer's `pipewiresrc`, not libpipewire directly.

## What each new layer had to get right

### JPEG: five parameters, and byte-identity is a side effect

**Fact.** libjpeg-turbo driven through its own TurboJPEG API is
**byte-identical** to the same library driven through Pillow, on all 8 fixtures
— including 1280x960 pseudo-random noise (821,046 bytes) and single-pixel
chroma edges. Five settings are load-bearing:

| Parameter | Value | Why |
| --- | --- | --- |
| `TJPARAM_QUALITY` | 80 | fixes the quantization tables |
| `TJPARAM_SUBSAMP` | `TJSAMP_420` | the observed 0x22/0x11/0x11 geometry |
| `TJPARAM_DENSITYUNITS` | 1 | dots per inch |
| `TJPARAM_XDENSITY` | 120 | the observed JFIF density |
| `TJPARAM_YDENSITY` | 120 | the observed JFIF density |

Without the three density parameters TurboJPEG writes "no units, 1x1" where
the captured frames carry 120 dpi. The negative control above turns on exactly
this: density 121 produces a frame of *identical length* that differs in
bytes.

**Fact, reproduced independently.** Encoding a solid black 1280x960 buffer
gives 19,827 bytes with SHA-256 `317955d8383feb8b…` — the captured stream's
first record, matching the figure FED-JPEG-E001 recorded. That is the one
captured frame whose source pixels are reconstructible, so it is the only one
an encoder can be held to exactly.

**Clean-room note.** The Annex K table literals in `src/jpeg.cpp` were
*generated from the Python module* rather than retyped, so the two cannot
drift by transcription. They are published ISO/IEC 10918-1 data in both
places; no vendor table is transcribed.

### Mutter: the contract layer is split from the bus

`gnome.hpp` builds every D-Bus argument and plans every injection while
linking **nothing**. That is what lets conformance check it offline — with no
compositor running, no session created, and no monitor appearing on the user's
desk. `session.hpp` adds GIO and the calls.

The split also makes the two FED-DBUS-E001 results testable as behaviour
rather than as comments: the pinned `modes` key that makes the stream
non-resizable at 1280x960, and `NotifyPointerButton` taking the evdev
`BTN_LEFT` 272 rather than a Win32 flag. So is the motion-before-button
ordering, which Windows gets for free in one `SendInput` and Linux does not.

`check_versions` rejects a **higher** interface version as well as a lower
one, matching the reference. A changed `modes` contract would otherwise
surface only as wrong-sized frames.

### The session: the traps are enforced, not documented

- `inject()` **refuses** until `stream_consumed` is set, because Mutter
  silently discards absolute motion until something consumes the PipeWire
  stream while still returning success. Buttons land regardless, so the
  symptom is clicks at a stale position — selected text, odd window
  behaviour — with no error anywhere.
- `close()` stops the remote-desktop session and only falls back to stopping
  the cast if that did not happen, since stopping both makes the second call
  fail with "Object does not exist at path".
- `close()` **records** its errors rather than raising, so teardown cannot
  mask the failure that caused it: stopping a session that never started fails
  with "Session not started", which would otherwise replace the real cause.
- `stream_parameters()` returns the keys as they are. A virtual stream has no
  `size` or `position`; geometry is asserted on the negotiated PipeWire caps
  instead.

Every GLib handle is owned — the bus connection, each proxy, every GVariant,
the main loop — plus an `ErrorSink` so no path can drop a `GError`. This is
what C++17 was chosen for: the faults the Python host's first live run
produced were teardown-ordering ones.

### Capture: the geometry is pinned twice, on purpose

The virtual monitor's mode fixes the size on the compositor's side and the
caps fix it on the consumer's side, so a mismatch fails in **negotiation**
rather than quietly producing frames the 623-byte prelude cannot describe.

The damage-driven behaviour is handled as the reference handles it: the stream
negotiates `framerate=0/1`, so an idle virtual monitor yields no buffers at
all. A timeout once the stream is running means "nothing changed" and the last
frame is repeated; only never receiving a *first* frame is a failure.

### The binary keeps the dangerous part behind a flag

`hashi plan` prints what a run would do and touches nothing. `hashi devices`
asks the local usbmuxd and not the device. `hashi run` refuses without
`--allow-session`, naming the effects: a monitor on the desktop, a sharing
indicator, bytes to the iPad. Ctrl-C ends a run at a tick boundary so the
session and the monitor tear down in order.

## Conformance, not parallel test suites

The Python modules are the reference, so a layer is checked by diffing its
output against theirs rather than by asserting similar things twice. There are
now three kinds of comparison, run by `tools/conformance.py`:

**65 byte vectors** (`dump_vectors`) — the whole startup sequence in both byte
orders, record headers at the 24-bit boundary, image-record framing, the
usbmux header, the derived values, the JPEG prelude and each of its segments,
the capture pipeline string, and the pacer's schedule under a scripted clock.
The Mutter D-Bus arguments and injection plans are here too, rendered in a
canonical text form: GLib builds the real message, so what has to agree is the
signatures, keys, defaults and values.

**9 GVariant payloads** (`dump_variants`) — the same dictionaries, but built
into actual GVariants and printed with `g_variant_print` on both sides. This
is the stronger check, because it is the message that would go on the bus. It
agrees down to dictionary ordering and the empty `@a{sv} {}` case.

**8 whole JPEG frames** (`dump_frame`) — complete frames, scan data included,
encoded from identical pixel buffers. The reference reaches libjpeg-turbo
through Pillow and the port through the TurboJPEG API, so this checks the
entropy coder agrees rather than assuming that both linking libjpeg is enough.
The fixtures cover flat DC content, luma AC, heavy AC in all three components,
chroma edges at single-pixel pitch, and sizes that are not a multiple of the
16-pixel MCU.

Result: **0 mismatches across all three.**

### The harness was checked for the ability to fail

A conformance harness that cannot fail proves nothing, so each new kind of
comparison was given a negative control before being trusted:

- **Frames** — encoding at quality 79 instead of 80 is caught, and so is
  density 121 instead of 120. The second matters more: it is a difference at
  *equal length*, so the comparison is reading bytes and not just sizes.
- **D-Bus arguments** — rendering the cursor mode as `int32` instead of
  `uint32` is caught. That is the exact shape of bug this vector class exists
  to find, and nothing about the values themselves would look wrong.

### What is deliberately not compared

The usbmux **plist body**: usbmuxd parses XML, so two writers may legitimately
differ in whitespace and key order. The protocol pins the 16-byte header, so
that is what is checked, and the Python tests round-trip the body for the same
reason.

The **frame gate's** keepalive decision. The reference reads
`time.monotonic()` inside the method with no way to inject a clock, so there
is no way to drive both sides through the same instants. It is unit-tested in
C++ with a scripted clock instead, and that is stated rather than papered
over. The pacer *is* compared, because the reference's constructor already
takes a `now` argument.

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
- **A frame identical to the last one is still re-sent once a second.**
  Transmission is slowed, not stopped: what the device does with a silent
  stream has never been observed, and the captured Windows session streamed
  continuously for its whole life.
- **The stride assertion is kept even though it cannot fire at 1280x960.**
  GStreamer pads rows to a 4-byte boundary and 1280x3 is already a multiple of
  4. An unnoticed stride would shear the image diagonally rather than fail,
  which is the kind of fault that costs a session debugging the protocol
  instead of the capture.

Two of the reference's workarounds are deliberately **not** ported, with a
comment at each site saying so, because both are PyGObject artefacts rather
than facts about the protocol:

- `GLib.Variant("(a{sv})", (prebuilt,))` raising `KeyError`, which the
  reference avoids with `new_tuple`. In C, `g_variant_new_tuple` is simply the
  ordinary spelling.
- needing `GstApp` imported for `try_pull_sample` to exist. In C, including
  `gst/app/gstappsink.h` is the whole requirement.

And one divergence from the *agent* is kept, as the reference keeps it:
pacing uses a monotonic clock. The decoded pacing reads only
`GetSystemTime`'s `wMilliseconds`, so its own elapsed measurement wraps every
second and cannot tell a 1.2-second stall from a 200 ms one.
`hashi_stream.pacing_sleep_ms` reproduces that faithfully, including the wrap;
a host has no reason to inherit it. `frame_interval_ms` still supplies the
target, so the interval and its truncation are the decoded ones.

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

- **Nothing in `native/` has ever touched the device or the compositor.** The
  port is complete in *scope*, which is not the same as working. `hashi run`
  needs `--allow-session` and has not been given it; no `VirtualDisplaySession`
  has been opened, no GStreamer pipeline started, and no byte sent to the iPad.
  The ordering in `session.cpp` is copied from the Python host rather than
  rederived precisely because that ordering is what FED-HOST-E001 confirmed,
  but the composition remains an **Inference** for this implementation. Treat
  the first run as the experiment it is.
- **What a first run would most plausibly expose** is teardown ordering and
  the consumer gate, since those are what the Python host's first run
  exposed — not the protocol, which is validated twice over.
- **Conformance is vector-based, not exhaustive.** 65 vectors, 9 variants and
  8 frames agree; that is strong evidence of a faithful port, not proof. The
  Python side additionally reproduces a full captured stream byte-for-byte,
  which the C++ side does not yet do — pointing `dump_frame` at the captured
  stream's own records would be the natural next strengthening.
- **The plist and JSON readers implement subsets.** They are adequate for this
  protocol and are not general-purpose parsers. `libplist-devel` 2.7.0 is now
  installed, so switching is possible; it remains a judgement call rather than
  a fix, and the hand-written reader's strictness (an unsupported element
  raises rather than being skipped) is a property worth keeping.
- **Unexercised paths are unexercised in both implementations.** Multi-touch
  and `ContactID`, keyboard (`field0` 1/2), `field0` 16/17, reconfiguration,
  the TLV `0x70` subtype and differential JPEG. `field0` values 3, 4, 7, 8, 9
  and 11–17 have never been seen on the wire; only 5, 6 and 10 have. The port
  carries the statically decoded mappings for right and middle buttons and
  must not be read as evidence they work.
- **`diff_jpeg` is a refusal, not a feature.** If the device ever enables it
  the host stops with an error, because the differential path is gated but was
  never observed and nothing is known about what it transmits.
- The Rust implementation the user intends is not started. When it is, the
  same conformance harness should be pointed at it: a third implementation
  agreeing on bytes is worth far more than a third test suite. The three
  comparison kinds above are all reusable, since each compares text or bytes
  on stdout rather than anything language-specific.
