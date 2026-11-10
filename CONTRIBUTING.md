# Contributing to HASHI

Thanks for looking. HASHI is a small project with an unusual constraint — it
reimplements a protocol nobody documented — so the rules below are mostly about
*evidence*, not style.

## The one rule that matters: no guessed protocol behaviour

Every claim in this repository's documentation is labelled:

- **Fact** — directly observed, or stated in official documentation.
- **Inference** — a logical conclusion from observed evidence.
- **Hypothesis** — a plausible explanation awaiting confirmation.

A pull request that implements a message, field, resize path or control flow
that nobody has actually seen on the wire will not be merged, however plausible
it looks. The project has deliberately left decoded-but-unobserved paths
unimplemented — multi-touch, keyboard, reconfiguration, differential JPEG — and
that is a feature, not a backlog item waiting for a guess.

If you have a **capture** that exercises one of those paths, that is the single
most valuable contribution available. Open an issue describing what you
captured and how; do not attach raw captures to a public issue (see
[Private material](#private-material)).

## What is especially welcome

- Captures of unexercised paths: multi-touch, keyboard, Apple Pencil,
  display reconfiguration, error states, `field0` values other than 5, 6 and 10.
- Reports from **other hardware**: different iPad models, different iOS and
  Splashtop app versions, other GNOME versions.
- Support for **other compositors**. The virtual-monitor layer is isolated
  behind one module precisely so a KDE or wlroots backend can sit beside it.
- Packaging work — see [`docs/packaging.md`](docs/packaging.md).
- Documentation fixes, especially anywhere a claim is stated more strongly than
  its evidence supports.

## Before you open a pull request

```sh
./hashi.sh            # builds everything present, runs all three suites and conformance
```

This must pass. It touches no device and needs no iPad, which is why CI can run
the whole offline half of the project on every push.

If you change anything that produces bytes — framing, the handshake, the JPEG
prelude, the D-Bus arguments — you must keep **all three implementations in
agreement**. Conformance diffs Python against C++ and Rust over 65 byte
vectors, 9 GVariant payloads and 8 whole frames. A change to one
implementation alone will fail it, and that is the point: three
implementations agreeing on bytes is the project's main evidence that the
decode is correct.

New behaviour needs a test. New *observed* behaviour needs a note in the
relevant document under `docs/`, with its evidence.

## Code style

- **Python** — standard library plus PyGObject and Pillow. Keep anything that
  can be tested without a compositor, device or socket as a pure function.
- **C++** — C++17, no dependencies in the protocol core.
- **Rust** — no crates. The Rust core takes no dependencies on purpose: three
  implementations agreeing means nothing if they share the code that produces
  the bytes.
- Comments should explain *why*, and say what the evidence is. The existing
  code does this; match it.

## Commits

- One topic per commit, with a scope prefix: `fix:`, `docs:`, `feat:`, `ci:`,
  `refactor:`, `test:`.
- Describe what changed and why it is correct, not just what file moved.

## Private material

Never commit, attach or paste:

- raw USB captures, `.pcap`/`.pcapng`/`.etl` files
- pairing records or device identifiers
- vendor binaries, DLLs, drivers or extracted assets
- frame dumps containing real screen content

These are excluded by `.gitignore` as a second line of defence, but the first
line is you. If you need to share a capture for debugging, say so in the issue
and arrange a private channel.

## Legal

HASHI is an interoperability project. Contributions must not include Splashtop
code, decompiler output, disassembly listings of vendor binaries, or
transcribed vendor data tables. Describe observed *behaviour* and implement it
independently — that distinction is what keeps the project on the right side of
the line, and it is not negotiable.

By contributing you agree your work is dual-licensed under MIT OR Apache-2.0,
as described in the [README](README.md#license).
