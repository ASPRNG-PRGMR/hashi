# Reverse Engineering Devlog

**Project:** Splashtop Wired XDisplay (Windows Host)
**Investigation Phase 1 — Architecture Discovery**

## Objective

Determine how the Windows host application creates and manages a virtual display for an iPad connected over USB.

The goal is not to reverse engineer implementation details yet, but to identify the software architecture, installed components, and communication layers.

## Investigation Methodology

The investigation followed a strict evidence-based workflow.

Every observation was classified as:

- **Fact** – Directly observed.
- **Inference** – Logical conclusion from observed evidence.
- **Hypothesis** – Plausible explanation awaiting confirmation.

This prevents assumptions from becoming "facts."

## Phase 1 — Baseline System Snapshot

Before installing any software, baseline information was collected.

**Tools used:**

```
driverquery /v
```

Additional baseline information collected included:

- Installed drivers
- Installed services
- Device Manager state
- Network adapters
- Existing Apple drivers (none initially)

**Purpose:** To identify every component introduced by later installations.

## Phase 2 — Apple Driver Installation

**Installed:** Apple Devices / iTunes communication stack

**New observations:**

Running services:

- Apple Mobile Device Service
- Bonjour Service

Additional Apple drivers appeared, including:

- `AppleKmdfFilter.sys`
- `AppleLowerFilter.sys`
- `AppleSSD.sys`

**Initial assumption:** Splashtop probably relies on Apple's communication layer instead of implementing the proprietary USB protocol itself.

**Status:** Inference

## Phase 3 — Splashtop Installation

Splashtop installed successfully.

Initially:

- Mirror mode worked.
- Extended Display required installation of an additional display driver.

This suggested two independent subsystems:

1. USB communication
2. Virtual display creation

## Phase 4 — Driver Comparison

Two complete snapshots were collected.

**Before installation:**

```
driverquery /v > before_virtual_driver.txt
```

**After installation:**

```
driverquery /v > after_virtual_driver.txt
```

Comparison revealed two significant observations.

### Discovery 1 — IndirectKmd Activation

**Before installation:**
- `IndirectKmd` — State: Stopped

**After installation:**
- `IndirectKmd` — State: Running

**Observation:** Windows' own Indirect Display kernel component becomes active.

**Evidence:** `driverquery`

**Classification:** Fact

### Discovery 2 — New Kernel Driver

New kernel driver detected:

- **Module:** `lci_proxywdd`
- **Driver:** `lci_proxywddm.sys`

**Observed path:**

```
C:\Windows\System32\drivers\lci_proxywddm.sys
```

**Description:** LuminonCore WDDM PROXY

**Classification:** Fact

## Phase 5 — Driver Package Enumeration

**Tool:**

```
pnputil /enum-drivers
```

This revealed two LuminonCore driver packages.

### Package 1

- **Published name:** `oem1.inf`
- **Original name:** `lci_iddcx.inf`
- **Provider:** LuminonCore
- **Class:** Display
- **Class Version:** 2.0
- **Driver Version:** 1.0.2018.1204

**Driver package stored as:**

```
C:\Windows\INF\oem1.inf
```

**Original package located in Driver Store:**

```
C:\Windows\System32\DriverStore\FileRepository\<lci_iddcx package>\
```

Inside that package:

- `lci_iddcx.inf`
- `lci_iddcx.dll`
- `lci_iddcx.cat`

*(Actual folder name is architecture/version-dependent.)*

### Package 2

- **Published name:** `oem2.inf`
- **Original name:** `lci_proxywddm.inf`
- **Provider:** LuminonCore
- **Class:** System
- **Driver Version:** 1.0.2018.1204

**Observed kernel driver:**

```
C:\Windows\System32\drivers\lci_proxywddm.sys
```

**Classification:** Fact

## Phase 6 — INF Analysis

Opened: `lci_iddcx.inf`

