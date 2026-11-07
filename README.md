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

**Fact:** Repository code is now `hashi_framing.py` (validated record/JPEG-header parser), `hashi_startup.py` (handshake codec, no I/O), `hashi_stream.py` (steady-state codec, no I/O), `hashi_jpeg.py` (frame prelude), `hashi_usbmux.py` (transport, no I/O) and `hashi_mode.py` (FED-MODE-E001 dimension rules, with the reconstructed `FindBestResolution` scorer marked **Inference** and not wired into anything), with 128 passing tests in `tests/`. **There is still no Linux host implementation and no validated application protocol beyond the record boundary.** No guessed handshake, resize, codec or control message has been implemented, and none should be.

**Fact (2026-11-08, FED-ARCH/JPEG/USBMUX-E001):** The Linux side is now designed and partly built. The **architecture is settled**: GNOME Shell 51.1 on Wayland exposes `org.gnome.Mutter.ScreenCast.Session.RecordVirtual`, a userspace **virtual monitor** the desktop genuinely extends onto and which streams over PipeWire, plus `RemoteDesktop` input injection reporting `SupportedDeviceTypes = 7` (keyboard, pointer, touchscreen). So no kernel module, no root, no `evdi`. See [Linux host architecture](docs/linux-host-architecture.md).

**Fact:** the **JPEG frame prelude** is reproducible: all 1,903 captured records share a 623-byte prelude built entirely from published ISO/IEC 10918-1 Annex K tables at **quality 80**, 1280×960, 4:2:0 — verified 1903/1903 and 12/12 against the capture. No vendor table data is transcribed. See [JPEG frames](docs/fedora-jpeg-frames.md). The **usbmux transport** is implemented and validated against the captured control exchange, including the byte-swapped `PortNumber` (6789 → 34074). See [usbmux transport](docs/fedora-usbmux-transport.md).

**Remaining to a working host:** the JPEG entropy coder (DCT, quantize, Huffman — no protocol unknowns left in it), the PipeWire capture and Mutter virtual-monitor plumbing, and input injection. **Nothing has ever been transmitted to the iPad**; that remains the user's decision.

**Resume from:** [Model handoff](MODEL-HANDOFF.md), then [Fedora next steps](docs/fedora-next-steps.md). Returning to Windows instead: [RETURN-TO-WINDOWS.md](RETURN-TO-WINDOWS.md). The import receipt for the 2026-11-07 transfer is [Fedora backend import](docs/fedora-backend-import.md); its archive was verified and then deleted, and private evidence lives outside this checkout under `~/HASHI-private/`. The `hashi-stuff/` transfer folder referenced below is historical.

**Returning to Windows with the private transfer ZIP:** Start with [RETURN-TO-WINDOWS.md](RETURN-TO-WINDOWS.md). Include the ignored `hashi-stuff/` folder in that private transfer; it contains the Windows artifacts and new Fedora evidence bundle.

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

**What's in progress right now:** Week 1 of the study plan (reading x64 from self-compiled C in Ghidra). After that: install the Visual Studio / Windows SDK / WDK toolchain in the existing GNOME Boxes `win11` VM and build Microsoft's IDDCX sample as Release + PDB and Debug + PDB. See [`docs/driver-build-setup.md`](docs/driver-build-setup.md).

**Not started yet:**
- Enabling IddCx frame capture or WPP tracing against the real Splashtop host (documented, ready to run).
- Building the sample driver itself.
- Any Ghidra work on `lci_iddcx.dll`.
- Anything on the actual Linux implementation — no code exists yet.

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
| [`docs/driver-build-setup.md`](docs/driver-build-setup.md) | Why and how to build Microsoft's sample IDD driver with debug symbols — toolchain requirements, PDB explanation, setup checklist. **Current active work.** |
| [`docs/reverse-engineering-methodology.md`](docs/reverse-engineering-methodology.md) | Full binary-diffing and driver-analysis workflow: Ghidra + BinDiff setup, how to identify vendor-added code, how to trace host↔driver IPC, and how findings get replaced with open-source Linux code without ever porting Splashtop's own code. |
| [`docs/study-plan-x64-windows-reversing.md`](docs/study-plan-x64-windows-reversing.md) | Prerequisite-skills plan: x64 assembly and Windows reversing scoped to reading a UMDF/IddCx driver. What to learn, what to skip, day-by-day Week 1 with check questions, outlines for Weeks 2–4, cheat sheets. Exercises in [`study/`](study/). **Current active work.** |

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

## Planned Linux Host Architecture

```
                          iPad (USB)
                     Splashtop app, unmodified
                               │
                               ▼
                usbmuxd / libimobiledevice
              USB mux, pairing, lockdownd tunnel
                               │
                               ▼
                Protocol-compat daemon (Rust)
        Handshake, framing, codec, input events
                        │              │
                        ▼              ▼
              evdi kernel driver   DRM writeback
              (virtual display)    (alternative)
                        │              │
                        └──────┬───────┘
                               ▼
                Wayland compositor / X11 (Xrandr)
             Registers virtual output, composites frame
                               │
                               ▼
                     Encode + send back
                 GStreamer / FFmpeg over USB
                               │
                               ▼
              Frame reaches iPad's Splashtop renderer
```

