# HASHI

**H**ost **A**dapter for **S**plashtop **H**ardware **I**nterop

A Linux host implementation that speaks Splashtop's wired display protocol — letting an unmodified iPad running the Splashtop app work as a real extended or mirrored display for a Linux machine over USB, the way Splashtop's own Windows/macOS host works today.

HASHI (橋, "bridge") is an interoperability-motivated reverse-engineering project. No Splashtop code, binaries, or proprietary assets are used or redistributed — only observed protocol behavior, documented Microsoft/Apple platform APIs, and standard Linux kernel interfaces. (It is not a formal two-team clean room; see the devlog's 2026-10-14 notes.)

## Why This Project Exists

Splashtop's wired XDisplay host only ships for Windows and macOS. There is no Linux host, and no open alternative that speaks its actual protocol — so an iPad can't be used as a USB-tethered display for a Linux machine without switching platforms.

This project investigates Splashtop's Windows host architecture (USB pairing, virtual display creation, frame delivery) and reimplements the *host* side on Linux, using Linux's own equivalents for each layer:

| Windows piece | Linux equivalent |
|---|---|
| Apple Mobile Device Service / Bonjour | `usbmuxd` + `libimobiledevice` |
| `lci_iddcx.dll` (IddCx virtual display driver) | `evdi` kernel driver, or DRM writeback connectors |
| `IndirectKmd` (Microsoft kernel component) | Native DRM/KMS |
| Windows Display Manager | Wayland compositor or X11 (Xrandr) |

The goal is not to clone Splashtop's software — it's to speak its wire protocol well enough that the real, unmodified Splashtop iPad app treats a Linux box as a valid host, the same way Samba lets Linux speak SMB to Windows clients, or libimobiledevice lets Linux speak lockdownd to iOS devices.

## Current Status — Read This First When Resuming

**2026-11-07 update — this is the current resume point. Everything dated earlier in this section is historical.**

**Fact:** The prerequisite-skills phase and the REA/Ghidra study check are **complete**; do not restart them and do not rebuild the study DLL. Phase 1 capture is complete and reproduced offline: the application record boundary (one tag byte + BE24 length), 1,903 tag-6 JPEG records at 1280×960, and twelve decoded pixel-matched samples. See [Windows startup framing](docs/windows-startup-framing.md) and FED-FRAME-E001.

**Fact:** The live capture backend is established. On the working Windows installation the active captor was **LCI** (vtable RVA `0x1ac4b4`) and the encoder was **ordinary JPEG** (vtable RVA `0x1ac818`), recorded as WIN-BACKEND-E001–E004.

**Fact:** The sizing question is resolved structurally as FED-MODE-E001: the dimensions reaching the encoder are the selected monitor's `rcMonitor` extent from `GetMonitorInfoW`, and the captured LuminonCore rectangle `[1920,0,3200,960]` gives exactly the observed 1280×960. The captor cannot set the mode in an LCI configuration, the agent's own best-mode scorer selects 1600×1200 rather than 1280×960 for this client, and the mode already existed before the traced window. **Fact (user-reported):** the cause is simply that the user chose 1280×960 in Windows display settings as the size they want for the iPad, and Windows persisted it. The sizing question is closed and needs no Windows access; 1280×960 is the host's target size. See [mode-selection chain](docs/fedora-mode-selection.md).

**Fact (FED-START-E001):** The startup handshake is decoded and implemented. The whole exchange is one function at RVA `0x303f0`, `CProbeUsbmuxd::DoHandshake`; the host side now reproduces the captured outgoing startup bytes **byte-for-byte**, parses the captured incoming stream with zero remainder, and accounts for the entire 130,375,177-byte application stream — all offline, with no device and no Windows. See [startup handshake](docs/fedora-startup-handshake.md).

**Fact (FED-STREAM-E001):** The steady-state loop is decoded. **The entire host→device direction now reproduces byte-for-byte offline** — all 1,903 image records plus the handshake rebuild the full 130,375,177-byte outgoing stream, same SHA-256 as the capture. The inbound TLV channel is the **input** channel: mouse and keyboard via `SendInput` with the Win32 button constants mapped, multi-touch via `InjectTouchInput` with a `ContactID`, and coordinates absolute over the virtual desktop. The handshake's extra-data block is a JSON capability document, and its `diff_jpeg` gate explains why ordinary rather than differential JPEG ran. Neither inbound records nor a reconfiguration were ever captured, so those two are decoded but unvalidated. See [steady state](docs/fedora-steady-state.md).

**Fact:** Repository code is now `hashi_framing.py` (validated record/JPEG-header parser), `hashi_startup.py` (handshake codec, no I/O), `hashi_stream.py` (steady-state codec, no I/O), `hashi_jpeg.py` (frame prelude), `hashi_usbmux.py` (transport, no I/O) `hashi_mode.py` (FED-MODE-E001 dimension rules, with the reconstructed `FindBestResolution` scorer marked **Inference** and not wired into anything) `hashi_gnome.py` (the Mutter virtual-monitor and input-injection layer, FED-DBUS-E001) and `hashi_host.py` (the composition of all of it, never run), with **289 passing tests** in `tests/`. No guessed handshake, resize, codec or control message has been implemented, and none should be.

Run them with — `-t .` because the modules import each other by bare name, so
the import root has to be `python/` rather than `python/tests`:

```sh
cd python && python3 -m unittest discover -s tests -t .
```

Or all of it at once, from the repository root — builds what is present, runs
the three suites and the conformance comparison, and touches no device:

```sh
./hashi.sh
```

The pieces, if you want them separately:

```sh
cmake -S native -B native/build && cmake --build native/build -j
ctest --test-dir native/build       # 5 binaries, 129 tests
cd rust && cargo test --offline     # 45 tests
python3 native/tools/conformance.py # 65 vectors x2, 9 variants, 8 frames
./native/build/hashi plan           # what a run would do; touches nothing
```

*(The sentence that stood here — "there is still no Linux host implementation and no validated application protocol beyond the record boundary" — was true when written and is now superseded: the protocol is decoded and live-validated, and the host's layers exist, though they have not been run end to end.)*

**MILESTONE — 2026-11-08 (FED-LIVE-E001): the iPad displayed frames sent from Fedora.** The unmodified Splashtop client completed the decoded handshake first time, rendered a white/black/white pattern from 362 streamed frames (9.6 MB at 30 fps, user-confirmed on screen), and sent back **1,449 input records** while the screen was touched. The handshake's client dimensions and extra-data block came back byte-identical to the Windows capture. Inbound records were all TLV type 7, 16 bytes, coordinates inside the 1280×960 display space — exactly as decoded. `field0` 5 and 6 are pointer down/up as statically predicted, and 10 — the one value static analysis could not classify — is motion. See [live validation](docs/fedora-live-validation.md).

**The protocol is no longer the risk.** What remains is generation, not understanding: the Mutter virtual monitor plus PipeWire capture so frames come from a real extended display rather than a replay, and input injection. Frames so far were *replayed*, not generated. (The JPEG entropy coder, listed here when this paragraph was written, is since closed — see below.)

**Fact (2026-11-08, FED-ARCH/JPEG/USBMUX-E001):** The Linux side is now designed and partly built. The **architecture is settled**: GNOME Shell 51.1 on Wayland exposes `org.gnome.Mutter.ScreenCast.Session.RecordVirtual`, a userspace **virtual monitor** the desktop genuinely extends onto and which streams over PipeWire, plus `RemoteDesktop` input injection reporting `SupportedDeviceTypes = 7` (keyboard, pointer, touchscreen). So no kernel module, no root, no `evdi`. See [Linux host architecture](docs/linux-host-architecture.md).

**Fact:** the **JPEG frame prelude** is reproducible: all 1,903 captured records share a 623-byte prelude built entirely from published ISO/IEC 10918-1 Annex K tables at **quality 80**, 1280×960, 4:2:0 — verified 1903/1903 and 12/12 against the capture. No vendor table data is transcribed. See [JPEG frames](docs/fedora-jpeg-frames.md). The **usbmux transport** is implemented and validated against the captured control exchange, including the byte-swapped `PortNumber` (6789 → 34074). See [usbmux transport](docs/fedora-usbmux-transport.md).

**Fact (2026-11-08, FED-DBUS-E001):** the **Mutter 51 D-Bus contracts are verified** and the GNOME display/input layer is written. Every `ScreenCast` and `RemoteDesktop` signature is confirmed three ways against the installed `mutter-51.1-1.fc45` build — live introspection, the `GDBusMethodInfo` tables inside `libmutter-51.so.0`, and the unpatched Fedora source RPM — closing the caveat that only the method *names* were known. Two results shaped the design: `RecordVirtual` takes a **`modes`** key that pins the virtual monitor to exactly 1280×960 and makes the PipeWire stream non-resizable, and `NotifyPointerButton`'s `button` is an **evdev** code (`BTN_LEFT` = 272), not a Win32 flag. The absolute-motion transform is a pure translation, so the iPad's monitor-relative pixels pass straight through — the Windows 65535 normalisation has no Linux counterpart. `hashi_gnome.py` implements this with 57 tests; **no D-Bus session has ever been created**. See [Mutter D-Bus contracts](docs/fedora-mutter-dbus-contracts.md).

**Fact (2026-11-08):** the host is now **wired together** in `hashi_host.py` — PipeWire capture → `encode_frame` → the validated transport, and inbound records → injection — with 249 tests passing in all. **It has never been run**, and that report carries no evidence ID on purpose: every layer beneath it is validated, their composition is not. See [host wiring](docs/fedora-host-wiring.md).

**MILESTONE — 2026-11-08 (FED-HOST-E001): the host works end to end.** The iPad displayed frames HASHI **generated** from a real Linux virtual monitor, and touches on its screen **moved the Linux pointer**. A pinned 1280×960 `RecordVirtual` monitor negotiated at exactly that size, PipeWire capture encoded to valid 1280×960 JPEGs, the handshake returned the same 2048×1536 / `diff_jpeg=False` as always, and a 30-second run took **1,540 inbound records → 1,540 injected** while capturing **820 damage-driven frames** — the compositor only redraws a virtual monitor when something changes, so 820 captures is the system's own proof the pointer was moving. See [host live validation](docs/fedora-host-live.md).

**The key trap, worth knowing before touching this code:** `NotifyPointerMotionAbsolute` is **silently discarded until something consumes the PipeWire stream**, while still returning success. Buttons land anyway, so the symptom is clicks at a stale position — selected text and odd window behaviour — with a pointer that never moves. Measured with Mutter's idle timer: 40 motion calls left idle climbing 14,741 → 15,605 ms with no consumer, and took it 20,683 → **21 ms** with one.

**Fact (2026-11-08):** frames identical to the previous one are no longer re-sent, which cut a near-static run from ~9.9 MB/s to **0.89 MB/s** (36 frames sent, 414 skipped in 15 s). Transmission is slowed rather than stopped — an unchanged frame still goes out once a second — because what the device does with a silent stream has never been observed.

**Fact (2026-11-08) — milestone 1 of the native port, superseded in counts by the 2026-11-09 entry below:** the **C++17 protocol core** is in [`native/`](native/) — usbmux, handshake, record framing and input decode, dependency-free, 56 tests, and **byte-identical to the Python reference on 19 conformance vectors**. Profiling first established that a native port is *not* a speed win (encode is 4.9 ms of a 33 ms budget and already native C); the gains are a single binary with no Python runtime and a base for the planned Rust implementation. See [native port](docs/native-port.md).

**Fact (2026-11-09): the native port is complete in scope — and has never been run.** `native/` now implements every subsystem the Python host has: the protocol core, JPEG frame generation, Mutter's D-Bus contracts, the live session over GIO, PipeWire capture over GStreamer, and the composed loop behind a `hashi` binary. 4,040 lines, **129 tests**, and agreement with the Python reference on **65 byte vectors, 9 GVariant payloads and 8 whole JPEG frames, 0 mismatches**. Three results are worth carrying forward:

- **libjpeg-turbo through the TurboJPEG API is byte-identical to the same library through Pillow**, on all 8 fixtures including 1280×960 pseudo-random noise and single-pixel chroma edges. Five parameters are load-bearing — quality 80, 4:2:0, and the three JFIF density settings, without which TurboJPEG writes "no units, 1×1" where the captured frames carry 120 dpi. A solid black buffer reproduces the captured first record exactly: 19,827 bytes, SHA-256 `317955d8…`.
- **The GVariant payloads the port would put on the bus are identical to PyGObject's**, down to dictionary ordering and the empty `@a{sv} {}` case — a stronger check than comparing the arguments as data, since it is the actual message.
- **Each comparison was given a negative control before being trusted.** A conformance harness that cannot fail proves nothing: quality 79-vs-80 and density 121-vs-120 are both caught (the second at *equal length*, so bytes are genuinely being read), and so is rendering the cursor mode as `int32` instead of `uint32`.

**Correction to the handoff:** no packages needed installing. `libturbojpeg` 3.1.4.1, `gstreamer-1.0`/`gstreamer-app-1.0` 1.28.8 and `gio-2.0` 2.90.1 are all present and link; the expected `sudo dnf install` step was unnecessary, and no `sudo` was used. See [native port](docs/native-port.md).

**The port being scope-complete is not the same as it working.** `hashi run` refuses without `--allow-session` and that flag has not been passed: no Mutter session has been opened by the native code, no GStreamer pipeline started, and no byte sent to the iPad from it. The ordering in `session.cpp` is copied from the Python host precisely because that ordering is what FED-HOST-E001 confirmed, but the composition is an **Inference** for this implementation. On the evidence of the Python host's first run, what a first native run would most plausibly expose is teardown ordering and the consumer gate — not the protocol, which is validated twice over.

**Fact (2026-11-09): a third implementation now agrees on the bytes.** `rust/` holds a dependency-free Rust core — usbmux and its plist subset, the handshake, record framing, the inbound decode, the JPEG prelude, Mutter's D-Bus arguments, the pipeline string and the pacer — with 45 tests, clippy clean. Conformance diffs **both** ports against the Python reference: **65 vectors against C++ and 65 against Rust, 0 mismatches**, plus the 9 GVariant payloads and 8 frames. Because nearly every vector is pure computation, Rust reaches the same coverage while linking nothing at all.

Why that is worth more than a third test suite: a test asserts what its author believed, while an independent implementation landing on the same bytes is evidence the decode itself is right. The negative control makes the point concretely — the comparison catches the `0xfc` record's field 1 being "fixed" to big-endian instead of reproduced as the little-endian 5 the agent actually writes, which is exactly the change a careful port would make unprompted. The crate takes no crates for the same reason: three implementations agreeing on bytes means nothing if they share the code that produces them.

**One divergence the port found, and the gap it reveals:** the inbound TLV sanity limit is 4096 in Python and C++; the Rust version was written as `0xFFFFFF` and no vector covers it, because the limit is a *refusal* path rather than a byte on the wire. It is now aligned. Vectors compare what the implementations emit, not what they refuse. See [Rust core](docs/rust-core.md).

**`hashi.sh`** builds whatever is present and runs all three suites plus conformance, defaulting to `check`, which touches no device: `./hashi.sh` to verify, `./hashi.sh plan` to see what a run would do, `./hashi.sh run` for the real thing (the binary still enforces `--allow-session`).

**Fact (2026-11-09): the Python host now has an entry point.** `python/hashi_cli.py` is the startup sequence FED-HOST-E001 used, as a supported command rather than an ad-hoc script kept with the instrumentation — which had in any case stopped working, since it imported the modules from the pre-`94b69e6` layout. It has the same three commands as the native binary, and `./hashi.sh plan|devices|run` now drives *it* rather than the native one, because it is the implementation that has actually worked; the native binary is the same commands under `native-`. **The ordering is the reason the file exists**: capture must be running and a first frame pulled before anything is injected, or Mutter discards every absolute motion while still returning success. 20 tests, including one that asserts that ordering by recording the call sequence.

Using it: plug the iPad in (usbmuxd is udev-activated, so nothing needs starting), open Splashtop Wired XDisplay, then `./hashi.sh run --allow-session`. `--solid` streams solid frames with no virtual monitor and no injection, which separates a transport fault from a capture one.

**Remaining:** a first live run of the native host; optionally switching `plist.cpp` to the now-installed `libplist` 2.7.0, which is a judgement call rather than a fix; whether to extend the Rust core with FFI to libjpeg-turbo or a D-Bus crate, which is a real trade-off since each costs the independence that makes its agreement meaningful; and the unexercised paths. Multi-touch, keyboard, `field0` 16/17, reconfiguration, the TLV `0x70` subtype and differential JPEG remain unexercised **in both implementations** — `field0` 3, 4, 7, 8, 9 and 11–17 have never been seen on the wire, only 5, 6 and 10.

**Resume from:** this Current Status section, then [native port](docs/native-port.md) and [Rust core](docs/rust-core.md) for the current frontier and [Fedora next steps](docs/fedora-next-steps.md) for the older backlog. The Windows return handoff `RETURN-TO-WINDOWS.md` was removed on 2026-11-08; there is no pending Windows work. The import receipt for the 2026-11-07 transfer is [Fedora backend import](docs/fedora-backend-import.md); its archive was verified and then deleted, and private evidence lives outside this checkout under `~/HASHI-private/`. The `hashi-stuff/` transfer folder referenced below is historical.

**Historical — returning to Windows with the private transfer ZIP:** this route is closed. `RETURN-TO-WINDOWS.md` and `WINDOWS-CODEX-HANDOFF.md` were removed on 2026-11-08, the protocol work they guided is finished, and the host now runs on Linux (FED-HOST-E001).

**2026-11-01 update:** Start with [Fedora next-session handoff](docs/fedora-next-steps.md) and [Fedora investigation](docs/fedora-investigation.md). **Fact:** HASHI still has no Linux host implementation or validated application protocol. The Windows handoff corrections and newer Windows/Fedora observations supersede the historical roadmap below; Windows runtime behavior has not been reproduced on Fedora.

**Phase 0 (Windows host architecture discovery) is mostly complete.** As of 2026-10-14 the active work is a **prerequisite-skills phase** (x64 assembly and Windows reversing) before any disassembly of `lci_iddcx.dll`. The ordered study plan and exercises are in [`docs/study-plan-x64-windows-reversing.md`](docs/study-plan-x64-windows-reversing.md) and [`study/`](study/). Week 1 is defined; Weeks 2–4 are outlines.

**Corrections made on resumption (2026-10-14, details in the devlog):** `IddCx0102` in the INF does not pin IddCx 1.2 (the current Windows 11 sample uses the same value); BinExport's Ghidra extension is stale for Ghidra 12 so diffing starts with Ghidra's built-in Version Tracking; `AppleSSD.sys` is a Boot Camp storage driver unrelated to the iPad link; and the wire protocol HASHI must reproduce lives in the Splashtop host agent and the USB traffic, not in the IddCx driver, so Phase 1 capture outranks Phase 0.75 diffing.

**What's confirmed:**
- Splashtop rides on Apple's own communication stack (Apple Mobile Device Service, Bonjour) for USB/iPad connectivity — not a proprietary USB layer of its own.
- Extended Display is powered by `lci_iddcx.dll`, a **UMDF (user-mode) driver** loaded via `WUDFRd`, built on Microsoft's **IddCx** framework (INF binding `IddCx0102`; the actual IddCx API level is set at build time and is most likely 1.3 or earlier given the December 2018 build date — inference).
- A second file, `lci_proxywddm.sys`, is a real kernel-mode driver ("LuminonCore WDDM PROXY") — its exact role is still unknown.
- `IndirectKmd` (Microsoft's kernel component) activates because `lci_iddcx.inf` declares it via `UpperFilters` — fully explained, no longer a mystery.
- The real frame handoff point, per Microsoft's own IddCx documentation, is the `EvtIddCxMonitorAssignSwapChain` callback.
- `lci_iddcx.dll` is very likely a **console IDD**, not a remote-session IDD (inference, not yet confirmed in the binary).
- The diffing toolchain has been corrected twice: **Diaphora is IDA-only** as of 2026, and **BinExport's prebuilt Ghidra extension stops at Ghidra 11.0.3** (open protobuf-mismatch bug). First pass is Ghidra 12's built-in Version Tracking and BSim; BinDiff only if BinExport builds against the installed Ghidra.

**Historical (2026-10-14) — what was in progress then:** Week 1 of the study plan (reading x64 from self-compiled C in Ghidra), to be followed by a Visual Studio / Windows SDK / WDK toolchain in the `win11` VM and a build of Microsoft's IDDCX sample. The study phase is complete and the driver build never happened: the Windows route closed once Phase 1 capture established that the wire protocol lives in the host agent rather than in the IddCx driver. See [`docs/driver-build-setup.md`](docs/driver-build-setup.md).

**Historical (2026-10-14) — what had not started then.** Every item below has since been either completed by another route or deliberately abandoned; none is pending:
- Enabling IddCx frame capture or WPP tracing against the real Splashtop host — **abandoned**; Phase 1 captured the application stream directly instead.
- Building the sample driver itself — **abandoned**; no driver build is pending.
- Any Ghidra work on `lci_iddcx.dll` — **superseded**; the Ghidra work that mattered went into the host agent, giving `CProbeUsbmuxd::DoHandshake` at RVA `0x303f0` (FED-START-E001) and the captor/encoder vtables (WIN-BACKEND-E001–E004).
- Anything on the actual Linux implementation — **done**; three implementations now exist and the Python host has run end to end (FED-HOST-E001).

## Investigation Methodology

Every research finding in this project is classified as:

- **Fact** – Directly observed or directly stated in official documentation.
- **Inference** – Logical conclusion from observed evidence.
- **Hypothesis** – Plausible explanation awaiting confirmation.

This discipline prevents assumptions from silently becoming "facts" as the investigation progresses.

## Research Documents

| Document | Covers |
|---|---|
| [`docs/splashtop-xdisplay-reversing-devlog.md`](docs/splashtop-xdisplay-reversing-devlog.md) | Phase 0 architecture discovery: driver enumeration, INF analysis, current model of the Windows host's driver stack. |
| [`docs/iddcx-reference.md`](docs/iddcx-reference.md) | Distilled reference on Microsoft's IddCx framework: object lifecycle, console vs. remote IDD modes, and the registry-driven debug facilities (frame capture, WPP tracing) that expose ground-truth data without disassembly. |
| [`docs/driver-build-setup.md`](docs/driver-build-setup.md) | Why and how to build Microsoft's sample IDD driver with debug symbols — toolchain requirements, PDB explanation, setup checklist. *Historical: the Windows route is closed and no driver build is pending.* |
| [`docs/reverse-engineering-methodology.md`](docs/reverse-engineering-methodology.md) | Full binary-diffing and driver-analysis workflow: Ghidra + BinDiff setup, how to identify vendor-added code, how to trace host↔driver IPC, and how findings get replaced with open-source Linux code without ever porting Splashtop's own code. |
| [`docs/study-plan-x64-windows-reversing.md`](docs/study-plan-x64-windows-reversing.md) | Prerequisite-skills plan: x64 assembly and Windows reversing scoped to reading a UMDF/IddCx driver. What to learn, what to skip, day-by-day Week 1 with check questions, outlines for Weeks 2–4, cheat sheets. Exercises in [`study/`](study/). *Historical: this phase is complete; do not restart it.* |

The Linux-side reports are the live ones; this table was written during Phase 0
and the rows above are historical. The current frontier is:

| Document | Covers |
|---|---|
| [`docs/native-port.md`](docs/native-port.md) | The C++17 port: its five-target layering, the three kinds of conformance comparison and the negative controls that license them, what each layer had to get right, and why scope-complete is not the same as working. **Current frontier.** |
| [`docs/rust-core.md`](docs/rust-core.md) | The dependency-free Rust core, why a third implementation is worth more than a third test suite, and the divergence it found. **Current frontier.** |
| [`docs/fedora-host-live.md`](docs/fedora-host-live.md) | FED-HOST-E001: the host working end to end — generated frames on the iPad, touch moving the Linux pointer, and the traps that cost the most time. |
| [`docs/fedora-mutter-dbus-contracts.md`](docs/fedora-mutter-dbus-contracts.md) | FED-DBUS-E001: every Mutter 51 `ScreenCast`/`RemoteDesktop` signature verified three ways, the pinned `modes` key, and the evdev button codes. |
| [`docs/linux-host-architecture.md`](docs/linux-host-architecture.md) | Why a userspace virtual monitor over Mutter's private D-Bus APIs, and what that rules out: no kernel module, no root, no `evdi`. |
| [`docs/fedora-host-wiring.md`](docs/fedora-host-wiring.md) | How the Python host's layers compose, and what a first run would and would not prove. |

## Current Architecture (Windows host, as understood so far)

```
                     Splashtop Host (Windows)
                               │
                    Apple Mobile Device Stack
                               │
                           USB / iPad
                               │
                               ▼
                   LuminonCore IDDCX Driver
           (lci_iddcx.dll — console-mode UMDF driver)
                               │
                               ▼
                    Windows UMDF Runtime → IndirectKmd
                               │
                               ▼
                    Windows Display Manager
```

## Linux Host Architecture (as built)

No kernel module and no root: the virtual monitor is a userspace one that Mutter
owns, and frames come back out of it over PipeWire. See
[Linux host architecture](docs/linux-host-architecture.md) for why, and what that
rules out.

```
                          iPad (USB)
                     Splashtop app, unmodified
                               │
                               ▼
                     usbmuxd (Unix socket)
          device discovery, Connect to port 6789 byte-swapped
                               │
                               ▼
                   HASHI host  (python/ · native/ · rust/)
        handshake · record framing · JPEG prelude · input decode
                        │                        ▲
       RecordVirtual    │                        │  type-7 records
       pinned 1280x960  ▼                        │  (absolute pixels)
              Mutter ScreenCast  ─────────────►  NotifyPointer*
              virtual monitor, cursor embedded   RemoteDesktop
                               │
                               ▼
                   PipeWire  ──►  GStreamer pipewiresrc
                               │
                               ▼
                 libjpeg-turbo, quality 80, 4:2:0
                 paced to 30 fps, unchanged frames skipped
                               │
                               ▼
              Frame reaches iPad's Splashtop renderer
```

## Development Phases

This roadmap was written at the start of the project, when the plan was to reach
Linux by way of a Windows driver analysis. **It is kept as a record of the
original plan, not as a description of the work.** The route actually taken was
shorter: Phase 1 capture established that the protocol lives in the host agent
and the USB traffic rather than in the IddCx driver, which closed the Windows
driver phases outright, and the Linux display layer landed on Mutter's D-Bus
APIs rather than on the `evdi` kernel module the plan assumed. Each phase below
carries its real outcome. The authoritative account is the Current Status
section above.

### Phase 0 — Windows Host Architecture Discovery

**Outcome: complete in what mattered; the rest abandoned with the Windows route.**
- [x] Baseline system snapshot (`driverquery`, services, Device Manager)
- [x] Identify Apple driver stack introduced by iTunes/Apple Devices install
- [x] Identify LuminonCore driver packages (`lci_iddcx.inf`, `lci_proxywddm.inf`) via `pnputil`
- [x] INF analysis — confirm UMDF/IddCx architecture, `IndirectKmd` upper filter relationship
- [x] Study Microsoft's IddCx framework documentation (object lifecycle, console vs. remote modes, debug tooling)
- [ ] Enable IddCx frame capture against the real Splashtop host — capture real frame data
- [ ] Capture WPP trace across mirror mode and extended-display mode — diff DDI call sequences
- [ ] Confirm IddCx version target (`IDDCX_MINIMUM_VERSION_REQUIRED` embedded in the binary, or `IddCxGetVersion` use) against Microsoft's version table — `IddCx0102` in the INF is not the answer (see devlog C1)
- [ ] Re-run `driverquery /v` for the Apple Mobile Device USB driver (`USBAAPL64.sys` or successor); drop `AppleSSD.sys` from the USB-side inventory
- [ ] Identify the host agent process (reported as `SWXDAgent.exe` by third-party guides; verify) and list its loaded DLLs and open handles
- [ ] Inspect `lci_proxywddm.inf` package to determine the kernel driver's actual responsibility
- [ ] Trace process interactions (Process Monitor/Process Explorer) between host app, `lci_iddcx.dll`, `lci_proxywddm.sys`

### Phase 0.25 — Prerequisite Skills

**Outcome: complete.** The skills phase and the Ghidra study check are done; do not
restart them and do not rebuild the study DLL. Week 1 was worked through in
[`study/week1/`](study/week1/); Weeks 2–4 were overtaken by the real agent
analysis rather than finished as exercises.
- [ ] Week 1: x64 reading from own compiled C (Ghidra 12.1.4 on Fedora, MinGW-built PE binaries) — `study/week1/`
- [ ] Week 2: PE format, MSVC idioms, C++ objects, Windows API calls; TryHackMe "Windows x64 Assembly" then "Windows Reversing Intro"
- [ ] Week 3: WDF/IddCx function-table and callback-table patterns; build and read the sample (overlaps Phase 0.5)
- [ ] Week 4: first structured look at `lci_iddcx.dll` with the checklist in the study plan (overlaps Phase 0.75)

### Phase 0.5 — Reference Binary Preparation

**Outcome: abandoned.** No toolchain was installed and no sample driver was ever
built. Nothing here is pending.
- [ ] Install Visual Studio 2022 or 2026 Community, Windows SDK, current WDK, in the existing `win11` Boxes VM
- [ ] Verify toolchain installation
- [ ] Clone `Windows-driver-samples`, locate `video/IndirectDisplay/`
- [ ] Inspect the sample project structure
- [ ] Build the sample as **Release + PDB** (closest shape to the vendor binary) and **Debug + PDB** (easiest to read)

### Phase 0.75 — Binary Diffing

**Outcome: abandoned as planned, superseded in substance.** No BinDiff/BinExport
or Version Tracking diff of `lci_iddcx.dll` was run. The disassembly that the
protocol actually needed was done directly against the Splashtop host agent —
see FED-START-E001 and WIN-BACKEND-E001–E004 in the Current Status section.
- [ ] Import both sample driver (with PDB) and `lci_iddcx.dll` into Ghidra
- [ ] Locate the WDF and IddCx function tables and the `IDD_CX_CLIENT_CONFIG` callback fill (names every DDI callback without diffing)
- [ ] Run Ghidra Version Tracking for a first-pass bulk match; try BSim
- [ ] BinDiff + BinExport only if BinExport builds against the installed Ghidra (prebuilt is stale; see devlog C3)
- [ ] Bucket functions: framework glue (ignore) / partial match (priority) / unmatched (pure vendor code)
- [ ] Open `lci_iddcx.dll` in Ghidra directly, informed by the diff results
- [ ] Trace Splashtop host ↔ driver IPC mechanism (Process Monitor → Process Explorer → API Monitor → WinDbg as needed)

### Phase 1 — Protocol Capture

**Outcome: complete (FED-FRAME-E001, FED-START-E001, FED-STREAM-E001).** The
application stream was captured and is reproduced offline byte-for-byte: the
record boundary, the handshake, 1,903 tag-6 JPEG records at 1280×960, and the
whole 130,375,177-byte host→device direction at the same SHA-256.
- [ ] Stop `usbmuxd` on the Fedora host, redirect the iPad into the `win11` VM (USB redirection, not VFIO), confirm the guest sees it
- [ ] Capture raw USB traffic (Wireshark + usbmon on the Fedora host) during connect/pairing
- [ ] Capture raw USB traffic (Wireshark + usbmon or equivalent) during mirror mode
- [ ] Capture raw USB traffic during extended-display mode
- [ ] Isolate control-channel framing from video-frame framing
- [ ] Identify handshake/pairing sequence at the application layer
- [ ] Identify video codec and frame container format

### Phase 2 — USB/Pairing Layer (Linux)

**Outcome: complete (FED-HOST-E001).** `usbmuxd` discovery and the
application-layer handshake are implemented in all three cores, and the real
unmodified Splashtop iPad app accepts the handshake and streams from it.
- [ ] Integrate `usbmuxd`/`libimobiledevice` for device discovery and tunnel setup
- [ ] Reimplement the application-layer handshake identified in Phase 1
- [ ] Confirm the real Splashtop iPad app accepts the handshake and considers HASHI a valid host

### Phase 3 — Passive Virtual Display

**Outcome: complete by a different route than planned.** `evdi` and DRM
writeback were both **ruled out** in favour of a userspace virtual monitor over
Mutter's `ScreenCast`/`RemoteDesktop` D-Bus APIs — no kernel module, no root.
See [Linux host architecture](docs/linux-host-architecture.md). `--solid`
streams a test pattern with no virtual monitor, which is the end-to-end pipe
proof this phase asked for.
- [ ] Stand up `evdi` (or DRM writeback) as a virtual display endpoint
- [ ] Confirm Linux recognizes and can render to the virtual display
- [ ] Prove the pipe end-to-end with a test pattern, no real frame data yet

### Phase 4 — Real Frame Pipeline

**Outcome: complete (FED-HOST-E001).** PipeWire capture → JPEG encode → the
validated transport, with generated frames visible on the iPad.
- [ ] Implement encode/decode matching the protocol identified in Phase 1
- [ ] Get working mirror mode against the real iPad app

### Phase 5 — Extended Display + Input

**Outcome: extended display complete; input partially exercised.** The virtual
monitor is a separate output rather than a mirror, and iPad touch moves the
Linux pointer. Multi-touch, keyboard and Pencil remain **decoded but never seen
on the wire** — only `field0` 5, 6 and 10 have ever been observed.
- [ ] Extended-display mode (separate virtual output, not mirrored)
- [ ] Touch/Pencil input passthrough into Linux input events

### Phase 6 — Native Integration

**Outcome: not done, and partly reconsidered.** There is no packaging and no
GPU-accelerated encode path; profiling showed encode is 4.9 ms of a 33 ms budget,
so the latter is not the win it was assumed to be. "Wayland-native" arrived in
the weaker sense that the host talks to a Wayland compositor over D-Bus, not as
a compositor-native virtual output.
- [ ] Wayland-native virtual output integration
- [ ] Packaging for distribution
- [ ] GPU-accelerated encode path

## Technical Stack (as built)

| Component | Technology | Differs from the original plan |
|---|---|---|
| Language | Python (reference, the one that has run), C++17 (`native/`), Rust (`rust/`) | Plan said Rust only; the reference implementation is Python and all three agree on the bytes |
| USB / device pairing | `usbmuxd` over its Unix socket, spoken directly | As planned, minus `libimobiledevice`: the plist subset needed is small enough to implement, so the cores stay dependency-light |
| Virtual display | Mutter `ScreenCast` + `RemoteDesktop` D-Bus APIs (`RecordVirtual`, pinned `modes`) | **Changed.** `evdi` and DRM writeback both ruled out — userspace only, no kernel module, no root |
| Compositor integration | GNOME / Mutter 51 on Wayland | **Changed.** wlroots-first and the X11/Xrandr fallback were never pursued |
| Capture | PipeWire via GStreamer `pipewiresrc` | GStreamer, as planned |
| Encode | libjpeg-turbo — Pillow (Python), TurboJPEG API (C++); baseline JPEG, quality 80, 4:2:0, 120 dpi | Plan left this open; the protocol turned out to require ordinary JPEG, not a video codec |
| Protocol capture tooling | Capture of the host agent's application stream | Wireshark/usbmon were not what produced the decode |
| Reverse engineering | Ghidra on the Splashtop host agent | Driver diffing (BinDiff/BinExport/ghidriff) never ran — see Phase 0.75 |

## License & Scope Note

This project does not include, redistribute, or depend on any Splashtop software, binaries, or proprietary protocol specifications. All findings are derived from independent observation of driver installation artifacts, publicly documented Microsoft platform APIs, and standard USB/display protocol analysis — in the same tradition as projects like Samba, Wine, and libimobiledevice. Raw captures (USB, WPP traces, frame dumps, pairing records) are never committed; only derived, described behavior is published.