| Observation | Meaning | Classification |
|---|---|---|
| `Class = Display` | This package installs a Display-class driver. | Fact |
| `ServiceBinary=%12%\UMDF\lci_iddcx.dll` | The actual implementation is `lci_iddcx.dll` rather than `lci_iddcx.sys` | Fact |
| `UmdfLibraryVersion = 2.15` | The driver uses Windows User Mode Driver Framework (UMDF) v2 | Fact |
| `UmdfExtensions = IddCx0102` | The driver is built on Microsoft's Indirect Display Driver Class Extension (IDDCX) | Fact |
| `UpperFilters = IndirectKmd` | Windows inserts Microsoft's `IndirectKmd` above this driver. This perfectly explains why `IndirectKmd` became active after installation. | Fact |
| `AddService = WUDFRd` | Windows loads this driver through Windows User Mode Driver Framework Reflector instead of installing a custom kernel service. | Fact |
| `ServiceBinary=%12%\UMDF\lci_iddcx.dll` (runtime location) | Actual runtime location: `C:\Windows\System32\drivers\UMDF\lci_iddcx.dll` | Fact |

## Current Architecture

Current evidence supports the following architecture:

```
                         Splashtop Host
                               │
                               │
                    Apple Mobile Device Stack
                               │
                               │
                           USB / iPad
                               │
                               │
                 ---------------------------------
                               │
                               ▼
                   LuminonCore IDDCX Driver
           (lci_iddcx.dll — User Mode Driver)
                               │
                               ▼
                    Windows UMDF Runtime
                               │
                               ▼
                         IndirectKmd
                    (Microsoft Kernel Component)
                               │
                               ▼
                 Windows Display Driver Model
                               │
                               ▼
                    Windows Display Manager
```

## Components Identified

| Component | Type | Status |
|---|---|---|
| Apple Mobile Device Service | Service | Confirmed |
| Bonjour Service | Service | Confirmed |
| `lci_iddcx.dll` | UMDF Display Driver | Confirmed |
| `lci_iddcx.inf` | Driver Package | Confirmed |
| `lci_proxywddm.sys` | Kernel Driver | Confirmed |
| `IndirectKmd` | Microsoft Kernel Component | Confirmed |
| `WUDFRd` | UMDF Reflector | Confirmed |
| `IDDCX` | Microsoft Display Framework | Confirmed |

## Files Identified

**Windows Driver Store**

```
C:\Windows\System32\DriverStore\FileRepository\<lci_iddcx package>\
```

Contains:

- `lci_iddcx.inf`
- `lci_iddcx.dll`
- `lci_iddcx.cat`

**Installed INF**

```
C:\Windows\INF\oem1.inf
```

Original: `lci_iddcx.inf`

**UMDF Driver**

```
C:\Windows\System32\drivers\UMDF\lci_iddcx.dll
```

**Kernel Driver**

```
C:\Windows\System32\drivers\lci_proxywddm.sys
```

## Open Questions

These remain unresolved.

1. **What is `lci_proxywddm.sys` responsible for?**
   - Known: Exists, kernel-mode, installed by LuminonCore
   - Unknown: Whether it communicates with `lci_iddcx.dll`; whether it exposes a virtual device; whether it is only a helper

2. **How does Splashtop communicate with the UMDF driver?**
   - Unknown: IOCTLs, COM, RPC, Named Pipes, ALPC, Device Interface APIs

3. **How does the user-mode application deliver rendered frames to the IDDCX driver?**
   - Unknown.

4. **How does Apple USB communication integrate with the display pipeline?**
   - Unknown.

## Planned Next Steps

1. ✅ Study Microsoft's IDDCX architecture — see [`iddcx-reference.md`](./iddcx-reference.md) for distilled findings from the official documentation. Key results: `lci_iddcx.dll` is very likely a **console IDD** (not remote-session); the real frame handoff point is `EvtIddCxMonitorAssignSwapChain`; and IddCx has built-in, registry-driven debug facilities (frame capture, WPP tracing) that provide ground truth without any disassembly.
2. **New — before Ghidra:** Enable IddCx frame capture (`IddCxFrameCapture` registry keys) against the real Splashtop host to dump the actual desktop frames handed to `lci_iddcx.dll` — confirms resolution, pixel format, and frame cadence via a documented OS debug feature, not driver reverse engineering.
3. **New — before Ghidra:** Capture a WPP trace (`logman`, flags `0x1f4`) across both mirror mode and extended-display mode. Diff the DDI call sequences to map which callbacks fire, and in what order, during real operation.
4. **New:** Cross-reference `IddCxGetVersion`'s returned value against Microsoft's IddCx version table to pin down exactly which IddCx feature set `lci_iddcx.dll` targets (INF suggests `IddCx0102` — an older, narrower surface than current versions), so later disassembly isn't misread against newer-version-only behavior.
5. Inspect the full `lci_proxywddm.inf` package and its associated files to determine the kernel driver's purpose — specifically whether it participates in the `EvtIddCxMonitorAssignSwapChain` frame loop at all, or is isolated to USB endpoint management.
6. Trace process interactions between the Splashtop host application, `lci_iddcx.dll`, and `lci_proxywddm.sys` using Process Monitor or Process Explorer.
7. Open `lci_iddcx.dll` in Ghidra, using the frame-capture and WPP findings from steps 2–3 to identify which functions correspond to `EvtIddCxMonitorAssignSwapChain` and the per-frame processing loop, rather than starting cold.
8. Correlate USB communication (Apple stack) with display events to understand where the rendering pipeline hands off frames.