## Development Phases

### Phase 0 — Windows Host Architecture Discovery
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

### Phase 0.25 — Prerequisite Skills *(current focus, started 2026-10-14)*
- [ ] Week 1: x64 reading from own compiled C (Ghidra 12.1.4 on Fedora, MinGW-built PE binaries) — `study/week1/`
- [ ] Week 2: PE format, MSVC idioms, C++ objects, Windows API calls; TryHackMe "Windows x64 Assembly" then "Windows Reversing Intro"
- [ ] Week 3: WDF/IddCx function-table and callback-table patterns; build and read the sample (overlaps Phase 0.5)
- [ ] Week 4: first structured look at `lci_iddcx.dll` with the checklist in the study plan (overlaps Phase 0.75)

### Phase 0.5 — Reference Binary Preparation
- [ ] Install Visual Studio 2022 or 2026 Community, Windows SDK, current WDK, in the existing `win11` Boxes VM
- [ ] Verify toolchain installation
- [ ] Clone `Windows-driver-samples`, locate `video/IndirectDisplay/`
- [ ] Inspect the sample project structure
- [ ] Build the sample as **Release + PDB** (closest shape to the vendor binary) and **Debug + PDB** (easiest to read)

### Phase 0.75 — Binary Diffing
- [ ] Import both sample driver (with PDB) and `lci_iddcx.dll` into Ghidra
- [ ] Locate the WDF and IddCx function tables and the `IDD_CX_CLIENT_CONFIG` callback fill (names every DDI callback without diffing)
- [ ] Run Ghidra Version Tracking for a first-pass bulk match; try BSim
- [ ] BinDiff + BinExport only if BinExport builds against the installed Ghidra (prebuilt is stale; see devlog C3)
- [ ] Bucket functions: framework glue (ignore) / partial match (priority) / unmatched (pure vendor code)
- [ ] Open `lci_iddcx.dll` in Ghidra directly, informed by the diff results
- [ ] Trace Splashtop host ↔ driver IPC mechanism (Process Monitor → Process Explorer → API Monitor → WinDbg as needed)

### Phase 1 — Protocol Capture *(higher priority than Phase 0.75; see devlog C5)*
- [ ] Stop `usbmuxd` on the Fedora host, redirect the iPad into the `win11` VM (USB redirection, not VFIO), confirm the guest sees it
- [ ] Capture raw USB traffic (Wireshark + usbmon on the Fedora host) during connect/pairing
- [ ] Capture raw USB traffic (Wireshark + usbmon or equivalent) during mirror mode
- [ ] Capture raw USB traffic during extended-display mode
- [ ] Isolate control-channel framing from video-frame framing
- [ ] Identify handshake/pairing sequence at the application layer
- [ ] Identify video codec and frame container format

### Phase 2 — USB/Pairing Layer (Linux)
- [ ] Integrate `usbmuxd`/`libimobiledevice` for device discovery and tunnel setup
- [ ] Reimplement the application-layer handshake identified in Phase 1
- [ ] Confirm the real Splashtop iPad app accepts the handshake and considers HASHI a valid host

### Phase 3 — Passive Virtual Display
- [ ] Stand up `evdi` (or DRM writeback) as a virtual display endpoint
- [ ] Confirm Linux recognizes and can render to the virtual display
- [ ] Prove the pipe end-to-end with a test pattern, no real frame data yet

### Phase 4 — Real Frame Pipeline
- [ ] Implement encode/decode matching the protocol identified in Phase 1
- [ ] Get working mirror mode against the real iPad app

### Phase 5 — Extended Display + Input
- [ ] Extended-display mode (separate virtual output, not mirrored)
- [ ] Touch/Pencil input passthrough into Linux input events

### Phase 6 — Native Integration
- [ ] Wayland-native virtual output integration
- [ ] Packaging for distribution
- [ ] GPU-accelerated encode path

## Technical Stack (planned)

| Component | Technology |
|---|---|
| Language | Rust |
| USB / device pairing | `usbmuxd`, `libimobiledevice` |
| Virtual display | `evdi` kernel driver (primary), DRM writeback (alternative) |
| Compositor integration | Wayland (wlroots-based first), X11/Xrandr as fallback |
| Encode/decode | GStreamer or FFmpeg |
| Protocol capture tooling | Wireshark, usbmon |
| Driver reverse engineering | Ghidra 12 (Version Tracking, BSim); BinDiff/BinExport or ghidriff if they build against it |

## License & Scope Note

This project does not include, redistribute, or depend on any Splashtop software, binaries, or proprietary protocol specifications. All findings are derived from independent observation of driver installation artifacts, publicly documented Microsoft platform APIs, and standard USB/display protocol analysis — in the same tradition as projects like Samba, Wine, and libimobiledevice. Raw captures (USB, WPP traces, frame dumps, pairing records) are never committed; only derived, described behavior is published.
