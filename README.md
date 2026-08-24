# HASHI

**H**ost **A**dapter for **S**plashtop **H**ardware **I**nterop

A Linux host implementation that speaks Splashtop's wired display protocol — letting an unmodified iPad running the Splashtop app work as a real extended or mirrored display for a Linux machine over USB, the way Splashtop's own Windows/macOS host works today.

HASHI (橋, "bridge") is a clean-room, interoperability-motivated project. No Splashtop code, binaries, or proprietary assets are used or redistributed — only observed protocol behavior, documented Microsoft/Apple platform APIs, and standard Linux kernel interfaces.

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

**Phase 0 (Windows host architecture discovery) is mostly complete.** The active work is preparing a labeled reference binary for diffing against Splashtop's real driver — no disassembly of `lci_iddcx.dll` has started yet.

**What's confirmed:**
- Splashtop rides on Apple's own communication stack (Apple Mobile Device Service, Bonjour) for USB/iPad connectivity — not a proprietary USB layer of its own.
- Extended Display is powered by `lci_iddcx.dll`, a **UMDF (user-mode) driver** loaded via `WUDFRd`, built on Microsoft's **IddCx** framework at version `IddCx0102` specifically.
- A second file, `lci_proxywddm.sys`, is a real kernel-mode driver ("LuminonCore WDDM PROXY") — its exact role is still unknown.
- `IndirectKmd` (Microsoft's kernel component) activates because `lci_iddcx.inf` declares it via `UpperFilters` — fully explained, no longer a mystery.
- The real frame handoff point, per Microsoft's own IddCx documentation, is the `EvtIddCxMonitorAssignSwapChain` callback.
- `lci_iddcx.dll` is very likely a **console IDD**, not a remote-session IDD (inference, not yet confirmed in the binary).
- The diffing toolchain has been corrected once already: **Diaphora is IDA-only** as of 2026 with no working Ghidra support despite years "in development." The correct free tool for Ghidra is **BinDiff + BinExport** (Google, free, Apache-licensed).

**What's in progress right now:** installing the Visual Studio / Windows SDK / WDK toolchain needed to build Microsoft's official IDDCX sample driver with full debug symbols (PDB), to use as a labeled ground-truth baseline. See [`docs/driver-build-setup.md`](docs/driver-build-setup.md).

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
- [ ] Confirm IddCx version target (`IddCxGetVersion`) against Microsoft's version table
- [ ] Inspect `lci_proxywddm.inf` package to determine the kernel driver's actual responsibility
- [ ] Trace process interactions (Process Monitor/Process Explorer) between host app, `lci_iddcx.dll`, `lci_proxywddm.sys`

### Phase 0.5 — Reference Binary Preparation *(current focus)*
- [ ] Install Visual Studio 2022 Community, Windows SDK, Windows Driver Kit (version matched to IddCx 1.2)
- [ ] Verify toolchain installation
- [ ] Clone `Windows-driver-samples`, locate `video/IndirectDisplay/`
- [ ] Inspect the sample project structure
- [ ] Build the sample in Debug config with `/DEBUG` → produces `sample.dll` + PDB

### Phase 0.75 — Binary Diffing
- [ ] Import both sample driver (with PDB) and `lci_iddcx.dll` into Ghidra
- [ ] Run Ghidra Version Tracking for a first-pass bulk match
- [ ] Install BinDiff + BinExport, export both binaries, run full diff
- [ ] Bucket functions: framework glue (ignore) / partial match (priority) / unmatched (pure vendor code)
- [ ] Open `lci_iddcx.dll` in Ghidra directly, informed by the diff results
- [ ] Trace Splashtop host ↔ driver IPC mechanism (Process Monitor → Process Explorer → API Monitor → WinDbg as needed)

### Phase 1 — Protocol Capture
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
| Driver reverse engineering | Ghidra, BinDiff/BinExport |

## License & Scope Note

This project does not include, redistribute, or depend on any Splashtop software, binaries, or proprietary protocol specifications. All findings are derived from independent observation of driver installation artifacts, publicly documented Microsoft platform APIs, and standard USB/display protocol analysis — in the same tradition as projects like Samba, Wine, and libimobiledevice.
