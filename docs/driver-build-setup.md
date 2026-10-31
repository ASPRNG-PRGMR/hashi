# Driver Build Environment — Setup Notes

**Project:** HASHI (Host Adapter for Splashtop Hardware Interop)
**Purpose:** Build Microsoft's official IDDCX sample driver, with full debug symbols, to use as a labeled ground-truth baseline for binary diffing against `lci_iddcx.dll`.

This is a prerequisite step for the binary-diffing methodology described in `reverse-engineering-methodology.md` — it does not touch Splashtop's driver at all. Everything here is building and inspecting Microsoft's own open-source sample.

---

## Why build the sample at all

Binary diffing only works if one side of the comparison is *labeled*. Without a symboled baseline, there's no way to tell which code in `lci_iddcx.dll` is Microsoft's IddCx framework boilerplate and which is LuminonCore's actual contribution.

Illustrative example — both `sample.dll` and `lci_iddcx.dll` implement `EvtIddCxMonitorAssignSwapChain()`. Microsoft's version is plausibly just:

```
AcquireSwapChain();
while (running) {
    ProcessFrame();
}
```

LuminonCore's version plausibly extends it:

```
AcquireSwapChain();
InitializeEncoder();
while (running) {
    ProcessFrame();
    Encode();
    SendUSB();
}
```

The sample lets us subtract the boilerplate — `AcquireSwapChain()` and the frame loop shape are Microsoft's; `InitializeEncoder()`, `Encode()`, `SendUSB()` are the actual research target.

## What the WDK is, and why GCC can't build this

The Windows Driver Kit (WDK) is Microsoft's SDK for kernel and driver development — headers, libraries, driver templates, build tools, sample drivers, Visual Studio integration, signing utilities. Without it, nothing knows how to compile a driver project.

The sample uses IddCx-specific types and functions that exist *only* in the WDK's headers/libs:

- `IddCxAdapterInitAsync()`
- `WdfDeviceCreate()`
- `IDDCX_SWAPCHAIN`
- `EVT_IDD_CX_MONITOR_ASSIGN_SWAPCHAIN`

No compiler can resolve these without the WDK's headers and import libraries — this isn't a GCC limitation, it's a missing-dependency problem regardless of toolchain.

Three components work together:

| Component | Role |
|---|---|
| Visual Studio Community | IDE / build orchestration |
| Windows SDK | Normal Windows application development |
| Windows Driver Kit (WDK) | Driver-specific headers, libs, templates, signing tools |

"Building" here means compiling Microsoft's sample exactly as intended — not writing new code, the same way building the Linux kernel from source doesn't mean writing it.

## Debug and Release — build both (corrected 2026-10-14)

Earlier text here said only Debug builds keep names. That was wrong. Names live in the **PDB**, which Visual Studio driver projects emit for Release builds too. The configuration controls optimization, not symbols.

- **Release + PDB** is the primary baseline: its code shape (inlining, register allocation, RSP-relative frames) matches what a vendor ships, so it diffs and reads like `lci_iddcx.dll` will.
- **Debug + PDB** is the reading copy: one C++ statement maps to a few instructions, which is easier while learning.

Without a PDB either build shows only generated labels such as `FUN_18003f210`.

## What a PDB is

A PDB (Program Database) is everything the compiler normally discards when producing a binary: function names, variable names, structure/enum definitions, source filenames, line numbers, type information. The CPU only ever sees addresses (`0x180023450`); the PDB is the separate file that maps those addresses back to human-meaningful names.

Ghidra reads PDBs directly — importing one turns `FUN_180012340` into `EvtIddCxMonitorAssignSwapChain` throughout the whole disassembly.

Vendors, including LuminonCore/Splashtop, don't ship PDBs publicly — that's expected and normal (it's exactly what makes reverse engineering necessary in the first place). Microsoft does publish PDBs for many of its own binaries via its public symbol server, but that doesn't extend to third-party drivers built on top of its frameworks.

## The plan this build step feeds into

```
Microsoft Sample
      ↓ build (Debug, /DEBUG)
sample.dll + PDB
      ↓ import into Ghidra, load PDB
Fully symboled disassembly
      ↓ study architecture, confirm IddCx object lifecycle in practice
Only THEN
      ↓
Open lci_iddcx.dll in Ghidra, diff against the sample
```

This is the textbook-before-implementation approach — understand Microsoft's intended shape first, so LuminonCore's deviations from it are obvious rather than needing to be discovered cold.

---

## Setup Checklist

Install only — do not build yet. Verify the environment before moving to the sample project.

- [ ] Visual Studio 2022 Community **or** Visual Studio 2026 Community (the WDK officially supports both as of 2026; Microsoft's download page lagged and still named VS 2022 when checked on 2026-10-14)
- [ ] Current Windows SDK
- [ ] Current Windows Driver Kit (WDK), installed after the SDK, same build number

Install inside the existing GNOME Boxes `win11` VM on the Fedora host (image last modified 2026-09-02). Give it at least 60 GB of disk if it does not already have it; VS + SDK + WDK is large.

**Version note (corrected 2026-10-14):** `UmdfExtensions = IddCx0102` is the UMDF class-extension binding and is still what Microsoft's Windows 11 sample declares. It does not pin IddCx 1.2. The IddCx API level is chosen at build time (`IDDCX_MINIMUM_VERSION_REQUIRED` plus the WDK headers). Given the 2018-12 build date, the vendor driver most likely targets IddCx 1.3 or earlier (inference). Do not hunt for an old WDK; build the current sample with the current WDK. The sample's `Driver.cpp` uses no version-gated features, so its shape is the same at any IddCx level.

## Next Steps (once installed)

1. Verify the installed toolchain is correctly recognized (Visual Studio can see the WDK, driver project templates are available).
2. Clone `Windows-driver-samples`:
   ```
   git clone https://github.com/microsoft/Windows-driver-samples
   ```
3. Locate the sample at `video/IndirectDisplay/`.
4. Inspect the project structure before compiling — understand what's in it before building it.
5. Build **Release** (x64) and **Debug** (x64). Both produce `IddSampleDriver.dll` plus `IddSampleDriver.pdb` in their output folders. Keep each pair together.
6. Note that the public sample was first published 2020-02-19, after the vendor driver's 2018-12 build; it is a textbook for the framework shape, not the vendor's starting point.
6. Proceed to the binary-diffing workflow (Ghidra Version Tracking, then BinDiff/BinExport) described in `reverse-engineering-methodology.md`, using this build as the labeled baseline against `lci_iddcx.dll`.