## Current Confidence Assessment

| Statement | Confidence |
|---|---|
| Splashtop uses Apple's communication stack for USB connectivity | High |
| Virtual display is implemented using Microsoft's IDDCX framework | Certain |
| `lci_iddcx.dll` is the primary UMDF display driver | Certain |
| `IndirectKmd` is activated because the IDDCX driver requests it as an upper filter | Certain |
| `lci_proxywddm.sys` participates in the virtual display subsystem | High |
| `lci_iddcx.dll` is a console IDD, not a remote-session IDD | Medium (inference from IddCx spec, not yet confirmed in binary) |
| `EvtIddCxMonitorAssignSwapChain` is the real frame handoff point in the driver | High (documented behavior, not yet located in binary) |
| The exact role of `lci_proxywddm.sys` | Unknown |
| The exact IPC mechanism between Splashtop and the driver | Unknown |

---

## Resumption 2026-10-14 — Corrections and Re-verification

Resumed after a break of more than a month. Before continuing, every tool and version claim in the project brief was re-checked against current primary sources. Items below supersede earlier statements where they conflict.

### C1. `UmdfExtensions = IddCx0102` does **not** pin the driver to IddCx 1.2

**Fact:** Microsoft's current sample INF (`Windows-driver-samples`, `IddSampleDriver.inf`, main branch, which targets Windows 11 build 22000+) still declares `UmdfExtensions = IddCx0102`. The first public commit of the sample (2020-02-19, `d43983a97c`) declares the same value.
**Fact:** Microsoft's "Building IddCx 1.4 drivers" page says the IddCx version a driver targets is set at build time by the WDK headers plus `IDDCX_MINIMUM_VERSION_REQUIRED`, and is checked at runtime with `IddCxGetVersion` / `IDD_IS_FUNCTION_AVAILABLE`. The INF value is the UMDF class-extension binding, not the IddCx API level.
**Fact (version table):** IddCx 1.2 = 0x1200 shipped in Windows 10 1709; 1.3 = 0x1300/0x1380 in 1803/1809; 1.4 = 0x1400 in 1903; 1.5 in 2004–22H2; 1.8/1.9/1.10 in Windows 11 21H2/22H2/23H2; 1.11 is current prerelease.
**Inference:** `lci_iddcx.dll` (file version 1.0.2018.1204) was built in December 2018, when the newest shipping WDK was 1809 (IddCx 1.3). It is therefore most likely an IddCx 1.3-or-earlier driver, not specifically 1.2.
**Hypothesis:** The required minimum version is embedded in the binary in the class-extension binding data the IddCx stub library emits. Confirm in Ghidra once the WDK header is available to compare against.
**Consequence:** Do not try to match a 2017-era WDK for the baseline build. Build the current sample with the current WDK.

### C2. Microsoft's public sample post-dates the Splashtop driver

**Fact:** The `video/IndirectDisplay` sample was added to `Windows-driver-samples` on 2020-02-19. `lci_iddcx.dll` is dated 2018-12-04.
**Inference:** LuminonCore did not derive from this public sample. Expect lower similarity in diffing than "sample plus vendor additions". The sample is still the right textbook for the framework's shape.

### C3. BinExport's Ghidra extension is stale for current Ghidra

