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
