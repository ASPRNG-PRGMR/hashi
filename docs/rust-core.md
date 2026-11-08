# The Rust core, and what a third implementation is for

2026-11-09. `rust/` holds a third implementation of HASHI's decoded protocol,
alongside the Python reference in `python/` and the C++17 port in `native/`.
All three now agree on **65 byte vectors, 0 mismatches**.

## Why a third one

**A test asserts what its author believed. An independent implementation that
lands on the same bytes is evidence the decode itself is right.**

That distinction is the whole argument. The Python suite could assert a wrong
value confidently, and a second suite written by the same hand against the
same reading would assert it just as confidently. What a second and third
*implementation* cannot easily do is reproduce the same mistake — especially
the mistakes this protocol invites, which are the places where the agent does
something that looks wrong.

The sharpest example is the `0xfc` record's field 1. The agent stores the
literal 5 with **no** `htonl` while its siblings are big-endian, so the
capture carries a little-endian 5. Every implementation has to decide whether
to reproduce that or "fix" it, and a port written by someone reading tidy code
will fix it. The conformance harness catches exactly that: sabotaging the
expectation to the big-endian form is reported immediately, by bytes, rather
than relying on a comment asking nobody to make the change.

## No dependencies, and why that is load-bearing

The crate links nothing beyond the standard library — no `serde`, no plist
crate, no JSON crate. Three consequences, all of them wanted:

1. `cargo build --offline` needs no network and no vendored registry. The
   launcher passes `--offline` deliberately, so a build that fails for want of
   a crate is itself the signal that a dependency crept in.
2. The implementation stays **independent**. Three implementations agreeing on
   bytes is only evidence if they do not share the code that produces those
   bytes. If all three parsed plists with the same crate, their agreement on
   plists would mean nothing.
3. It mirrors `hashi_protocol`, which has the same property for the same
   reasons.

The XML-plist reader is a strict subset, as in the C++ port: an unsupported
element is an error rather than being skipped, so a reply shaped differently
from the decoded protocol fails visibly instead of yielding a half-parsed
value. The same applies to the `diff_jpeg` gate's JSON scanner — the agent
genuinely parses, so a malformed document must fail the gate rather than
appear to contain a key.

## What is here

```
rust/
  Cargo.toml              no [dependencies], on purpose
  src/
    lib.rs                the crate's one error type
    bytes.rs              byte-order helpers, each naming its order
    plist.rs              the XML-plist subset usbmuxd needs
    usbmux.rs             the 16-byte header and the Connect/ListDevices plists
    startup.rs            the handshake, and the diff_jpeg JSON gate
    stream.rs             record framing and the inbound TLV decode
    jpeg.rs               the 623-byte prelude from Annex K tables
    gnome.rs              Mutter's D-Bus arguments and injection planning
    capture.rs            the pipeline description and the geometry check
    pacer.rs              the frame schedule
    bin/dump_vectors.rs   emits the 65 vectors for the harness
  tests/protocol.rs       45 tests
```

Checks:

```sh
cd rust && cargo test --offline          # 45 tests
cargo clippy --offline --all-targets     # clean
cargo fmt --check                        # clean
```

## Coverage: the same 65 vectors, without linking anything

Nearly every conformance vector is pure computation, so Rust reaches the same
coverage as the C++ port while linking nothing at all — the handshake, record
framing, the usbmux header, the whole JPEG prelude, the canonical D-Bus
arguments and injection plans, the capture pipeline string, and the pacer's
schedule under a scripted clock.

Three comparisons are **not** reproduced in Rust, and the reasons differ:

- the **9 GVariant payloads** need GLib, which this crate declines to link;
- the **8 whole JPEG frames** need libjpeg-turbo's entropy coder;
- the usbmux **plist body**, which is deliberately not compared in any
  implementation — usbmuxd parses XML, so three writers may legitimately
  differ in whitespace and key order. The protocol pins the 16-byte header,
  and that is what is checked.

A missing Rust build is reported as a note rather than a failure, so the
harness still works in a checkout where only the C++ side has been built.

## A divergence the port found

The inbound sanity limit on an announced TLV payload is **4096** in the Python
reference and the C++ port. I wrote `0xFFFFFF` in Rust first, and no
conformance vector covers it — the limit is a refusal path, not a byte on the
wire — so it would have diverged silently. It is aligned to 4096, and this is
worth recording as the shape of gap the harness does *not* close: vectors
compare what three implementations emit, not what they refuse.

Every record ever observed inbound was 16 bytes, so the limit is a
desynchronisation guard rather than anything the protocol requires. The agent
itself has no such limit.

## What the Rust core deliberately lacks

No entropy coder, no D-Bus session, no PipeWire capture, no main loop and no
I/O of any kind. Those need libraries the crate declines to take, and the
Python host and the C++ port already have them. **Nothing in `rust/` has run
against the device.**

Whether to extend it — FFI to libjpeg-turbo for frames, a D-Bus crate for the
session — is a real decision rather than an obvious next step, because each
one costs the independence described above. Frames would be the most valuable,
since byte-identical JPEG output from a third encoder path would be strong
evidence; it is also the only one where the comparison is exact.

## The launcher

`hashi.sh` builds whatever is present and runs all three suites plus
conformance. It defaults to `check`, which touches no device:

```sh
./hashi.sh              # build everything present, run every check
./hashi.sh plan         # what a run would do; touches nothing
./hashi.sh devices      # ask the local usbmuxd what is attached
./hashi.sh run ...      # the real thing; the binary needs --allow-session
```

`run` prints what it is about to cause — a monitor appearing, a sharing
indicator, bytes to the device — and then lets the binary enforce
`--allow-session` itself, rather than re-implementing that gate in shell where
it could drift.

Two bugs in the script were found and fixed before it was committed, both in
its *reporting* rather than its behaviour, which is the kind that quietly
misleads: `--help` printed past the comment block into the shell options, and
the Rust summary read the last `test result` line, which is the empty doc-test
suite, and so reported 0 passed when 45 had.