**Fact:** Ghidra's latest release is 12.1.4 (2026-09-21); it requires Java 21+ with no upper bound (`application.java.min=21`, `application.java.max=` empty). Fedora has no Ghidra package; this machine has OpenJDK 25.
**Fact:** The newest prebuilt BinExport Ghidra extension is tagged for Ghidra 11.0.3 (April 2024). google/binexport issue #144 (protobuf version mismatch, `IllegalAccessError` at export) is open with comments through 2025-10-29 and no confirmed fix. BinDiff 8's release notes do not mention Ghidra at all.
**Consequence:** The methodology's "BinDiff + BinExport, bundled prebuilt" step is not reliable today. Revised order: Ghidra Version Tracking (built in) → Ghidra BSim (built in since 11.x) → `ghidriff` (Python, pyghidra-based; verify it supports Ghidra 12 before relying on it) → BinDiff only if BinExport builds cleanly against the installed Ghidra. See `reverse-engineering-methodology.md`.
**Fact (unchanged):** Diaphora remains IDA-only. Latest release 3.1.x (2024); Ghidra support still "in development".

### C4. `AppleSSD.sys` is not part of the Apple Mobile Device stack

**Fact:** `AppleSSD.sys` is Apple's Boot Camp storage driver for internal SSDs in Macs running Windows (Apple support threads, Winclone documentation).
**Inference:** Its presence in the Phase 2 driver list is either because the test machine is a Mac in Boot Camp, or a misattribution. It plays no role in iPad USB communication.
**Action:** Re-run `driverquery /v` and look for the Apple Mobile Device USB driver (historically `USBAAPL64.sys`, "Apple Mobile Device USB Composite Device") to complete the USB-side inventory. Keep `AppleKmdfFilter.sys` and `AppleLowerFilter.sys` as the USB-relevant entries.

### C5. The IddCx driver is not where the wire protocol lives (priority change)

**Fact:** Splashtop's own support article for extending an iOS device on Windows requires iTunes installed and the device visible in iTunes; the "Virtual Display Driver" is a separate install only needed for extended mode. Third-party troubleshooting guides name the host process as `SWXDAgent.exe` (unverified; confirm with Task Manager / Process Explorer).
**Inference:** The component HASHI must reproduce bit-for-bit is the protocol between the host agent process and the iPad app, carried over Apple's USB multiplexing. The IddCx driver only produces desktop frames for that agent; on Linux, `evdi` replaces the driver outright.
**Consequence:** Phase 1 (USB capture) and analysis of the host agent's network/usbmux behavior are higher value than Phase 0.75 (driver diffing). Driver reversing stays in the plan for learning and for the "how do frames reach the agent" question, but it is no longer the critical path.
**Hypothesis:** The agent connects to a TCP port the iPad app listens on through usbmuxd (host-initiated, as `iproxy` does on Linux); the iPad cannot initiate connections to the host over usbmux. If the session is TLS-encrypted, `usbmon` captures will show ciphertext and the protocol will have to be observed inside the agent process instead.

### C6. Toolchain and VM facts as of 2026-10-14

**Fact:** The WDK now officially supports Visual Studio 2026 as well as VS 2022 (Windows Driver Developer Blog announcement, 2026). Microsoft's "Download the WDK" page lagged behind and still said to use VS 2022 at the time of checking. Either works.
**Fact:** A Release build also produces a PDB. The earlier note that only Debug builds keep names was wrong: names come from the PDB, optimization level comes from the configuration. For diffing against a shipped (Release) vendor binary, build the sample as **Release with PDB**; build Debug too for easier reading.
**Fact:** This Fedora host already has: `gnome-boxes` 50 with an existing `win11` VM image (24 GB, last modified 2026-09-02), `virt-manager`, `qemu-kvm` 10.2, `usbredir`, `usbmuxd` 1.1.1, `libimobiledevice` 1.4.0, `wireshark` 4.6.9, the `usbmon` kernel module, `mingw64-gcc` 16 (builds Windows PE binaries locally), `gdb` 17, OpenJDK 25. Ghidra is not installed.
**Fact:** TryHackMe's "Windows Reversing Intro" is the second room of a series; "Windows x64 Assembly" (tryhackme.com/room/win64assembly) is the first. Both use IDA Freeware in-room.

### C7. Wording: "clean-room"

A strict clean-room process (Phoenix/Compaq style) uses separate analysis and implementation teams. A solo project cannot do that. The accurate description is "interoperability-driven reverse engineering with no code copied", which is also the basis of the Samba, Wine and libimobiledevice comparisons. The README wording is adjusted accordingly. Related practice: never commit USB captures, WPP traces, frame dumps, or pairing records to the public repo; they may contain Splashtop assets, device identifiers, or personal data. Keep them in a local, ignored directory and publish only derived findings.
