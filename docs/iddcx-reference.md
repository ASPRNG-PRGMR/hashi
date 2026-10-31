# IddCx Reference Notes

**Project:** HASHI (Host Adapter for Splashtop Hardware Interop)
**Source:** Microsoft Learn — Windows Hardware Developer documentation, "Indirect display drivers" chapter (IddCx overview, IddCx Objects, Debugging IDDs, IddCx versions, IddCx 1.4+ remote/console updates)
**Purpose:** Distilled reference for understanding the Microsoft-supplied framework that `lci_iddcx.dll` (LuminonCore, used by Splashtop) is built on, ahead of any disassembly work.

Classification follows the same convention as the reversing devlog:

- **Fact** – Directly stated in Microsoft's documentation.
- **Inference** – Logical conclusion combining documentation with prior devlog findings.
- **Hypothesis** – Plausible explanation awaiting confirmation against the real driver.

---

## 1. What an IDD Is

**Fact:** An Indirect Display Driver (IDD) is a third-party UMDF (User-Mode Driver Framework) driver. It has no kernel-mode component of its own — IddCx is a *class extension*, meaning Windows supplies the kernel-side plumbing and the vendor only writes user-mode code.

**Fact:** Typical IDD use cases per Microsoft: remote display streaming, virtual monitors (virtual desktop environments), and USB-to-physical-monitor dongles.

**Fact:** The driver may only use DirectX APIs to process the desktop image. It must not call GDI, windowing APIs, OpenGL, or Vulkan.

**Fact:** The IDD runs in Session 0, with no components in the user session — so a driver crash doesn't take down the interactive desktop.

**Inference:** This matches Phase 6 of the reversing devlog exactly — `lci_iddcx.dll` runs as a UMDF driver via `WUDFRd`, with no matching kernel service of its own, consistent with the IDD model described here.

---

## 2. Object Lifecycle

**Fact:** IddCx objects are created in a strict order, each a child of the previous:

```
IDDCX_ADAPTER
      └── IDDCX_MONITOR
                └── IDDCX_SWAPCHAIN
                └── IDDCX_OPMCTX   (protected content, optional, can be multiple)
```

**Fact — IDDCX_ADAPTER:** Created via `IddCxAdapterInitAsync`, completed by the OS calling `EvtIddCxAdapterInitFinished`. No explicit destroy callback exists — the adapter is valid until the underlying UMDF device is stopped.

**Fact — IDDCX_MONITOR:** Created via `IddCxMonitorCreate`, then `IddCxMonitorArrival` to complete arrival. Removed via `IddCxMonitorDeparture`, which destroys the object. Re-plugging the same monitor requires the full departure/arrival sequence again — there's no "refresh" path.

**Fact — IDDCX_SWAPCHAIN:** Represents the buffer(s) delivering desktop images to a monitor. Multiple buffers let the OS compose the next frame while the driver reads the current one. Created and destroyed *by the OS*, assigned to a monitor via `EvtIddCxMonitorAssignSwapChain` and unassigned via `EvtIddCxMonitorUnassignSwapChain`.

**Fact — IDDCX_OPMCTX:** Output Protection Manager context, for protected-content scenarios. Multiple can be active per monitor simultaneously.

**Inference:** `EvtIddCxMonitorAssignSwapChain` is the single most important callback for understanding Splashtop's pipeline — it's the handoff point where the driver takes ownership of a swapchain and begins pulling frames. Any USB-bound frame transmission logic in `lci_iddcx.dll` almost certainly originates from the frame-processing loop started here.

**Fact:** Once `EvtIddCxMonitorAssignSwapChain` returns successfully, the driver owns the swapchain object. On unrecoverable error it should call `IddCxReportCriticalError`; on recoverable error it can `WdfObjectDelete` the swapchain, causing the OS to create a new one.

**Fact:** A watchdog (`TerminateIndirectOnStall`) kills the driver if it fails to process a frame within 10 seconds of the frame becoming available. This is enabled by default; disabling it fails HLK certification.

---

## 3. Console IDD vs. Remote IDD — a real fork in the spec

**Fact:** IddCx supports two distinct adapter modes, declared at `IddCxAdapterInitAsync` time via `IDDCX_ADAPTER_CAPS.Flags`:

- **Console IDD** — the default. Represents a monitor attached to the local interactive session (dongles, local virtual displays).
- **Remote IDD** — declared via `IDDCX_ADAPTER_FLAGS_REMOTE_SESSION_DRIVER`. Built for RDP-style *separate Windows sessions*. The OS actively enforces this: it fails adapter init if a remote-session device doesn't set the flag, and equally fails it if a non-remote device does set it.

**Fact:** Remote IDDs have additional constraints not present for console IDDs:
- Must set `IDDCX_ADAPTER_FLAGS_USE_SMALLEST_MODE` (no virtual modes — swapchain always matches desktop resolution exactly).
- Only progressive scan modes are permitted.
- Display configuration is driven by `IddCxDisplayConfigUpdate`, with an explicit state machine governing how monitor arrival/departure interacts with the currently active display topology (Microsoft documents four worked scenarios for this).
- Recommended to run with `UmdfHostProcessSharing = ProcessSharingDisabled` so each remote session gets its own driver process.

**Inference:** Splashtop's Extended Display feature presents as a real, local, console-session desktop extension — not a separate Windows session the way Remote Desktop is. This strongly suggests `lci_iddcx.dll` is a **console IDD**, not a remote one. That rules out the entire remote-session state machine (multi-monitor arbitration via `IddCxDisplayConfigUpdate`, session idle/disconnect handling) as something to look for inside the binary — it likely doesn't exist there.

**Status:** Inference, pending confirmation via disassembly (check whether `IDDCX_ADAPTER_FLAGS_REMOTE_SESSION_DRIVER` appears referenced at all in `lci_iddcx.dll`).

---

## 4. Debug Tooling — usable before any disassembly

This is the most actionable section for HASHI's methodology: these are OS-level, registry-driven debug facilities that apply to *any* IddCx driver, including Splashtop's, without needing to touch the binary at all.

### 4.1 Frame capture dump

**Fact:** Starting with a sufficiently recent Windows build, IddCx can dump the literal desktop frames it hands to the driver, as PNG files — a debug facility built into the OS class extension itself, independent of the vendor driver.

**Fact — registry location:** `HKLM\System\CurrentControlSet\Control\GraphicsDrivers\IddCxFrameCapture` (create this key first), gated by a master bit in `IddCxDebugCtrl` under `HKLM\System\CurrentControlSet\Control\GraphicsDrivers`.

**Fact — relevant values:**

| Value | Default | Meaning |
|---|---|---|
| `TriggerUniqueness` | 0 | Nonzero + changed from last read = (re)start a capture session |
| `TargetMask` | 0xffff | Bitmask of which target indices to capture |
| `CaptureCount` | 10 | Number of frames to capture once triggered |
| `SkipFrames` | 0 | Frames to skip between captures |
| `CaptureSessionID` | 0 | Which session to capture (0 = console) |
| `ScaleFactor` | 100 | Output scale, 1–100 |
| `CaptureFolder` | `C:\IddCxImages` | Output directory |

**Fact:** Captured file naming encodes session, adapter LUID, target index, and IddCx's own frame counter: `S<session>_Ad<LUID>_T<target>_Frame<n>_<date>_<time>.png`.

**Fact:** This functionality is disabled whenever an OPM (protected content) session is active on the driver.

**Inference for HASHI:** This lets you capture ground-truth frame data — exact resolution, pixel format, cadence — that Windows is feeding into Splashtop's `lci_iddcx.dll`, entirely through documented OS behavior. No Ghidra, no binary modification, no ToS-relevant reverse engineering of Splashtop's own code — you're just using a Microsoft-documented Windows debug feature while Splashtop happens to be running. This should be one of the first concrete experiments run, before opening the DLL in a disassembler.

### 4.2 WPP call tracing

**Fact:** IddCx logs its internal operation via WPP tracing, capturable with `logman.exe` (built into Windows) into an `.etl` file, keyed by GUID `{D92BCB52-FA78-406F-A9A5-2037509FADEA}`.

**Fact:** The `Flags` bitmask controls granularity — of particular interest:

| Bit | Captures |
|---|---|
| 0x040 | DDI calls **from IddCx to the driver** |
| 0x080 | Low-frequency calls **from driver to IddCx** |
| 0x100 | High-frequency **frame-related** calls from driver to IddCx |
| 0x200 | High-frequency **cursor-related** calls from driver to IddCx |

**Inference:** A trace with `0x1f4` (per-frame detail enabled) would show the exact DDI call sequence IddCx drives into `lci_iddcx.dll` during normal operation — including which callback fires per frame — giving a call-order map before ever disassembling the binary. This directly informs which exported/imported functions inside `lci_iddcx.dll` are worth prioritizing in Ghidra.

**Fact:** Decoding WPP output requires the matching `IddCx.pdb`; Microsoft states public-symbol-server PDBs contain the necessary WPP info starting with a specific Windows build (19560), not before.

---

## 5. Versioning

**Fact:** IddCx has its own version scheme (`IddCxGetVersion`), independent of the Windows build number, with compatibility ranges published by Microsoft. A driver built against IddCx 1.4+ can use runtime feature-detection macros (`IDD_IS_FUNCTION_AVAILABLE`, `IDD_IS_FIELD_AVAILABLE`) to support multiple Windows versions from one binary.

**Corrected 2026-10-14.** The earlier inference that `UmdfExtensions = IddCx0102` pins the driver to IddCx 1.2 was wrong.

**Fact:** Microsoft's current sample INF, which targets Windows 11, declares the same `IddCx0102`. The value is the UMDF class-extension binding, constant across IddCx versions.
**Fact:** The IddCx API level is fixed at build time by the WDK headers and `IDDCX_MINIMUM_VERSION_REQUIRED`; runtime checks use `IddCxGetVersion`, `IDD_IS_FUNCTION_AVAILABLE`, `IDD_IS_FIELD_AVAILABLE` ("Building IddCx 1.4 drivers"). Version values: 1.2 = 0x1200 (Win10 1709), 1.3 = 0x1300/0x1380 (1803/1809), 1.4 = 0x1400 (1903), 1.5 = 0x1500 (2004–22H2), 1.8–1.10 on Windows 11 ("IddCx versions").
**Fact:** Windows 10 1709 (IddCx 1.2) can load only 1.0 and 1.2 drivers; 1803+ (IddCx 1.3) can load 1.0–1.3 drivers and 1.4+ drivers built with the minimum-version mechanism.
**Inference:** With a 2018-12-04 build date, `lci_iddcx.dll` most likely targets IddCx 1.3 or earlier. Features from 1.4+ (remote-session flags, `IddCxAdapterSetRenderAdapter`, system-memory swapchains, HDR) are then absent, which is consistent with the console-IDD inference in §3.
**Status:** confirm in the binary (Week 4 checklist in the study plan).

---

## 6. Open Questions Carried Forward

1. Is `lci_iddcx.dll` confirmed as a console IDD (no `IDDCX_ADAPTER_FLAGS_REMOTE_SESSION_DRIVER` reference)?
2. What does a WPP trace (`0x1f4`) actually show during Splashtop mirror mode vs. extended display mode — same DDI sequence, or different?
3. What does IddCx frame capture reveal about the real pixel format/resolution/cadence handed to the driver, before any encoding Splashtop itself performs?
4. Does `IddCxGetVersion` returning a value consistent with IddCx 1.2 rule out any DDI callbacks this reference describes as newer (1.4+)?
5. How does `lci_proxywddm.sys` fit in — is it invoked at all during the `EvtIddCxMonitorAssignSwapChain` frame loop, or is it isolated to a different responsibility entirely (e.g., USB endpoint management rather than display)?

---

## 7. Next Concrete Actions

1. Enable `IddCxDebugCtrl` + `IddCxFrameCapture` registry keys on a test machine running Splashtop; capture and inspect real frames.
2. Capture a WPP trace (`logman`, flags `0x1f4`) across a full mirror-mode session and a full extended-display session; diff the DDI call sequences.
3. Cross-reference `IddCxGetVersion` output against Microsoft's version table to pin down exactly which IddCx feature set `lci_iddcx.dll` was built against.
4. Only after the above: open `lci_iddcx.dll` in Ghidra, using the frame-capture and WPP findings to identify which functions correspond to `EvtIddCxMonitorAssignSwapChain` and the per-frame processing loop.
